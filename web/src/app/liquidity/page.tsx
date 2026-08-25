"use client";

import { useEffect, useState } from "react";
import { fetchLiquidity } from "@/lib/api";
import { BrandLiquidity } from "@/lib/types";
import { formatPercent, formatDays } from "@/lib/formatters";
import { BarChart3, TrendingUp, AlertTriangle, ShieldCheck, Search } from "lucide-react";

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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800/80">
        <div>
          <h1 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-emerald-400" />
            Bảng Xếp Hạng Thanh Khoản Thương Hiệu Quốc Tế
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Phân tích tốc độ quay vòng vốn, tỷ lệ bán thành công và xu hướng quý của các hãng đồng hồ
          </p>
        </div>

        <div className="relative w-full sm:w-64">
          <input
            type="text"
            placeholder="Tìm thương hiệu (Omega, Seiko...)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
        </div>
      </div>

      {/* Leaderboard Table / Cards */}
      {loading ? (
        <div className="glass-panel rounded-2xl p-12 text-center text-slate-400">
          <BarChart3 className="w-8 h-8 text-emerald-400 mx-auto animate-pulse mb-2" />
          <p className="text-sm">Đang tải bảng xếp hạng thanh khoản...</p>
        </div>
      ) : (
        <div className="glass-panel rounded-2xl p-5 border border-slate-800/80">
          {/* Desktop & Tablet Table */}
          <div className="hidden sm:block overflow-x-auto rounded-xl border border-slate-800/60">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/90 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Hạng</th>
                  <th className="py-3 px-4">Thương Hiệu</th>
                  <th className="py-3 px-4">Dáng Vỏ</th>
                  <th className="py-3 px-4">Điểm Thanh Khoản</th>
                  <th className="py-3 px-4">Tỷ Lệ Bán</th>
                  <th className="py-3 px-4">Chuyển Đổi Tim</th>
                  <th className="py-3 px-4">Ngày Chốt</th>
                  <th className="py-3 px-4">Tổng Lô</th>
                  <th className="py-3 px-4 text-right">Trạng Thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/40 text-slate-300">
                {filtered.map((b, idx) => (
                  <tr key={`${b.brand}-${b.form}`} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-slate-400">#{idx + 1}</td>
                    <td className="py-3 px-4 font-bold text-white text-sm">{b.brand.toUpperCase()}</td>
                    <td className="py-3 px-4 capitalize text-slate-400">{b.form}</td>
                    <td className="py-3 px-4 font-bold text-emerald-400 text-sm font-mono">
                      {formatPercent(b.index)}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-200">{formatPercent(b.sell_through)}</td>
                    <td className="py-3 px-4 font-mono text-rose-400">{formatPercent(b.heart_to_hammer)}</td>
                    <td className="py-3 px-4 font-mono text-slate-300">{formatDays(b.median_days_to_close)}</td>
                    <td className="py-3 px-4 font-mono text-slate-400">{b.lots} lô</td>
                    <td className="py-3 px-4 text-right">
                      {b.stop_buying ? (
                        <span className="px-2.5 py-1 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[10px] font-bold">
                          DỪNG MUA
                        </span>
                      ) : b.status === "declining" ? (
                        <span className="px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold">
                          SUY GIẢM
                        </span>
                      ) : (
                        <span className="px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold">
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
          <div className="sm:hidden space-y-3">
            {filtered.map((b, idx) => (
              <div
                key={`${b.brand}-${b.form}`}
                className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-500">#{idx + 1}</span>
                    <span className="text-sm font-bold text-white">{b.brand.toUpperCase()}</span>
                    <span className="text-[11px] text-slate-400 capitalize">({b.form})</span>
                  </div>
                  <span className="text-sm font-black text-emerald-400 font-mono">
                    {formatPercent(b.index)}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-[11px] text-slate-400 pt-2 border-t border-slate-800/60">
                  <div>Bán được: <strong className="text-white font-mono">{formatPercent(b.sell_through)}</strong></div>
                  <div>Chốt: <strong className="text-white font-mono">{formatDays(b.median_days_to_close)}</strong></div>
                  <div>Quy mô: <strong className="text-white font-mono">{b.lots}</strong> lô</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
