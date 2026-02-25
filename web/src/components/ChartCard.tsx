import type { ReactNode } from "react";

const cardStyle: React.CSSProperties = {
  background: "var(--schlouh-card)",
  borderRadius: 12,
  padding: "20px 20px 14px",
  marginBottom: 20,
};

const titleStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontWeight: 700,
  fontSize: "1.1rem",
  color: "var(--schlouh-text)",
  margin: "0 0 4px 0",
};

const subtitleStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontSize: "0.8rem",
  color: "var(--schlouh-text-secondary)",
  margin: "0 0 12px 0",
};

const footerStyle: React.CSSProperties = {
  marginTop: 8,
  paddingTop: 10,
  borderTop: "1px solid var(--schlouh-border)",
  fontSize: "var(--schlouh-footnote-size)",
  color: "var(--schlouh-text-muted)",
};

export function ChartCard({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: string;
}) {
  return (
    <article style={cardStyle}>
      <h2 style={titleStyle}>{title}</h2>
      {subtitle && <p style={subtitleStyle}>{subtitle}</p>}
      {children}
      {footer && <div style={footerStyle}>{footer}</div>}
    </article>
  );
}
