"use client";

import { useEffect, useState } from "react";
import { fetchLiveLots } from "@/lib/api";
import { LiveLot } from "@/lib/types";
import { formatDate } from "@/lib/formatters";
import { RadioIcon, ExternalLinkIcon, SearchIcon, ClockIcon } from "@/components/Icons";

export default function LiveLotsPage() {
  const [lots, setLots] = useState<LiveLot[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetchLiveLots()
      .then((res) => setLots(res.lots))
      .catch((err) => console.error("Error fetching live lots:", err))
      .finally(() => setLoading(false));
  }, []);

  const filtered = lots.filter((l) =>
    l.title.toLowerCase().includes(search.toLowerCase()) ||
    l.lot_id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <RadioIcon className="w-5 h-5 text-emerald-400" />
            Lô Đang Đấu Giá Trên Sàn Catawiki
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Danh sách các phiên đấu giá mở đang được theo dõi và chốt giá định kỳ
          </p>
        </div>

        <div className="relative w-full sm:w-60">
          <input
            type="text"
            placeholder="Tìm mã hoặc tên..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-black/40 border border-white/[0.1] rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/70"
          />
          <SearchIcon className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="glass-card rounded-2xl p-12 text-center text-slate-400">
          <RadioIcon className="w-6 h-6 text-emerald-400 mx-auto animate-pulse mb-2" />
          <p className="text-xs font-mono">Đang tải danh sách lô đang đấu giá...</p>
        </div>
      ) : (
        <div className="glass-card rounded-2xl p-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filtered.map((lot) => (
              <div
                key={lot.lot_id}
                className="p-4 rounded-xl bg-black/40 border border-white/[0.06] hover:border-white/[0.12] transition-colors flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 text-xs text-slate-400 mb-1.5">
                    <span className="font-mono text-slate-500 text-[11px]">{lot.lot_id}</span>
                    <span className="flex items-center gap-1 text-slate-300 font-mono text-[11px]">
                      <ClockIcon className="w-3.5 h-3.5 text-slate-400" /> {formatDate(lot.bidding_end_at)}
                    </span>
                  </div>
                  <h3 className="text-xs font-semibold text-white line-clamp-2 leading-relaxed">{lot.title}</h3>
                </div>

                <div className="mt-3 pt-2 border-t border-white/[0.04] flex items-center justify-end">
                  {lot.url && (
                    <a
                      href={lot.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] font-medium text-slate-400 hover:text-emerald-400 inline-flex items-center gap-1.5 transition-colors"
                    >
                      Xem Trên Catawiki <ExternalLinkIcon className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
