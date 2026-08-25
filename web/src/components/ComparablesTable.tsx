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
    <div className="glass-card rounded-2xl p-5 border border-white/[0.08]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-xs font-bold text-white flex items-center gap-2 tracking-tight">
            <LayersIcon className="w-4 h-4 text-slate-300" />
            Lịch Sử Các Lô Tương Đồng Đã Bán ({lots.length} lô)
          </h3>
          <p className="text-[10px] text-slate-400 mt-0.5">
            Dữ liệu đối chiếu từ các phiên đấu giá đã kết thúc trên sàn quốc tế
          </p>
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-60">
          <input
            type="text"
            placeholder="Lọc kết quả..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-black/40 border border-white/[0.1] rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/70"
          />
          <SearchIcon className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
        </div>
      </div>

      {/* Desktop & Tablet Table */}
      <div className="hidden sm:block overflow-x-auto rounded-xl border border-white/[0.06]">
        <table className="w-full text-left text-xs">
          <thead className="bg-black/60 text-slate-400 font-medium border-b border-white/[0.08]">
            <tr>
              <th className="py-2.5 px-3">Chiếc Đồng Hồ</th>
              <th className="py-2.5 px-3">Giá Búa (€)</th>
              <th className="py-2.5 px-3">Quy Đổi (VNĐ)</th>
              <th className="py-2.5 px-3">Độ Khớp</th>
              <th className="py-2.5 px-3">Tim</th>
              <th className="py-2.5 px-3">Bid</th>
              <th className="py-2.5 px-3">Ngày Bán</th>
              <th className="py-2.5 px-3 text-right">Lô Gốc</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04] text-slate-300">
            {filtered.map((lot) => (
              <tr key={lot.lot_id} className="hover:bg-white/[0.03] transition-colors">
                <td className="py-2.5 px-3 font-medium text-white max-w-[240px] truncate" title={lot.title}>
                  {lot.title}
                </td>
                <td className="py-2.5 px-3 font-bold text-emerald-400 font-mono">
                  {lot.hammer_eur !== null ? formatEUR(lot.hammer_eur) : "Chưa bán"}
                </td>
                <td className="py-2.5 px-3 text-slate-300 font-mono">
                  {lot.hammer_eur !== null ? formatVND(lot.hammer_eur * rate) : "—"}
                </td>
                <td className="py-2.5 px-3 font-mono">
                  <span className="px-1.5 py-0.5 rounded bg-white/[0.05] text-[10px] text-slate-300">
                    {(lot.score * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="py-2.5 px-3 text-rose-400 font-mono">
                  <span className="flex items-center gap-1">
                    <HeartIcon className="w-3 h-3 text-rose-400" filled />
                    {lot.hearts}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-slate-400 font-mono">
                  {lot.bids_count !== null ? lot.bids_count : "—"}
                </td>
                <td className="py-2.5 px-3 text-slate-400 font-mono">
                  {formatDate(lot.ended_at)}
                </td>
                <td className="py-2.5 px-3 text-right">
                  {lot.url ? (
                    <a
                      href={lot.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-slate-400 hover:text-emerald-400 font-medium"
                    >
                      <ExternalLinkIcon className="w-3.5 h-3.5" />
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
      <div className="sm:hidden space-y-2.5">
        {filtered.map((lot) => (
          <div
            key={lot.lot_id}
            className="p-3.5 rounded-xl bg-black/40 border border-white/[0.06] space-y-2"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-semibold text-white line-clamp-2">{lot.title}</span>
              <span className="px-1.5 py-0.5 rounded bg-white/[0.05] text-[10px] font-mono text-slate-300 shrink-0">
                {(lot.score * 100).toFixed(0)}%
              </span>
            </div>

            <div className="flex items-center justify-between text-xs pt-1.5 border-t border-white/[0.06]">
              <div>
                <span className="text-emerald-400 font-bold font-mono">
                  {lot.hammer_eur !== null ? formatEUR(lot.hammer_eur) : "Chưa bán"}
                </span>
                <span className="text-slate-400 text-[11px] ml-1.5 font-mono">
                  ({lot.hammer_eur !== null ? formatVND(lot.hammer_eur * rate) : "—"})
                </span>
              </div>
              <span className="flex items-center gap-1 text-rose-400 text-[11px] font-mono">
                <HeartIcon className="w-3 h-3" filled />
                {lot.hearts}
              </span>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
              <span className="font-mono">Ngày: {formatDate(lot.ended_at)}</span>
              {lot.url && (
                <a
                  href={lot.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-400 hover:text-emerald-400 flex items-center gap-1 font-medium"
                >
                  Lô gốc <ExternalLinkIcon className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
