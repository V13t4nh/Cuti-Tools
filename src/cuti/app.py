"""Single-page Streamlit buyer dashboard."""

from __future__ import annotations

from datetime import datetime, timezone

from cuti.config import BUSINESS_TIMEZONE, load_settings
from cuti.errors import CutiError
from cuti.liquidity import compute_liquidity
from cuti.models import Condition, Verdict, WatchForm
from cuti.normalize import load_rules
from cuti.pipeline import quote_watch
from cuti.storage import connect


VERDICT_LABELS = {
    Verdict.GREEN: "XANH — đạt ngưỡng lợi nhuận ở kịch bản p25",
    Verdict.YELLOW: "VÀNG — chỉ đạt ngưỡng ở kịch bản median",
    Verdict.RED: "ĐỎ — không đạt ngưỡng lợi nhuận",
    Verdict.INSUFFICIENT_DATA: "DỮ LIỆU MỎNG — chưa khuyến nghị",
}


def _money(value: float | None) -> str:
    return "—" if value is None else f"{value:,.0f} EUR"


def _render_quote(conn, report, settings, today, st) -> None:
    from cuti.charts import (
        brand_lots,
        heart_acceleration,
        model_lots,
        price_histogram,
        quarterly_median,
    )

    price = report.price
    verdict_renderer = {
        Verdict.GREEN: st.success,
        Verdict.YELLOW: st.warning,
        Verdict.RED: st.error,
        Verdict.INSUFFICIENT_DATA: st.info,
    }[price.verdict]
    verdict_renderer(VERDICT_LABELS[price.verdict])
    columns = st.columns(4)
    columns[0].metric("Net p25", _money(price.net_p25_eur))
    columns[1].metric("Net median", _money(price.net_median_eur))
    columns[2].metric("Ngưỡng lãi", _money(price.threshold_eur))
    columns[3].metric("Sold / attempts", f"{price.sample_size} / {price.attempt_count}")
    st.caption(
        f"Sell-through {price.sell_through_rate:.0%} · median chốt "
        f"{'—' if price.median_days_to_close is None else f'{price.median_days_to_close:,.1f} ngày'} · "
        f"hammer hòa vốn {_money(price.break_even_hammer_eur)} · audit #{report.quote_id}"
    )
    if report.comparable_titles:
        with st.expander("Comparables đã dùng"):
            for title in report.comparable_titles:
                st.write(f"- {title}")

    lots = model_lots(
        conn,
        model_key=report.model_key,
        condition=report.condition,
        settings=settings,
        today=today,
    )
    left, right = st.columns(2)
    left.plotly_chart(price_histogram(lots, price.cost_eur), width="stretch")
    right.plotly_chart(quarterly_median(lots), width="stretch")
    st.plotly_chart(
        heart_acceleration(
            brand_lots(
                conn,
                brand=report.model_key.partition(":")[0],
                settings=settings,
                today=today,
            )
        ),
        width="stretch",
    )


def _render_liquidity(conn, settings, today, st) -> None:
    report = compute_liquidity(conn, settings, today)
    st.header("Thanh khoản theo brand + form")
    if not report.brands:
        st.info("Chưa có nhóm nào đủ số lot tối thiểu để xếp hạng.")
        return
    st.dataframe(
        [
            {
                "Brand": item.brand,
                "Form": item.form.value,
                "Lots": item.lots,
                "Sold": item.sold,
                "Sell-through": f"{item.sell_through:.0%}",
                "Median days": item.median_days_to_close,
                "Liquidity": round(item.index, 3),
                "QoQ": "—" if item.latest_qoq_change is None else f"{item.latest_qoq_change:+.0%}",
                "Khuyến nghị": "NGỪNG NHẬP" if item.stop_buying else "Theo dõi",
            }
            for item in report.brands
        ],
        width="stretch",
        hide_index=True,
    )
    stopped = [f"{item.brand}/{item.form.value}" for item in report.brands if item.stop_buying]
    if stopped:
        st.error("Giảm trên ngưỡng trong 2 quý liên tiếp: " + ", ".join(stopped))


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="CUTI-Tools", page_icon="⌚", layout="wide")
    st.title("CUTI-Tools — Watch Arbitrage")
    st.caption("Một công thức pricing dùng chung cho form buyer và bot săn deal.")
    try:
        settings = load_settings()
        rules = load_rules(settings.rules_path)
        now = datetime.now(timezone.utc)
        today = now.astimezone(BUSINESS_TIMEZONE).date()
        with connect(settings.db_path) as conn:
            with st.form("quote-form"):
                title = st.text_input("Tên / reference đồng hồ")
                cost_vnd = st.number_input(
                    "Giá nhập (VND)", min_value=1, value=10_000_000, step=100_000
                )
                condition = st.selectbox(
                    "Tình trạng",
                    options=list(Condition),
                    index=None,
                    placeholder="Chọn tình trạng",
                    format_func=lambda item: item.value,
                )
                form = st.selectbox(
                    "Form vỏ",
                    options=list(WatchForm),
                    index=None,
                    placeholder="Chọn form vỏ",
                    format_func=lambda item: item.value,
                )
                submitted = st.form_submit_button("Chấm deal", type="primary")
            if submitted:
                if condition is None or form is None:
                    st.error("Hãy chọn rõ tình trạng và form vỏ trước khi chấm deal.")
                else:
                    report = quote_watch(
                        conn,
                        rules,
                        settings,
                        title=title,
                        cost_vnd=int(cost_vnd),
                        condition=condition,
                        form=form,
                        today=today,
                        now=now,
                    )
                    _render_quote(conn, report, settings, today, st)
            _render_liquidity(conn, settings, today, st)
    except CutiError as exc:
        st.error(str(exc))


if __name__ == "__main__":
    main()
