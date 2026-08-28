"""Visual views and components for Streamlit Watch Decision Dashboard."""

from __future__ import annotations

from .comparables import ScoredLot
from .config import Settings
from .evaluation import DealEvaluation
from .evaluation_chart import ComparisonChartData
from .models import Verdict
from .pricing import pricing_value
from .ui_theme import format_days, format_eur, format_rate, format_vnd


def render_verdict_hero(decision: DealEvaluation, settings: Settings) -> None:
    """Render a bold, modern decision hero banner with clear recommendation."""
    import streamlit as st

    verdict = decision.verdict
    if verdict == Verdict.GREEN:
        css_style, badge_cls, tag, title = "verdict-hero-green", "badge-green", "● KHUYÊN MUA", "MỨC GIÁ NHẬP RẤT TỐT"
        desc = "Giá nhập này đảm bảo lợi nhuận ròng an toàn (p25) vượt ngưỡng mục tiêu đề ra."
    elif verdict == Verdict.YELLOW:
        css_style, badge_cls, tag, title = "verdict-hero-yellow", "badge-yellow", "▲ CÂN NHẮC RỦI RO", "BIÊN LỢI NHUẬN MỎNG"
        desc = "Deal có lãi theo trung vị thị trường nhưng biên độ an toàn p25 chưa đạt chuẩn."
    elif verdict == Verdict.RED:
        css_style, badge_cls, tag, title = "verdict-hero-red", "badge-red", "✕ KHÔNG NÊN MUA", "GIÁ RAO QUÁ CAO"
        desc = "Mức giá người bán đưa ra cao hơn vùng giá búa khả thi, rủi ro chôn vốn hoặc lỗ."
    else:
        css_style, badge_cls, tag, title = "verdict-hero-insufficient", "badge-insufficient", "○ CHƯA ĐỦ DỮ LIỆU", "CẦN THÊM MẪU SO SÁNH"
        desc = f"Chưa đủ tối thiểu {settings.min_comparables} giao dịch cùng model trong 24 tháng gần nhất."

    max_cost_str = format_vnd(decision.max_buy_cost_vnd) if decision.max_buy_cost_vnd else "—"

    st.markdown(
        f"""
        <div class="verdict-hero {css_style}">
            <div>
                <span class="verdict-badge {badge_cls}">{tag}</span>
                <div style="font-size: 1.15rem; font-weight: 700; margin-top: 2px;">{title}</div>
                <div style="font-size: 0.85rem; opacity: 0.85; margin-top: 4px; max-width: 480px;">{desc}</div>
            </div>
            <div style="text-align: right; min-width: 180px; padding-left: 16px; border-left: 1px solid rgba(148,163,184,0.2);">
                <div style="font-size: 0.75rem; opacity: 0.75; text-transform: uppercase; letter-spacing: 0.05em;">Giá Trần Khuyên Mua</div>
                <div class="mono-num" style="font-size: 1.4rem; font-weight: 800; color: #0284c7; margin-top: 2px;">{max_cost_str}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_profit_grid(decision: DealEvaluation, settings: Settings) -> None:
    """Render 3 cards showing safe p25, median, and p75 net profits."""
    if decision.verdict == Verdict.INSUFFICIENT_DATA:
        return

    import streamlit as st

    rate = pricing_value(settings, "eur_vnd_rate")
    cols = st.columns(3)
    p25_eur, med_eur, p75_eur = decision.net_p25_eur, decision.net_median_eur, decision.net_p75_eur
    cards = (
        ("🛡️ Lãi Ròng An Toàn (p25)", p25_eur, "#10b981", "Kịch bản thận trọng"),
        ("🎯 Lãi Ròng Kỳ Vọng (Median)", med_eur, "#3b82f6", "Mức trung vị thị trường"),
        ("🚀 Lãi Ròng Tối Ưu (p75)", p75_eur, "#8b5cf6", "Kịch bản thanh khoản tốt"),
    )
    for idx, (label, eur_val, color, sub_note) in enumerate(cards):
        vnd_str = format_vnd(eur_val * rate) if eur_val is not None else "—"
        with cols[idx]:
            st.markdown(
                f"""
                <div class="profit-card" style="border-top: 3px solid {color};">
                    <div class="profit-card-label">{label}</div>
                    <div class="profit-card-value" style="color: {color};">{vnd_str}</div>
                    <div class="profit-card-sub">{format_eur(eur_val)} • {sub_note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_kpi_grid(decision: DealEvaluation) -> None:
    """Render core liquidity and market response KPIs."""
    import streamlit as st

    cols = st.columns(4)
    items = (
        ("Mẫu Đã Khớp", f"{decision.sample_size} lô", None),
        ("Tỷ Lệ Bán", format_rate(decision.sell_through_rate), "#0284c7"),
        ("Chu Kỳ Thoát Hàng", format_days(decision.median_days_to_close), None),
        ("Chuyển Đổi Quan Tâm", format_rate(decision.heart_to_hammer_rate), None),
    )
    for col, (label, val, color) in zip(cols, items):
        color_style = f" style='color: {color};'" if color else ""
        with col:
            st.markdown(
                f"<div class='kpi-mini-card'><div class='kpi-mini-label'>{label}</div><div class='kpi-mini-val'{color_style}>{val}</div></div>",
                unsafe_allow_html=True,
            )


def render_plotly_distribution(chart: ComparisonChartData, settings: Settings) -> None:
    """Render an interactive Plotly histogram showing hammer price distribution and break-even line."""
    if not chart.hammer_prices_eur:
        return

    import plotly.graph_objects as go
    import streamlit as st

    values = list(chart.hammer_prices_eur)
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=values,
            nbinsx=8,
            marker=dict(color="rgba(59, 130, 246, 0.7)", line=dict(color="rgba(37, 99, 235, 1)", width=1.5)),
            hovertemplate="<b>Vùng giá: %{x:,.0f} €</b><br>Số lô khớp: %{y}<extra></extra>",
            name="Lô đã bán",
        )
    )
    if chart.input_hammer_eur is not None:
        be_eur = chart.input_hammer_eur
        be_vnd = format_vnd(be_eur * pricing_value(settings, "eur_vnd_rate"))
        fig.add_vline(
            x=be_eur,
            line_width=2.5,
            line_dash="dash",
            line_color="#ef4444",
            annotation_text=f"Giá búa hòa vốn: {be_eur:,.0f} € ({be_vnd})",
            annotation_position="top left",
            annotation_font=dict(color="#dc2626", size=11),
        )
    fig.update_layout(
        title=dict(text="Phân Bố Giá Búa Lịch Sử & Ngưỡng Hòa Vốn", font=dict(size=14)),
        xaxis_title="Giá búa (EUR)",
        yaxis_title="Số lượng lô",
        template="plotly_white",
        height=260,
        margin=dict(l=10, r=10, t=35, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_comparables_table(matches: list[ScoredLot], settings: Settings) -> None:
    """Render a clean interactive table of historical comparable lots."""
    if not matches:
        return

    import pandas as pd
    import streamlit as st

    rate = pricing_value(settings, "eur_vnd_rate")
    records = [
        {
            "Tiêu Đề / Phiên Đấu": item.lot.title,
            "Giá Búa": f"{item.lot.hammer_eur:,.0f} €" if item.lot.hammer_eur else "Chưa bán",
            "Quy Đổi (VNĐ)": format_vnd(item.lot.hammer_eur * rate) if item.lot.hammer_eur else "—",
            "Độ Khớp": item.score,
            "Lượt Thích": item.lot.hearts,
            "Số Bid": item.lot.bids_count if item.lot.bids_count is not None else "—",
            "Ngày Chốt": str(item.lot.ended_at),
        }
        for item in matches
    ]
    st.markdown("<div class='section-header'>📋 Lịch Sử Giao Dịch Tương Đồng Thực Tế</div>", unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(records),
        column_config={
            "Độ Khớp": st.column_config.ProgressColumn("Độ Khớp", format="%.0f%%", min_value=0.0, max_value=1.0),
        },
        use_container_width=True,
        hide_index=True,
    )
