"""UI Theme, modern design tokens, custom CSS and formatters for Streamlit."""

from __future__ import annotations


def format_vnd(amount: float | int | None) -> str:
    """Format a numeric value into standard Vietnamese currency (e.g. 6.711.000 ₫)."""
    if amount is None:
        return "—"
    rounded = int(round(float(amount)))
    return f"{rounded:,} ₫".replace(",", ".")


def format_eur(amount: float | int | None) -> str:
    """Format a numeric value into EUR currency (e.g. 68.93 €)."""
    if amount is None:
        return "—"
    return f"{float(amount):,.2f} €"


def format_rate(rate: float | None) -> str:
    """Format a decimal rate into percentage (e.g. 75.0%)."""
    if rate is None:
        return "—"
    return f"{rate:.1%}"


def format_days(days: float | None) -> str:
    """Format duration in days (e.g. 18.5 ngày)."""
    if days is None:
        return "—"
    return f"{days:.1f} ngày"


def inject_custom_css() -> None:
    """Inject modern Financial Terminal CSS for cards, badges, and typography."""
    import streamlit as st

    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        .mono-num {
            font-family: "SF Mono", "Fira Code", Consolas, monospace;
            font-variant-numeric: tabular-nums;
        }
        .cuti-topbar {
            display: flex; align-items: center; justify-content: space-between;
            background: rgba(15, 23, 42, 0.03); border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 10px; padding: 10px 16px; margin-bottom: 20px; font-size: 0.85rem;
        }
        .cuti-topbar-left { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
        .status-pill {
            display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px;
            border-radius: 6px; font-size: 0.78rem; font-weight: 600;
            background: rgba(16, 185, 129, 0.12); color: #059669; border: 1px solid rgba(16, 185, 129, 0.25);
        }
        .status-dot { width: 7px; height: 7px; border-radius: 50%; background-color: #10b981; display: inline-block; }
        .verdict-hero {
            border-radius: 12px; padding: 18px 22px; margin-bottom: 18px;
            display: flex; justify-content: space-between; align-items: center; border-width: 1px; border-style: solid;
        }
        .verdict-hero-green { background: rgba(16, 185, 129, 0.08); border-color: rgba(16, 185, 129, 0.35); }
        .verdict-hero-yellow { background: rgba(245, 158, 11, 0.08); border-color: rgba(245, 158, 11, 0.35); }
        .verdict-hero-red { background: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.35); }
        .verdict-hero-insufficient { background: rgba(100, 116, 139, 0.08); border-color: rgba(100, 116, 139, 0.3); }
        .verdict-badge {
            display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px;
            border-radius: 6px; font-size: 0.78rem; font-weight: 700; text-transform: uppercase; margin-bottom: 6px;
        }
        .badge-green { background: #10b981; color: #ffffff; }
        .badge-yellow { background: #f59e0b; color: #ffffff; }
        .badge-red { background: #ef4444; color: #ffffff; }
        .badge-insufficient { background: #64748b; color: #ffffff; }
        .profit-card {
            background: var(--secondary-background-color); border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 10px; padding: 12px 14px; text-align: left;
        }
        .profit-card-label { font-size: 0.78rem; text-transform: uppercase; opacity: 0.75; margin-bottom: 4px; font-weight: 600; }
        .profit-card-value { font-size: 1.3rem; font-weight: 700; font-family: "SF Mono", Consolas, monospace; }
        .profit-card-sub { font-size: 0.78rem; opacity: 0.7; margin-top: 3px; font-family: "SF Mono", Consolas, monospace; }
        .kpi-mini-card { background: var(--secondary-background-color); border: 1px solid rgba(148, 163, 184, 0.15); border-radius: 8px; padding: 10px 12px; }
        .kpi-mini-label { font-size: 0.75rem; opacity: 0.7; text-transform: uppercase; margin-bottom: 3px; }
        .kpi-mini-val { font-size: 1.1rem; font-weight: 700; font-family: "SF Mono", Consolas, monospace; }
        .section-header { font-size: 0.92rem; font-weight: 700; text-transform: uppercase; margin: 16px 0 8px 0; opacity: 0.9; }
        div.stButton > button { border-radius: 8px; font-weight: 500; border: 1px solid rgba(148, 163, 184, 0.3); }
        </style>
        """,
        unsafe_allow_html=True,
    )
