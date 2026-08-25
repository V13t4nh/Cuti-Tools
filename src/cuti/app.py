"""Modern Streamlit decision dashboard for watch arbitrage buyers."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

# Ensure src/ is on sys.path for direct streamlit execution
_SRC_ROOT = str(Path(__file__).resolve().parents[1])
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from cuti.charts import hammer_histogram, price_position
from cuti.comparables import find_comparables
from cuti.config import load_settings
from cuti.errors import CutiError
from cuti.evaluation import DealEvaluation
from cuti.evaluation_chart import BuyerEvaluation, ComparisonChartData, evaluate_deal_with_chart
from cuti.models import Condition, WatchForm
from cuti.normalize import load_rules
from cuti.storage import connect, count_rows

CONDITIONS = tuple(item.value for item in Condition)
FORMS = tuple(item.value for item in WatchForm if item is not WatchForm.UNKNOWN)
CURRENCIES = ("vnd", "eur")

PRESETS = {
    "Seiko Presage SRPB41": {"query": "Seiko Presage SRPB41", "cost": 6200000.0, "cond": "fullset", "form": "round"},
    "Omega Seamaster 210.30.42": {"query": "Omega Seamaster Diver 300M 210.30.42", "cost": 28000000.0, "cond": "fullset", "form": "round"},
    "Citizen Tsuyosa NJ0150": {"query": "Citizen Tsuyosa NJ0150", "cost": 4500000.0, "cond": "fullset", "form": "round"},
    "Rolex Datejust 126234": {"query": "Rolex Datejust 126234", "cost": 180000000.0, "cond": "fullset", "form": "round"},
}


def _money(value: float | None) -> str:
    return "—" if value is None else f"{value:,.2f} EUR"


def _rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _money_days(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} ngày"


def _render_result(result: DealEvaluation, st_ctx: Any) -> None:
    verdict = result.verdict.value
    st_ctx.subheader("Bước 3 — Kết quả quyết định")
    renderer = {"green": st_ctx.success, "yellow": st_ctx.warning, "red": st_ctx.error, "insufficient_data": st_ctx.info}.get(verdict, st_ctx.info)
    renderer(f"Verdict: {verdict}")
    if result.max_buy_cost_vnd is not None:
        st_ctx.metric("Giá nhập tối đa (VNĐ)", result.max_buy_cost_vnd)
    st_ctx.metric("Số mẫu so sánh", result.sample_size)
    st_ctx.metric("Tỷ lệ bán (sell-through)", _rate(result.sell_through_rate))
    st_ctx.metric("Ngày trung bình để chốt", _money_days(result.median_days_to_close))
    st_ctx.metric("Chuyển đổi tim → hammer", _rate(result.heart_to_hammer_rate))
    if verdict == "insufficient_data":
        st_ctx.info("insufficient_data — chưa đủ mẫu so sánh để tính Net Profit.")
    else:
        columns = st_ctx.columns(3)
        columns[0].metric("Net Profit p25", _money(result.net_p25_eur))
        columns[1].metric("Net Profit median", _money(result.net_median_eur))
        columns[2].metric("Net Profit p75", _money(result.net_p75_eur))
    st_ctx.caption(f"Lý do: {result.reason}")


def _render_liquidity_series(chart: ComparisonChartData, st_ctx: Any) -> None:
    series = chart.liquidity_series
    if series is None:
        return
    st_ctx.subheader("Thanh khoản theo thời gian")
    st_ctx.bar_chart(tuple(window.sell_through_rate for window in series))
    latest = series[-1]
    st_ctx.metric("Sell-through gần nhất", latest.sell_through_rate)
    if latest.heart_to_hammer_rate is not None:
        st_ctx.metric("Heart → hammer gần nhất", latest.heart_to_hammer_rate)
    if latest.median_days_to_close is not None:
        st_ctx.metric("Median days to close gần nhất", latest.median_days_to_close)
    st_ctx.metric("Sample size gần nhất", latest.sample_size)


def _render_distribution(chart: ComparisonChartData, st_ctx: Any) -> None:
    if chart.input_hammer_eur is not None:
        values = list(chart.hammer_prices_eur)
        position = price_position(chart.input_hammer_eur, values)
        if position is not None:
            histogram = hammer_histogram(values, bins=8)
            st_ctx.subheader("Phân phối hammer price")
            st_ctx.bar_chart(histogram.counts)
            st_ctx.metric("Vị trí giá hoà vốn trong pool", f"{position:.0%}")
    if chart.cycle_position is not None:
        st_ctx.metric("Vị trí chu kỳ", f"{chart.cycle_position:.0%}")
    if chart.heart_acceleration_rate is not None:
        st_ctx.metric("Gia tốc tim", f"{chart.heart_acceleration_rate:+.1%}")
    _render_liquidity_series(chart, st_ctx)


def _render_buyer_evaluation(result: BuyerEvaluation, st_ctx: Any) -> None:
    _render_result(result.decision, st_ctx)
    if result.decision.verdict.value != "insufficient_data":
        _render_distribution(result.chart, st_ctx)


def _render_evaluation_screen(conn: object, rules: object, settings: object, today: date, st_ui: Any) -> None:
    from cuti.ui_views import (
        render_comparables_table,
        render_kpi_grid,
        render_plotly_distribution,
        render_profit_grid,
        render_verdict_hero,
    )

    col_left, col_right = st_ui.columns([1, 1.35], gap="large")

    with col_left:
        st_ui.markdown("#### 📝 Thông Tin Deal Cần Đánh Giá")
        st_ui.caption("Chọn mẫu nhanh hoặc tự nhập thông tin từ bài rao bán:")

        preset_cols = st_ui.columns(len(PRESETS))
        selected_preset = None
        for idx, (label, data) in enumerate(PRESETS.items()):
            short_name = label.split()[0] + " " + label.split()[1]
            if preset_cols[idx].button(f"⌚ {short_name}", key=f"preset_{idx}", use_container_width=True):
                selected_preset = data

        default_query = selected_preset["query"] if selected_preset else "Seiko Presage SRPB41"
        default_cost = selected_preset["cost"] if selected_preset else 6200000.0
        default_cond = selected_preset["cond"] if selected_preset else "fullset"
        default_form = selected_preset["form"] if selected_preset else "round"

        with st_ui.form("evaluate-deal-form"):
            query = st_ui.text_input("Tên / Mã Đồng Hồ (Model / Reference):", value=default_query)
            c1, c2 = st_ui.columns([1.5, 1])
            with c1:
                amount = st_ui.number_input("Giá Người Bán Rao:", min_value=0.0, value=default_cost, step=500000.0)
            with c2:
                currency = st_ui.selectbox("Đơn Vị Tiền:", options=CURRENCIES, index=0)

            c3, c4 = st_ui.columns(2)
            with c3:
                condition_str = st_ui.selectbox("Tình Trạng Phụ Kiện:", options=CONDITIONS, index=CONDITIONS.index(default_cond) if default_cond in CONDITIONS else 0)
            with c4:
                form_str = st_ui.selectbox("Hình Dạng Vỏ (Form):", options=FORMS, index=FORMS.index(default_form) if default_form in FORMS else 0)

            submitted = st_ui.form_submit_button("⚡ ĐÁNH GIÁ DEAL NGAY", type="primary", use_container_width=True)

    with col_right:
        st_ui.markdown("#### 🎯 Kết Quả Thẩm Định & Phân Tích")
        if not submitted and not selected_preset:
            st_ui.info("👈 Hãy nhập thông tin deal hoặc bấm chọn mẫu nhanh bên trái để bắt đầu thẩm định.")
            return

        cond_obj = Condition.parse(condition_str)
        result = evaluate_deal_with_chart(
            conn,
            rules,
            settings,
            query=query,
            cost=amount,
            currency=currency,
            condition=cond_obj,
            today=today,
        )

        render_verdict_hero(result.decision, settings)
        render_profit_grid(result.decision, settings)
        render_kpi_grid(result.decision)
        render_plotly_distribution(result.chart, settings)

        matches = find_comparables(conn, title=query, condition=cond_obj, rules=rules, settings=settings, today=today)
        render_comparables_table(matches, settings)


def main() -> None:
    import streamlit as st
    from cuti.ui_tabs import render_liquidity_leaderboard, render_live_lots_tab
    from cuti.ui_theme import inject_custom_css

    st.set_page_config(page_title="CUTI-Tools — Thẩm Định Đồng Hồ", page_icon="⌚", layout="wide")
    inject_custom_css()

    st.title("⌚ CUTI-Tools — Định Giá & Quyết Định Mua Đồng Hồ")
    today = date.today()

    try:
        settings = load_settings()
        rules = load_rules(settings.rules_path)
        with connect(settings.db_path) as conn:
            lots_count = count_rows(conn, "lots")
            queue_count = count_rows(conn, "live_watch")

            st.markdown(
                f"""
                <div style="margin-bottom: 12px; font-size: 0.88rem; opacity: 0.85; display: flex; gap: 20px;">
                    <span>📚 <b>Kho Dữ Liệu:</b> {lots_count:,} lô đã bán</span>
                    <span>📡 <b>Hàng Đợi Sàn:</b> {queue_count:,} lô đang theo dõi</span>
                    <span>💱 <b>Tỷ Giá:</b> 1 EUR = {settings.eur_vnd_rate:,.0f} VNĐ</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            tab1, tab2, tab3 = st.tabs(["🔍 Thẩm Định Deal", "📊 Xếp Hạng Thanh Khoản", "📡 Lô Đang Đấu Giá"])
            with tab1:
                _render_evaluation_screen(conn, rules, settings, today, st)
            with tab2:
                render_liquidity_leaderboard(conn, rules, settings, today)
            with tab3:
                render_live_lots_tab(conn)
    except CutiError as exc:
        st.error(f"Lỗi: {exc}")


if __name__ == "__main__":
    main()
