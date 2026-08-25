"""Tab views for Brand Liquidity and Live Auctions Feed."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from .comparables import window_start
from .config import Settings
from .liquidity import compute_liquidity
from .normalize import Rules
from .storage import fetch_lots_for_liquidity


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
    records = [
        {
            "Thương Hiệu": g.brand.upper(),
            "Dáng Vỏ": g.form.capitalize(),
            "Điểm Thanh Khoản": f"{g.index:.1%}",
            "Tỷ Lệ Bán": f"{g.sell_through:.1%}",
            "Chuyển Đổi Tim": f"{g.heart_to_hammer:.1%}",
            "Ngày Chốt": f"{g.median_days_to_close:.0f} ngày",
            "Tổng Số Lô": g.lots,
            "Trạng Thái": g.status.upper() if g.status else "ỔN ĐỊNH",
        }
        for g in index.brands
    ]
    st.markdown("### 🏆 Bảng Xếp Hạng Thanh Khoản Thương Hiệu Quốc Tế")
    st.caption("Dựa trên toàn bộ lịch sử đấu giá Catawiki trong 2 năm gần nhất.")
    st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)


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

    records = [
        {
            "Mã Lô": r["lot_id"],
            "Tiêu Đề Đồng Hồ": r["title"],
            "Hạn Đóng Phiên": r["bidding_end_at"],
            "Link Catawiki": r["url"],
        }
        for r in rows
    ]
    st.markdown(f"### 📡 100 Lô Đang Đấu Giá Sắp Kết Thúc Sớm Nhất ({len(rows)}/2.500 lô)")
    st.dataframe(
        pd.DataFrame(records),
        column_config={"Link Catawiki": st.column_config.LinkColumn("Xem Lô Gốc")},
        use_container_width=True,
        hide_index=True,
    )
