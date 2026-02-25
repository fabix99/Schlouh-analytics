"""Advanced analytics utilities for Phase 4.

This module provides:
- Correlation analysis tools
- Similarity search algorithms
- Pattern recognition
- Predictive metrics
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from scipy import stats
from scipy.spatial.distance import cdist
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots


@dataclass
class CorrelationResult:
    """Result of correlation analysis."""
    metric1: str
    metric2: str
    correlation: float
    p_value: float
    strength: str
    sample_size: int
    significance: str


class CorrelationAnalyzer:
    """Analyze correlations between player/team metrics."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    def find_correlations(
        self,
        min_correlation: float = 0.3,
        p_threshold: float = 0.05,
        exclude_cols: Optional[List[str]] = None
    ) -> List[CorrelationResult]:
        """Find significant correlations in the dataset.

        Args:
            min_correlation: Minimum absolute correlation to report
            p_threshold: Maximum p-value for significance
            exclude_cols: Columns to exclude from analysis

        Returns:
            List of CorrelationResult objects
        """
        if exclude_cols:
            cols = [c for c in self.numeric_cols if c not in exclude_cols]
        else:
            cols = self.numeric_cols

        results = []

        for i, col1 in enumerate(cols):
            for col2 in cols[i+1:]:
                # Get valid data (non-null pairs)
                data = self.df[[col1, col2]].dropna()

                if len(data) < 10:  # Need minimum sample size
                    continue

                # Calculate Pearson correlation
                corr, p_value = stats.pearsonr(data[col1], data[col2])

                if abs(corr) >= min_correlation and p_value <= p_threshold:
                    # Determine strength
                    if abs(corr) >= 0.8:
                        strength = "Very Strong"
                    elif abs(corr) >= 0.6:
                        strength = "Strong"
                    elif abs(corr) >= 0.4:
                        strength = "Moderate"
                    else:
                        strength = "Weak"

                    significance = "Highly Significant" if p_value < 0.01 else "Significant"

                    results.append(CorrelationResult(
                        metric1=col1,
                        metric2=col2,
                        correlation=corr,
                        p_value=p_value,
                        strength=strength,
                        sample_size=len(data),
                        significance=significance
                    ))

        return sorted(results, key=lambda x: abs(x.correlation), reverse=True)

    def render_correlation_heatmap(
        self,
        cols: Optional[List[str]] = None,
        height: int = 600
    ) -> None:
        """Render an interactive correlation heatmap.

        Args:
            cols: Columns to include (None for all numeric)
            height: Plot height in pixels
        """
        if cols is None:
            cols = self.numeric_cols[:15]  # Limit to 15 for readability

        # Calculate correlation matrix
        corr_matrix = self.df[cols].corr()

        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.columns,
            colorscale="RdBu",
            zmid=0,
            zmin=-1,
            zmax=1,
            text=np.round(corr_matrix.values, 2),
            texttemplate="%{text}",
            textfont={"size": 9},
            hovertemplate="%{y} vs %{x}<br>Correlation: %{z:.3f}<extra></extra>",
        ))

        fig.update_layout(
            title="Correlation Matrix",
            width=800,
            height=height,
            xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
            yaxis=dict(tickfont=dict(size=10)),
            paper_bgcolor="#0D1117",
            plot_bgcolor="#161B22",
            font=dict(color="#F0F6FC"),
        )

        st.plotly_chart(fig, use_container_width=True)

    def render_scatter_matrix(
        self,
        cols: List[str],
        color_col: Optional[str] = None
    ) -> None:
        """Render a scatter plot matrix (SPLOM).

        Args:
            cols: Columns to visualize (max 5 recommended)
            color_col: Optional column for color encoding
        """
        if len(cols) > 5:
            cols = cols[:5]
            st.warning("Limited to 5 variables for readability")

        fig = go.Figure(data=go.Splom(
            dimensions=[dict(label=col, values=self.df[col]) for col in cols],
            marker=dict(
                color=self.df[color_col] if color_col else None,
                colorscale="Cividis",
                showscale=bool(color_col),
                size=5,
                opacity=0.7,
            ),
            diagonal=dict(visible=True),
        ))

        fig.update_layout(
            title="Scatter Plot Matrix",
            paper_bgcolor="#0D1117",
            plot_bgcolor="#161B22",
            font=dict(color="#F0F6FC"),
            height=700,
        )

        st.plotly_chart(fig, use_container_width=True)


