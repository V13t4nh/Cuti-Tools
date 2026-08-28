"""Tab views for Brand Liquidity and Live Auctions Feed."""

from __future__ import annotations

import sqlite3
from datetime import date

from .config import Settings
from .liquidity import compute_liquidity
from .normalize import Rules


def render_liquidity_leaderboard(
    conn: sqlite3.Connection, rules: Rules, settings: Settings, today: date
) -> None:
    """Render Brand Liquidity Leaderboard tab."""
    import pandas as pd
    import streamlit as st

    index = compute_liquidity(conn, settings, today)
    if not index.brands:
        st.info("Chưa có đủ dữ liệu lịch sử để xếp hạng thanh khoản.")
        return

    col1, col2, col3 = st.columns(3)
    top_brand = index.brands[0]
    total_lots = sum(b.lots for b in index.brands)
    avg_sell_through = sum(b.sell_through * b.lots for b in index.brands) / total_lots if total_lots else 0.0

    with col1:
        st.metric("🏆 Thương Hiệu Dẫn Đầu", f"{top_brand.brand.upper()} ({top_brand.index:.1%})")
    with col2:
        st.metric("📦 Tổng Số Lô Phân Tích", f"{total_lots:,} lô")
    with col3:
        st.metric("📈 Tỷ Lệ Bán Toàn Thị Trường", f"{avg_sell_through:.1%}")

    search_query = st.text_input("🔍 Tìm thương hiệu:", placeholder="Nhập tên hãng (Rolex, Omega, Seiko...)...")

    filtered_brands = index.brands
    if search_query.strip():
        q = search_query.strip().lower()
        filtered_brands = [b for b in filtered_brands if q in b.brand.lower()]

    records = [
        {
            "Thương Hiệu": g.brand.upper(),
            "Dáng Vỏ": g.form.capitalize(),
            "Điểm Thanh Khoản": g.index,
            "Tỷ Lệ Bán": g.sell_through,
            "Chuyển Đổi Tim": f"{g.heart_to_hammer:.1%}",
            "Ngày Chốt TB": f"{g.median_days_to_close:.0f} ngày",
            "Số Lô": g.lots,
            "Trạng Thái": g.status.upper() if g.status else "ỔN ĐỊNH",
        }
        for g in filtered_brands
    ]

    st.markdown("<div class='section-header'>📊 Bảng Xếp Hạng Thanh Khoản Chi Tiết (24 Tháng)</div>", unsafe_allow_html=True)
    df = pd.DataFrame(records)
    st.dataframe(
        df,
        column_config={
            "Điểm Thanh Khoản": st.column_config.ProgressColumn(
                "Điểm Thanh Khoản",
                format="%.1f%%",
                min_value=0.0,
                max_value=1.0,
            ),
            "Tỷ Lệ Bán": st.column_config.ProgressColumn(
                "Tỷ Lệ Bán",
                format="%.1f%%",
                min_value=0.0,
                max_value=1.0,
            ),
        },
        use_container_width=True,
        hide_index=True,
    )


def render_live_lots_tab(conn: sqlite3.Connection) -> None:
    """Render live auctions feed tab."""
    import pandas as pd
    import streamlit as st

    cursor = conn.execute(
        "SELECT lot_id, title, bidding_end_at, url FROM live_watch ORDER BY bidding_end_at ASC LIMIT 100"
    )
    rows = cursor.fetchall()
    if not rows:
        st.info("Hàng đợi lô đang mở hiện tại đang trống.")
        return

    filter_text = st.text_input("🔍 Lọc danh sách lô đang đấu:", placeholder="Lọc theo tên đồng hồ hoặc mã...")

    filtered_rows = rows
    if filter_text.strip():
        ft = filter_text.strip().lower()
        filtered_rows = [r for r in rows if ft in r["title"].lower() or ft in r["lot_id"].lower()]

    records = [
        {
            "Mã Lô": r["lot_id"],
            "Tiêu Đề Đồng Hồ": r["title"],
            "Hạn Đóng Phiên": r["bidding_end_at"],
            "Link Catawiki": r["url"],
        }
        for r in filtered_rows
    ]
    st.markdown(
        f"<div class='section-header'>📡 Danh Sách Lô Sắp Kết Thúc Sớm Nhất ({len(filtered_rows)}/{len(rows)} lô hiển thị)</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(
        pd.DataFrame(records),
        column_config={"Link Catawiki": st.column_config.LinkColumn("Xem Lô Gốc")},
        use_container_width=True,
        hide_index=True,
    )
