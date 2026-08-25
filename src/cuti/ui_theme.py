"""UI Theme, styling constants, custom CSS and formatters for Streamlit."""

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
    """Inject custom modern CSS for cards, badges, and typography."""
    import streamlit as st

    st.markdown(
        """
        <style>
        /* Card container */
        .cuti-card {
            background-color: var(--secondary-background-color);
            border-radius: 12px;
            padding: 18px 22px;
            border: 1px solid rgba(128, 128, 128, 0.18);
            margin-bottom: 16px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        }
        
        /* Hero verdict banner */
        .verdict-banner {
            border-radius: 12px;
            padding: 20px 24px;
            color: #ffffff !important;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .verdict-green {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        }
        .verdict-yellow {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        }
        .verdict-red {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        }
        .verdict-insufficient {
            background: linear-gradient(135deg, #64748b 0%, #475569 100%);
        }
        
        /* Metric card */
        .metric-box {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.15);
            border-radius: 10px;
            padding: 14px 16px;
            text-align: center;
        }
        .metric-title {
            font-size: 0.85rem;
            color: var(--text-color);
            opacity: 0.8;
            margin-bottom: 4px;
            font-weight: 500;
        }
        .metric-value {
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--text-color);
        }
        .metric-sub {
            font-size: 0.78rem;
            opacity: 0.7;
            margin-top: 2px;
        }
        
        /* Status badge */
        .status-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
