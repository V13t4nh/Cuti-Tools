"""Visual views and components for Streamlit Watch Decision Dashboard."""

from __future__ import annotations

from .comparables import ScoredLot
from .config import Settings
from .evaluation import DealEvaluation
from .evaluation_chart import ComparisonChartData
from .models import Verdict
from .ui_theme import format_days, format_eur, format_rate, format_vnd


def render_verdict_hero(decision: DealEvaluation, settings: Settings) -> None:
    """Render a bold, modern decision hero banner with clear recommendation."""
    import streamlit as st

    verdict = decision.verdict
    if verdict == Verdict.GREEN:
        css_class, icon = "verdict-green", "🟢"
        title = "NÊN MUA NGAY (RECOMMENDED DEAL)"
        desc = "Mức giá nhập này đảm bảo lợi nhuận ròng an toàn (p25) vượt ngưỡng mục tiêu."
    elif verdict == Verdict.YELLOW:
        css_class, icon = "verdict-yellow", "🟡"
        title = "CÂN NHẮC RỦI RO (MARGINAL DEAL)"
        desc = "Deal có lãi nhưng biên lợi nhuận mỏng hoặc biến động giá quá khứ cao."
    elif verdict == Verdict.RED:
        css_class, icon = "verdict-red", "🔴"
        title = "KHÔNG NÊN MUA (HIGH RISK / OVERPRICED)"
        desc = "Giá rao bán quá cao so với lịch sử giá búa thực tế, nguy cơ lỗ vốn cao."
    else:
        css_class, icon = "verdict-insufficient", "⚪"
        title = "CHƯA ĐỦ DỮ LIỆU (INSUFFICIENT COMPARABLES)"
        desc = f"Chưa đủ tối thiểu {settings.min_comparables} mẫu giao dịch cùng mã trong quá khứ."

    max_cost_str = format_vnd(decision.max_buy_cost_vnd) if decision.max_buy_cost_vnd else "—"

    st.markdown(
        f"""
        <div class="verdict-banner {css_class}">
            <div>
                <div style="font-size: 1.2rem; font-weight: 700; display: flex; align-items: center; gap: 8px;">
                    <span>{icon}</span> {title}
                </div>
                <div style="font-size: 0.88rem; opacity: 0.92; margin-top: 5px;">
                    {desc}
                </div>
            </div>
            <div style="text-align: right; min-width: 170px;">
                <div style="font-size: 0.78rem; opacity: 0.85; text-transform: uppercase;">Giá Trần Khuyên Mua</div>
                <div style="font-size: 1.35rem; font-weight: 800;">{max_cost_str}</div>
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

    rate = settings.eur_vnd_rate
    cols = st.columns(3)
    p25_eur, med_eur, p75_eur = decision.net_p25_eur, decision.net_median_eur, decision.net_p75_eur
    p25_vnd = p25_eur * rate if p25_eur is not None else None
    med_vnd = med_eur * rate if med_eur is not None else None
    p75_vnd = p75_eur * rate if p75_eur is not None else None

    with cols[0]:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-title">🛡️ Lãi Ròng An Toàn (p25)</div>
                <div class="metric-value" style="color: #10b981;">{format_vnd(p25_vnd)}</div>
                <div class="metric-sub">{format_eur(p25_eur)} (25% thấp nhất)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[1]:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-title">🎯 Lãi Ròng Kỳ Vọng (Median)</div>
                <div class="metric-value">{format_vnd(med_vnd)}</div>
                <div class="metric-sub">{format_eur(med_eur)} (Mức trung vị)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[2]:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-title">🚀 Lãi Ròng Tối Ưu (p75)</div>
                <div class="metric-value">{format_vnd(p75_vnd)}</div>
                <div class="metric-sub">{format_eur(p75_eur)} (25% cao nhất)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_kpi_grid(decision: DealEvaluation) -> None:
    """Render 4 core liquidity and market response KPIs."""
    import streamlit as st

    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]:
        st.metric("📦 Số Mẫu Đã Bán", f"{decision.sample_size} lô")
    with cols[1]:
        st.metric("📈 Tỷ Lệ Bán Được", format_rate(decision.sell_through_rate))
    with cols[2]:
        st.metric("⏱️ Thời Gian Bán", format_days(decision.median_days_to_close))
    with cols[3]:
        st.metric("❤️ Tim → Búa", format_rate(decision.heart_to_hammer_rate))


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
            marker=dict(color="rgba(59, 130, 246, 0.75)", line=dict(color="rgba(29, 78, 216, 1)", width=1.2)),
            hovertemplate="Giá búa: %{x:,.0f} €<br>Số lượng: %{y} lô<extra></extra>",
            name="Lô đã bán",
        )
    )

    if chart.input_hammer_eur is not None:
        be_eur = chart.input_hammer_eur
        be_vnd = format_vnd(be_eur * settings.eur_vnd_rate)
        fig.add_vline(
            x=be_eur,
            line_width=2.5,
            line_dash="dash",
            line_color="#ef4444",
            annotation_text=f"Hòa vốn: {be_eur:,.0f} € ({be_vnd})",
            annotation_position="top left",
            annotation_font=dict(color="#ef4444", size=11),
        )

    fig.update_layout(
        title="📊 Phân phối Giá búa Lịch sử (€) & Vạch Hòa Vốn",
        xaxis_title="Giá búa (EUR)",
        yaxis_title="Số lượng lô",
        template="plotly_white",
        height=300,
        margin=dict(l=15, r=15, t=35, b=15),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_comparables_table(matches: list[ScoredLot], settings: Settings) -> None:
    """Render a clean interactive table of historical comparable lots."""
    if not matches:
        return

    import pandas as pd
    import streamlit as st

    rate = settings.eur_vnd_rate
    records = [
        {
            "Tiêu đề": item.lot.title,
            "Giá Búa (€)": f"{item.lot.hammer_eur:,.0f} €" if item.lot.hammer_eur else "Chưa bán",
            "Quy Đổi (VNĐ)": format_vnd(item.lot.hammer_eur * rate) if item.lot.hammer_eur else "—",
            "Độ Khớp": f"{item.score:.0%}",
            "Số Tim": item.lot.hearts,
            "Lượt Bid": item.lot.bids_count if item.lot.bids_count is not None else "—",
            "Ngày Bán": str(item.lot.ended_at),
        }
        for item in matches
    ]
    st.markdown("### 📋 Lịch Sử Các Lô Tương Đồng Đã Bán Trên Sàn")
    st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
