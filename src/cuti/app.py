"""Single-page Streamlit decision screen for buyers.

The optional UI layer is deliberately thin: ``evaluate_deal`` owns every
pricing, comparable and liquidity decision. This module only collects input,
converts the buyer's currency, and renders the typed result.
"""

from __future__ import annotations

from typing import Any

from cuti.config import load_settings
from cuti.errors import CutiError
from cuti.evaluation import DealEvaluation, cost_to_eur, evaluate_deal
from cuti.models import Condition
from cuti.normalize import load_rules
from cuti.storage import connect


CONDITIONS = tuple(item.value for item in Condition)
CURRENCIES = ("vnd", "eur")


def _money(value: float | None) -> str:
    return "—" if value is None else f"{value:,.2f} EUR"


def _rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _render_result(result: DealEvaluation, st: Any) -> None:
    verdict = result.verdict.value
    st.subheader("Bước 3 — Kết quả quyết định")
    renderer = {
        "green": st.success,
        "yellow": st.warning,
        "red": st.error,
        "insufficient_data": st.info,
    }.get(verdict, st.info)
    renderer(f"Verdict: {verdict}")

    st.metric("Số mẫu so sánh", result.sample_size)
    st.metric("Tỷ lệ bán (sell-through)", _rate(result.sell_through_rate))
    st.metric("Ngày trung bình để chốt", _money_days(result.median_days_to_close))
    st.metric(
        "Chuyển đổi tim → hammer",
        _rate(result.heart_to_hammer_rate),
    )
    if verdict == "insufficient_data":
        st.info("insufficient_data — chưa đủ mẫu so sánh để tính Net Profit.")
    else:
        columns = st.columns(3)
        columns[0].metric("Net Profit p25", _money(result.net_p25_eur))
        columns[1].metric("Net Profit median", _money(result.net_median_eur))
        columns[2].metric("Net Profit p75", _money(result.net_p75_eur))
    st.caption(f"Lý do: {result.reason}")


def _money_days(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} ngày"


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="CUTI-Tools Buyer", page_icon="⌚", layout="wide")
    st.title("CUTI-Tools — Quyết định mua đồng hồ")
    st.caption("Tra lịch sử cùng mã và cụm tình trạng để chấm một deal.")
    try:
        settings = load_settings()
        rules = load_rules(settings.rules_path)
        with connect(settings.db_path) as conn:
            st.subheader("Bước 1 — Nhập deal")
            with st.form("evaluate-deal"):
                query = st.text_input("Mã / tên đồng hồ")
                currency = st.selectbox("Đơn vị giá nhập", options=CURRENCIES)
                amount = st.number_input(
                    "Giá nhập", min_value=0.0, value=0.0, step=1000.0
                )
                condition = st.selectbox(
                    "Tình trạng", options=CONDITIONS, format_func=str
                )
                submitted = st.form_submit_button("Đánh giá deal", type="primary")
            if not submitted:
                return
            st.subheader("Bước 2 — Tra lịch sử đã bán")
            result = evaluate_deal(
                conn,
                rules,
                settings,
                query=query,
                cost_eur=cost_to_eur(amount, currency, settings),
                condition=Condition.parse(condition),
            )
            _render_result(result, st)
    except CutiError as exc:
        st.error(str(exc))


if __name__ == "__main__":
    main()
