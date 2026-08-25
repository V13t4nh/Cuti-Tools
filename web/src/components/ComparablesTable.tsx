"use client";

import { useState } from "react";
import { ComparableLot } from "@/lib/types";
import { formatVND, formatEUR, formatDate } from "@/lib/formatters";
import { LayersIcon, SearchIcon, HeartIcon, ExternalLinkIcon } from "./Icons";

interface ComparablesTableProps {
  lots: ComparableLot[];
  rate: number;
}

export default function ComparablesTable({ lots, rate }: ComparablesTableProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const filtered = lots.filter((l) =>
    l.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    l.brand.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (!lots || lots.length === 0) return null;

  return (
    <div className="glass-card rounded-2xl p-6 sm:p-7 border border-white/[0.08]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
        <div>
          <h3 className="text-sm sm:text-base font-bold text-white flex items-center gap-2.5 tracking-tight">
            <LayersIcon className="w-5 h-5 text-slate-300" />
            Lịch Sử Các Lô Tương Đồng Đã Bán ({lots.length} lô)
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Dữ liệu đối chiếu từ các phiên đấu giá đã chốt thành công trên sàn quốc tế
          </p>
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-64">
          <input
            type="text"
            placeholder="Lọc kết quả..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-black/50 border border-white/[0.12] rounded-xl pl-9 pr-3.5 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 font-medium"
          />
          <SearchIcon className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
        </div>
      </div>

      {/* Desktop & Tablet Table */}
      <div className="hidden sm:block overflow-x-auto rounded-xl border border-white/[0.08]">
        <table className="w-full text-left text-sm">
          <thead className="bg-black/60 text-slate-400 font-semibold border-b border-white/[0.08] text-xs uppercase tracking-wider">
            <tr>
              <th className="py-3 px-4">Chiếc Đồng Hồ</th>
              <th className="py-3 px-4">Giá Búa (€)</th>
              <th className="py-3 px-4">Quy Đổi (VNĐ)</th>
              <th className="py-3 px-4">Độ Khớp</th>
              <th className="py-3 px-4">Tim</th>
              <th className="py-3 px-4">Bid</th>
              <th className="py-3 px-4">Ngày Bán</th>
              <th className="py-3 px-4 text-right">Lô Gốc</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04] text-slate-300">
            {filtered.map((lot) => (
              <tr key={lot.lot_id} className="hover:bg-white/[0.04] transition-colors">
                <td className="py-3.5 px-4 font-medium text-white max-w-[260px] truncate text-sm" title={lot.title}>
                  {lot.title}
                </td>
                <td className="py-3.5 px-4 font-bold text-emerald-400 font-mono text-sm sm:text-base">
                  {lot.hammer_eur !== null ? formatEUR(lot.hammer_eur) : "Chưa bán"}
                </td>
                <td className="py-3.5 px-4 text-slate-300 font-mono text-xs sm:text-sm">
                  {lot.hammer_eur !== null ? formatVND(lot.hammer_eur * rate) : "—"}
                </td>
                <td className="py-3.5 px-4 font-mono">
                  <span className="px-2 py-0.5 rounded-md bg-white/[0.06] text-xs font-semibold text-slate-300">
                    {(lot.score * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="py-3.5 px-4 text-rose-400 font-mono font-medium">
                  <span className="flex items-center gap-1.5">
                    <HeartIcon className="w-3.5 h-3.5 text-rose-400" filled />
                    {lot.hearts}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-slate-400 font-mono text-xs">
                  {lot.bids_count !== null ? lot.bids_count : "—"}
                </td>
                <td className="py-3.5 px-4 text-slate-400 font-mono text-xs">
                  {formatDate(lot.ended_at)}
                </td>
                <td className="py-3.5 px-4 text-right">
                  {lot.url ? (
                    <a
                      href={lot.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-slate-400 hover:text-emerald-400 font-medium text-xs transition-colors"
                    >
                      <ExternalLinkIcon className="w-4 h-4" />
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card List */}
      <div className="sm:hidden space-y-3">
        {filtered.map((lot) => (
          <div
            key={lot.lot_id}
            className="p-4 rounded-xl bg-black/50 border border-white/[0.08] space-y-2.5"
          >
            <div className="flex items-start justify-between gap-2.5">
              <span className="text-sm font-semibold text-white line-clamp-2">{lot.title}</span>
              <span className="px-2 py-0.5 rounded-md bg-white/[0.06] text-xs font-mono text-slate-300 shrink-0">
                {(lot.score * 100).toFixed(0)}%
              </span>
            </div>

            <div className="flex items-center justify-between text-sm pt-2 border-t border-white/[0.06]">
              <div>
                <span className="text-emerald-400 font-bold font-mono text-base">
                  {lot.hammer_eur !== null ? formatEUR(lot.hammer_eur) : "Chưa bán"}
                </span>
                <span className="text-slate-400 text-xs ml-2 font-mono">
                  ({lot.hammer_eur !== null ? formatVND(lot.hammer_eur * rate) : "—"})
                </span>
              </div>
              <span className="flex items-center gap-1 text-rose-400 text-xs font-mono font-semibold">
                <HeartIcon className="w-3.5 h-3.5" filled />
                {lot.hearts}
              </span>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
              <span className="font-mono">Ngày: {formatDate(lot.ended_at)}</span>
              {lot.url && (
                <a
                  href={lot.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-300 hover:text-emerald-400 flex items-center gap-1 font-medium"
                >
                  Lô gốc <ExternalLinkIcon className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
