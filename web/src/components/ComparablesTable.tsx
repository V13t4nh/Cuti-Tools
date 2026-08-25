"use client";

import { useState } from "react";
import { ComparableLot } from "@/lib/types";
import { formatVND, formatEUR, formatDate } from "@/lib/formatters";
import { ExternalLink, Heart, Layers, Search } from "lucide-react";

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
    <div className="glass-panel rounded-2xl p-5 border border-slate-800/80">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Layers className="w-4 h-4 text-emerald-400" />
            Lịch Sử Các Lô Tương Đồng Đã Bán ({lots.length} lô)
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Dữ liệu đấu giá thực tế từ sàn quốc tế Catawiki
          </p>
        </div>

        {/* Search filter */}
        <div className="relative w-full sm:w-64">
          <input
            type="text"
            placeholder="Lọc tiêu đề, thương hiệu..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
        </div>
      </div>

      {/* Desktop & Tablet Table View */}
      <div className="hidden sm:block overflow-x-auto rounded-xl border border-slate-800/60">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/90 text-slate-400 font-semibold border-b border-slate-800">
            <tr>
              <th className="py-2.5 px-3">Chiếc Đồng Hồ (Title)</th>
              <th className="py-2.5 px-3">Giá Búa (€)</th>
              <th className="py-2.5 px-3">Quy Đổi (VNĐ)</th>
              <th className="py-2.5 px-3">Độ Khớp</th>
              <th className="py-2.5 px-3">❤️ Tim</th>
              <th className="py-2.5 px-3">Lượt Bid</th>
              <th className="py-2.5 px-3">Ngày Bán</th>
              <th className="py-2.5 px-3 text-right">Chi Tiết</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/40 text-slate-300">
            {filtered.map((lot) => (
              <tr key={lot.lot_id} className="hover:bg-slate-800/30 transition-colors">
                <td className="py-2.5 px-3 font-medium text-white max-w-[260px] truncate" title={lot.title}>
                  {lot.title}
                </td>
                <td className="py-2.5 px-3 font-bold text-emerald-400 font-mono">
                  {lot.hammer_eur !== null ? formatEUR(lot.hammer_eur) : "Chưa bán"}
                </td>
                <td className="py-2.5 px-3 text-slate-300 font-mono">
                  {lot.hammer_eur !== null ? formatVND(lot.hammer_eur * rate) : "—"}
                </td>
                <td className="py-2.5 px-3">
                  <span className="px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800 text-[10px] text-slate-300 font-semibold">
                    {(lot.score * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="py-2.5 px-3 text-rose-400 font-semibold">
                  <span className="flex items-center gap-1">
                    <Heart className="w-3 h-3 fill-rose-500/20 text-rose-400" />
                    {lot.hearts}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-slate-400">
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
                      className="inline-flex items-center gap-1 text-sky-400 hover:text-sky-300 font-medium"
                    >
                      Xem <ExternalLink className="w-3 h-3" />
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

      {/* Mobile Card List View */}
      <div className="sm:hidden space-y-2.5">
        {filtered.map((lot) => (
          <div
            key={lot.lot_id}
            className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-semibold text-white line-clamp-2">{lot.title}</span>
              <span className="px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800 text-[10px] text-slate-300 font-semibold shrink-0">
                {(lot.score * 100).toFixed(0)}%
              </span>
            </div>

            <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-800/60">
              <div>
                <span className="text-emerald-400 font-bold font-mono">
                  {lot.hammer_eur !== null ? formatEUR(lot.hammer_eur) : "Chưa bán"}
                </span>
                <span className="text-slate-400 text-[11px] ml-1.5 font-mono">
                  ({lot.hammer_eur !== null ? formatVND(lot.hammer_eur * rate) : "—"})
                </span>
              </div>
              <span className="flex items-center gap-1 text-rose-400 text-[11px] font-semibold">
                <Heart className="w-3 h-3 fill-rose-500/20" />
                {lot.hearts} tim
              </span>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
              <span>Ngày: {formatDate(lot.ended_at)}</span>
              {lot.url && (
                <a
                  href={lot.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sky-400 flex items-center gap-1 font-medium"
                >
                  Xem lô gốc <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
