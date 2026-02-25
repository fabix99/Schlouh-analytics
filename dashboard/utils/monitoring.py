"""Error tracking and performance monitoring utilities.

This module provides:
- Sentry error tracking integration
- Performance monitoring with timing decorators
- Logging utilities for dashboard operations

Usage:
    from dashboard.utils.monitoring import init_sentry, timing_decorator, monitor_performance

    # Initialize Sentry in app entry point
    init_sentry(dsn="your-dsn-here")

    # Use timing decorator on slow operations
    @timing_decorator
    def load_player_data():
        ...
"""

import time
import functools
import contextlib
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dashboard')

# =============================================================================
# SENTRY ERROR TRACKING (TASK INF-003)
# =============================================================================

_sentry_initialized = False

def init_sentry(
    dsn: Optional[str] = None,
    environment: str = "development",
    release: Optional[str] = None,
    sample_rate: float = 1.0,
    traces_sample_rate: float = 0.1,
) -> bool:
    """Initialize Sentry for error tracking.

    Args:
        dsn: Sentry DSN (Data Source Name). If None, Sentry won't be initialized.
        environment: Environment name (development, staging, production)
        release: Release version string
        sample_rate: Error sampling rate (0.0 to 1.0)
        traces_sample_rate: Performance trace sampling rate

    Returns:
        True if Sentry was successfully initialized
    """
    global _sentry_initialized

    if not dsn:
        logger.info("Sentry DSN not provided, error tracking disabled")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.streamlit import StreamlitIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            sample_rate=sample_rate,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=0.1,
            integrations=[
                StreamlitIntegration(),
            ],
        )

        _sentry_initialized = True
        logger.info(f"Sentry initialized for {environment} environment")
        return True

    except ImportError:
        logger.warning("sentry-sdk not installed, error tracking disabled")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def set_sentry_user(user_id: Optional[str] = None, email: Optional[str] = None, **kwargs) -> None:
    """Set user context for Sentry errors.

    Args:
        user_id: User identifier
        email: User email
        **kwargs: Additional user attributes
    """
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk
        user_data = {"id": user_id, "email": email}
        user_data.update(kwargs)
        sentry_sdk.set_user({k: v for k, v in user_data.items() if v is not None})
    except Exception as e:
        logger.warning(f"Failed to set Sentry user: {e}")


def set_sentry_tag(key: str, value: str) -> None:
    """Set a tag for filtering in Sentry.

    Args:
        key: Tag key
        value: Tag value
    """
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk
        sentry_sdk.set_tag(key, value)
    except Exception as e:
        logger.warning(f"Failed to set Sentry tag: {e}")


def capture_exception(error: Exception, context: Optional[Dict] = None) -> Optional[str]:
    """Capture an exception in Sentry.

    Args:
        error: Exception to capture
        context: Additional context data

    Returns:
        Event ID if captured, None otherwise
    """
    if not _sentry_initialized:
        logger.exception("Exception captured (Sentry not configured)", exc_info=error)
        return None

    try:
        import sentry_sdk

        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_extra(key, value)
                event_id = sentry_sdk.capture_exception(error)
                return event_id
        else:
            return sentry_sdk.capture_exception(error)

    except Exception as e:
        logger.error(f"Failed to capture exception in Sentry: {e}")
        return None


def capture_message(message: str, level: str = "info") -> Optional[str]:
    """Capture a message in Sentry.

    Args:
        message: Message to capture
        level: Log level (debug, info, warning, error, fatal)

    Returns:
        Event ID if captured, None otherwise
    """
    if not _sentry_initialized:
        logger.log(getattr(logging, level.upper(), logging.INFO), message)
        return None

    try:
        import sentry_sdk
        return sentry_sdk.capture_message(message, level=level)
    except Exception as e:
        logger.error(f"Failed to capture message in Sentry: {e}")
        return None


# =============================================================================
# PERFORMANCE MONITORING (TASK INF-004)
# =============================================================================

@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self) -> None:
        """Mark the operation as finished."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000


class PerformanceMonitor:
    """Simple performance monitor for dashboard operations."""

    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self.slow_threshold_ms = 1000  # Log warnings for operations > 1s

    def start(self, operation_name: str, **metadata) -> PerformanceMetrics:
        """Start timing an operation.

        Args:
            operation_name: Name of the operation
            **metadata: Additional context

        Returns:
            PerformanceMetrics object
        """
        metric = PerformanceMetrics(
            operation_name=operation_name,
            start_time=time.time(),
            metadata=metadata
        )
        self.metrics.append(metric)
        return metric

    def finish(self, metric: PerformanceMetrics) -> None:
        """Finish timing an operation."""
        metric.finish()
        self._log_if_slow(metric)

    def _log_if_slow(self, metric: PerformanceMetrics) -> None:
        """Log warning if operation was slow."""
        if metric.duration_ms and metric.duration_ms > self.slow_threshold_ms:
            logger.warning(
                f"Slow operation: {metric.operation_name} took {metric.duration_ms:.2f}ms "
                f"(threshold: {self.slow_threshold_ms}ms)"
            )

    def get_slow_operations(self, threshold_ms: Optional[float] = None) -> List[PerformanceMetrics]:
        """Get operations that exceeded threshold.

        Args:
            threshold_ms: Threshold in milliseconds (default: slow_threshold_ms)

        Returns:
            List of slow PerformanceMetrics
        """
        threshold = threshold_ms or self.slow_threshold_ms
        return [m for m in self.metrics if m.duration_ms and m.duration_ms > threshold]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        if not self.metrics:
            return {"count": 0}

        durations = [m.duration_ms for m in self.metrics if m.duration_ms is not None]
        return {
            "count": len(self.metrics),
            "total_duration_ms": sum(durations),
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "slow_operations": len(self.get_slow_operations()),
        }

    def clear(self) -> None:
        """Clear all metrics."""
        self.metrics = []


# Global performance monitor instance
_performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    return _performance_monitor


def timing_decorator(func: Callable) -> Callable:
    """Decorator to time function execution and log slow operations.

    Usage:
        @timing_decorator
        def load_player_data():
            # Your data loading logic
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        monitor = get_performance_monitor()
        metric = monitor.start(
            operation_name=func.__name__,
            args=str(args)[:100],
            kwargs=str(kwargs)[:100]
        )

        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            metric.metadata['error'] = str(e)
            raise
        finally:
            monitor.finish(metric)

    return wrapper