class SimilarityEngine:
    """Find similar players/teams based on statistical profiles."""

    def __init__(self, df: pd.DataFrame, id_col: str = "player_id"):
        self.df = df
        self.id_col = id_col
        self.features = df.select_dtypes(include=[np.number]).columns.tolist()

    def find_similar(
        self,
        target_id: Any,
        n_results: int = 5,
        features: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        """Find most similar entities to the target.

        Args:
            target_id: ID of the target entity
            n_results: Number of similar results to return
            features: Features to use for comparison (None for all numeric)
            weights: Optional feature weights

        Returns:
            DataFrame with similar entities and similarity scores
        """
        if features:
            feature_cols = features
        else:
            feature_cols = self.features

        # Get target vector
        target_row = self.df[self.df[self.id_col] == target_id]
        if target_row.empty:
            return pd.DataFrame()

        target_vector = target_row[feature_cols].values.reshape(1, -1)

        # Prepare comparison data (exclude target itself)
        compare_df = self.df[self.df[self.id_col] != target_id].copy()
        compare_matrix = compare_df[feature_cols].values

        # Apply weights if provided
        if weights:
            weight_array = np.array([weights.get(col, 1.0) for col in feature_cols])
            target_vector = target_vector * weight_array
            compare_matrix = compare_matrix * weight_array

        # Handle NaN values
        target_vector = np.nan_to_num(target_vector, nan=0.0)
        compare_matrix = np.nan_to_num(compare_matrix, nan=0.0)

        # Calculate cosine similarity
        similarities = self._cosine_similarity(target_vector, compare_matrix)

        # Add similarity scores
        compare_df['similarity_score'] = similarities
        compare_df['similarity_pct'] = (similarities * 100).round(1)

        # Return top N results
        return compare_df.nlargest(n_results, 'similarity_score')

    def _cosine_similarity(self, target: np.ndarray, candidates: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity between target and candidates."""
        # Normalize vectors
        target_norm = target / (np.linalg.norm(target, axis=1, keepdims=True) + 1e-10)
        cand_norm = candidates / (np.linalg.norm(candidates, axis=1, keepdims=True) + 1e-10)

        # Calculate similarity
        return np.dot(cand_norm, target_norm.T).flatten()

    def render_similarity_results(
        self,
        target_name: str,
        similar_df: pd.DataFrame,
        display_cols: List[str]
    ) -> None:
        """Render similarity search results.

        Args:
            target_name: Name of the target entity
            similar_df: DataFrame with similar entities
            display_cols: Columns to display for each result
        """
        st.markdown(f"**Players/Teams Similar to {target_name}**")

        for _, row in similar_df.iterrows():
            similarity = row.get('similarity_pct', 0)

            # Color based on similarity
            if similarity >= 90:
                color = "#3FB950"  # Green
            elif similarity >= 75:
                color = "#C9A840"  # Gold
            elif similarity >= 60:
                color = "#58A6FF"  # Blue
            else:
                color = "#8B949E"  # Gray

            with st.container():
                st.markdown(
                    f"""
                    <div style="background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 15px; margin: 10px 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <div style="font-weight: 600; color: #F0F6FC;">{row.get('player_name', row.get('team_name', 'Unknown'))}</div>
                            <div style="background: {color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;">
                                {similarity:.1f}% Match
                            </div>
                        </div>
                        <div style="display: flex; gap: 20px; font-size: 0.85rem; color: #8B949E;">
                    """,
                    unsafe_allow_html=True
                )

                # Display key stats
                for col in display_cols[:4]:  # Limit to 4
                    if col in row.index:
                        st.markdown(
                            f"<span><strong>{col.replace('_', ' ').title()}:</strong> {row[col]}</span>",
                            unsafe_allow_html=True
                        )

                st.markdown("</div></div>", unsafe_allow_html=True)


class PatternRecognizer:
    """Identify patterns and outliers in data."""

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def find_outliers(
        self,
        column: str,
        method: str = "iqr",
        threshold: float = 1.5
    ) -> pd.DataFrame:
        """Find outliers in a column.

        Args:
            column: Column to analyze
            method: "iqr" or "zscore"
            threshold: Threshold for outlier detection

        Returns:
            DataFrame with outliers
        """
        data = self.df[column].dropna()

        if method == "iqr":
            Q1 = data.quantile(0.25)
            Q3 = data.quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - threshold * IQR
            upper = Q3 + threshold * IQR
            outliers = self.df[(self.df[column] < lower) | (self.df[column] > upper)]
        else:  # zscore
            z_scores = np.abs(stats.zscore(data))
            outlier_indices = data[z_scores > threshold].index
            outliers = self.df.loc[outlier_indices]

        return outliers

    def detect_trends(
        self,
        column: str,
        time_col: str,
        window: int = 5
    ) -> Dict[str, Any]:
        """Detect trends in time-series data.

        Args:
            column: Value column
            time_col: Time/date column
            window: Rolling window size

        Returns:
            Dictionary with trend analysis
        """
        df_sorted = self.df.sort_values(time_col)
        rolling_mean = df_sorted[column].rolling(window=window).mean()

        # Calculate trend direction
        first_half = rolling_mean.iloc[:len(rolling_mean)//2].mean()
        second_half = rolling_mean.iloc[len(rolling_mean)//2:].mean()

        if second_half > first_half * 1.05:
            direction = "Improving"
        elif second_half < first_half * 0.95:
            direction = "Declining"
        else:
            direction = "Stable"

        # Calculate volatility
        volatility = df_sorted[column].std() / df_sorted[column].mean()

        return {
            "direction": direction,
            "volatility": volatility,
            "current_value": df_sorted[column].iloc[-1] if len(df_sorted) > 0 else None,
            "trend_strength": abs(second_half - first_half) / (first_half + 1e-10),
        }


def render_correlation_insights(results: List[CorrelationResult], top_n: int = 5) -> None:
    """Render insights from correlation analysis.

    Args:
        results: List of CorrelationResult objects
        top_n: Number of top correlations to display
    """
    if not results:
        st.info("No significant correlations found with current thresholds")
        return

    st.markdown(f"**Top {top_n} Correlations Found**")

    for result in results[:top_n]:
        # Direction indicator
        direction = "📈 Positive" if result.correlation > 0 else "📉 Negative"
        color = "#3FB950" if result.correlation > 0 else "#F85149"

        st.markdown(
            f"""
            <div style="background: #161B22; border-left: 4px solid {color}; padding: 12px; margin: 8px 0; border-radius: 0 6px 6px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-weight: 600; color: #F0F6FC;">{result.metric1} ↔ {result.metric2}</span>
                    <span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">{direction}</span>
                </div>
                <div style="font-size: 0.85rem; color: #8B949E;">
                    Correlation: <strong>{result.correlation:.3f}</strong> ({result.strength}) |
                    {result.significance} (p={result.p_value:.4f}) |
                    n={result.sample_size}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


def calculate_predictive_metrics(
    df: pd.DataFrame,
    target: str,
    features: List[str]
) -> Dict[str, Any]:
    """Calculate metrics for predictive modeling.

    Args:
        df: DataFrame with data
        target: Target variable column
        features: Feature columns

    Returns:
        Dictionary with predictive metrics
    """
    # Clean data
    clean_df = df[[target] + features].dropna()

    if len(clean_df) < 10:
        return {"error": "Insufficient data"}

    # Calculate feature importance via correlation with target
    importance = {}
    for feature in features:
        corr, p_value = stats.pearsonr(clean_df[target], clean_df[feature])
        importance[feature] = {
            "correlation": corr,
            "abs_correlation": abs(corr),
            "p_value": p_value,
            "significant": p_value < 0.05
        }

    # Sort by absolute correlation
    importance = dict(sorted(
        importance.items(),
        key=lambda x: x[1]["abs_correlation"],
        reverse=True
    ))

    # Calculate variance explained
    top_3_features = list(importance.keys())[:3]
    if len(top_3_features) >= 2:
        # Simple R² approximation
        combined_corr = np.mean([importance[f]["abs_correlation"] for f in top_3_features])
        r_squared_approx = combined_corr ** 2
    else:
        r_squared_approx = 0

    return {
        "target": target,
        "n_samples": len(clean_df),
        "feature_importance": importance,
        "top_features": top_3_features,
        "predictive_power": r_squared_approx,
        "data_quality": len(clean_df) / len(df)
    }
