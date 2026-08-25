"use client";

import { useEffect, useState } from "react";
import { fetchLiquidity } from "@/lib/api";
import { BrandLiquidity } from "@/lib/types";
import { formatPercent, formatDays } from "@/lib/formatters";
import { BarChartIcon, SearchIcon } from "@/components/Icons";

export default function LiquidityPage() {
  const [brands, setBrands] = useState<BrandLiquidity[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetchLiquidity()
      .then((res) => setBrands(res.brands))
      .catch((err) => console.error("Error fetching liquidity:", err))
      .finally(() => setLoading(false));
  }, []);

  const filtered = brands.filter((b) =>
    b.brand.toLowerCase().includes(search.toLowerCase()) ||
    b.form.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <BarChartIcon className="w-5 h-5 text-emerald-400" />
            Bảng Xếp Hạng Thanh Khoản Thương Hiệu
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Phân tích tốc độ quay vòng vốn và tỷ lệ bán thành công theo từng hãng đồng hồ
          </p>
        </div>

        <div className="relative w-full sm:w-60">
          <input
            type="text"
            placeholder="Tìm thương hiệu..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-black/40 border border-white/[0.1] rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/70"
          />
          <SearchIcon className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
        </div>
      </div>

      {/* Leaderboard Table */}
      {loading ? (
        <div className="glass-card rounded-2xl p-12 text-center text-slate-400">
          <BarChartIcon className="w-6 h-6 text-emerald-400 mx-auto animate-pulse mb-2" />
          <p className="text-xs font-mono">Đang tải dữ liệu thanh khoản...</p>
        </div>
      ) : (
        <div className="glass-card rounded-2xl p-5">
          <div className="hidden sm:block overflow-x-auto rounded-xl border border-white/[0.06]">
            <table className="w-full text-left text-xs">
              <thead className="bg-black/60 text-slate-400 font-medium border-b border-white/[0.08]">
                <tr>
                  <th className="py-2.5 px-3.5 font-mono">#</th>
                  <th className="py-2.5 px-3.5">Thương Hiệu</th>
                  <th className="py-2.5 px-3.5">Dáng Vỏ</th>
                  <th className="py-2.5 px-3.5">Điểm Thanh Khoản</th>
                  <th className="py-2.5 px-3.5">Tỷ Lệ Bán</th>
                  <th className="py-2.5 px-3.5">Chuyển Đổi Tim</th>
                  <th className="py-2.5 px-3.5">Ngày Chốt</th>
                  <th className="py-2.5 px-3.5">Tổng Lô</th>
                  <th className="py-2.5 px-3.5 text-right">Trạng Thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04] text-slate-300">
                {filtered.map((b, idx) => (
                  <tr key={`${b.brand}-${b.form}`} className="hover:bg-white/[0.03] transition-colors">
                    <td className="py-2.5 px-3.5 font-mono text-slate-500">#{idx + 1}</td>
                    <td className="py-2.5 px-3.5 font-bold text-white uppercase">{b.brand}</td>
                    <td className="py-2.5 px-3.5 capitalize text-slate-400">{b.form}</td>
                    <td className="py-2.5 px-3.5 font-bold text-emerald-400 font-mono">
                      {formatPercent(b.index)}
                    </td>
                    <td className="py-2.5 px-3.5 font-mono text-slate-200">{formatPercent(b.sell_through)}</td>
                    <td className="py-2.5 px-3.5 font-mono text-rose-400">{formatPercent(b.heart_to_hammer)}</td>
                    <td className="py-2.5 px-3.5 font-mono text-slate-300">{formatDays(b.median_days_to_close)}</td>
                    <td className="py-2.5 px-3.5 font-mono text-slate-400">{b.lots} lô</td>
                    <td className="py-2.5 px-3.5 text-right">
                      {b.stop_buying ? (
                        <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-bold font-mono">
                          DỪNG MUA
                        </span>
                      ) : b.status === "declining" ? (
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-bold font-mono">
                          SUY GIẢM
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-bold font-mono">
                          ỔN ĐỊNH
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards */}
          <div className="sm:hidden space-y-2.5">
            {filtered.map((b, idx) => (
              <div
                key={`${b.brand}-${b.form}`}
                className="p-3.5 rounded-xl bg-black/40 border border-white/[0.06] space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-500">#{idx + 1}</span>
                    <span className="text-sm font-bold text-white uppercase">{b.brand}</span>
                    <span className="text-[11px] text-slate-400 capitalize">({b.form})</span>
                  </div>
                  <span className="text-sm font-bold text-emerald-400 font-mono">
                    {formatPercent(b.index)}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-[11px] text-slate-400 pt-2 border-t border-white/[0.06]">
                  <div>Bán: <strong className="text-white font-mono">{formatPercent(b.sell_through)}</strong></div>
                  <div>Chốt: <strong className="text-white font-mono">{formatDays(b.median_days_to_close)}</strong></div>
                  <div>Lô: <strong className="text-white font-mono">{b.lots}</strong></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