@contextlib.contextmanager
def monitor_performance(operation_name: str, **metadata):
    """Context manager for monitoring performance of a code block.

    Usage:
        with monitor_performance("filter_operation", filter_count=5):
            # Your filter logic here
            pass
    """
    monitor = get_performance_monitor()
    metric = monitor.start(operation_name, **metadata)

    try:
        yield metric
    except Exception as e:
        metric.metadata['error'] = str(e)
        raise
    finally:
        monitor.finish(metric)


def log_slow_operations(threshold_ms: float = 1000) -> None:
    """Log all slow operations.

    Args:
        threshold_ms: Threshold in milliseconds
    """
    monitor = get_performance_monitor()
    slow_ops = monitor.get_slow_operations(threshold_ms)

    if slow_ops:
        logger.warning(f"Found {len(slow_ops)} slow operations (> {threshold_ms}ms):")
        for op in slow_ops:
            logger.warning(
                f"  - {op.operation_name}: {op.duration_ms:.2f}ms"
            )


# =============================================================================
# DASHBOARD ERROR HANDLER
# =============================================================================

class DashboardErrorHandler:
    """Centralized error handling for dashboard operations."""

    def __init__(self, use_sentry: bool = True):
        self.use_sentry = use_sentry and _sentry_initialized

    def handle_error(
        self,
        error: Exception,
        user_message: Optional[str] = None,
        context: Optional[Dict] = None,
        raise_error: bool = False
    ) -> None:
        """Handle an error with optional Sentry capture and user feedback.

        Args:
            error: The exception that occurred
            user_message: Message to display to the user
            context: Additional context for Sentry
            raise_error: Whether to re-raise the error
        """
        # Log the error
        logger.exception("Dashboard error occurred", exc_info=error)

        # Capture in Sentry if available
        if self.use_sentry:
            capture_exception(error, context)

        # Show user message if in Streamlit context
        try:
            import streamlit as st
            if user_message:
                st.error(user_message)
            else:
                st.error("An unexpected error occurred. Please try again.")
        except Exception:
            pass  # Not in Streamlit context

        if raise_error:
            raise


# Global error handler instance
_error_handler: Optional[DashboardErrorHandler] = None


def get_error_handler() -> DashboardErrorHandler:
    """Get or create the global error handler."""
    global _error_handler
    if _error_handler is None:
        _error_handler = DashboardErrorHandler(use_sentry=_sentry_initialized)
    return _error_handler


def safe_execute(
    func: Callable,
    *args,
    default_return: Any = None,
    error_message: Optional[str] = None,
    **kwargs
) -> Any:
    """Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Positional arguments
        default_return: Value to return on error
        error_message: Message to show on error
        **kwargs: Keyword arguments

    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        handler = get_error_handler()
        handler.handle_error(e, user_message=error_message)
        return default_return


# =============================================================================
# HEALTH CHECK UTILITIES
# =============================================================================

def run_health_checks() -> Dict[str, Any]:
    """Run basic health checks for the dashboard.

    Returns:
        Dictionary with health check results
    """
    checks = {
        "timestamp": datetime.now().isoformat(),
        "sentry": _sentry_initialized,
        "checks": {}
    }

    # Check data loading
    try:
        from dashboard.utils.data import load_enriched_season_stats
        with monitor_performance("health_check_data_load"):
            df = load_enriched_season_stats()
            checks["checks"]["data_load"] = {
                "status": "ok",
                "rows": len(df) if df is not None else 0
            }
    except Exception as e:
        checks["checks"]["data_load"] = {"status": "error", "message": str(e)}

    # Check filter components
    try:
        from dashboard.utils.filter_components import FilterState
        _ = FilterState()
        checks["checks"]["filter_components"] = {"status": "ok"}
    except Exception as e:
        checks["checks"]["filter_components"] = {"status": "error", "message": str(e)}

    # Check search components
    try:
        from dashboard.utils.search_components import SearchDebouncer
        _ = SearchDebouncer()
        checks["checks"]["search_components"] = {"status": "ok"}
    except Exception as e:
        checks["checks"]["search_components"] = {"status": "error", "message": str(e)}

    # Overall status
    all_ok = all(c.get("status") == "ok" for c in checks["checks"].values())
    checks["status"] = "healthy" if all_ok else "degraded"

    return checks


def render_health_status() -> None:
    """Render health status in Streamlit."""
    import streamlit as st

    checks = run_health_checks()

    if checks["status"] == "healthy":
        st.success("✅ All systems operational")
    else:
        st.warning("⚠️ Some systems are degraded")

    with st.expander("Health Check Details"):
        st.json(checks)
