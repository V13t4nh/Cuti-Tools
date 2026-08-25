"use client";

import { useEffect, useState } from "react";
import { fetchLiveLots } from "@/lib/api";
import { LiveLot } from "@/lib/types";
import { formatDate } from "@/lib/formatters";
import { Radio, ExternalLink, Search, Clock } from "lucide-react";

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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800/80">
        <div>
          <h1 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
            <Radio className="w-6 h-6 text-sky-400" />
            2.500 Lô Đang Đấu Giá Trên Sàn Catawiki
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Danh sách các phiên đấu giá mở đang được hệ thống quét và theo dõi thời gian thực
          </p>
        </div>

        <div className="relative w-full sm:w-64">
          <input
            type="text"
            placeholder="Tìm theo tên hoặc mã lô..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="glass-panel rounded-2xl p-12 text-center text-slate-400">
          <Radio className="w-8 h-8 text-sky-400 mx-auto animate-pulse mb-2" />
          <p className="text-sm">Đang tải danh sách các lô đang đấu giá...</p>
        </div>
      ) : (
        <div className="glass-panel rounded-2xl p-5 border border-slate-800/80">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filtered.map((lot) => (
              <div
                key={lot.lot_id}
                className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-slate-700/80 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 text-xs text-slate-400 mb-1">
                    <span className="font-mono text-slate-500">{lot.lot_id}</span>
                    <span className="flex items-center gap-1 text-sky-400 font-medium">
                      <Clock className="w-3.5 h-3.5" /> Đóng: {formatDate(lot.bidding_end_at)}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-white line-clamp-2">{lot.title}</h3>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-800/60 flex items-center justify-end">
                  {lot.url && (
                    <a
                      href={lot.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-semibold text-sky-400 hover:text-sky-300 inline-flex items-center gap-1.5"
                    >
                      Xem Trên Catawiki <ExternalLink className="w-3.5 h-3.5" />
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
