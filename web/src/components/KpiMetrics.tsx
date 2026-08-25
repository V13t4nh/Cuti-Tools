"use client";

import { DealEvaluation } from "@/lib/types";
import { formatPercent, formatDays } from "@/lib/formatters";
import { Package, TrendingUp, Clock, HeartHandshake } from "lucide-react";

interface KpiMetricsProps {
  decision: DealEvaluation;
}

export default function KpiMetrics({ decision }: KpiMetricsProps) {
  const kpis = [
    {
      label: "Số Mẫu Đã Bán",
      value: `${decision.sample_size} lô`,
      icon: Package,
      color: "text-slate-300",
    },
    {
      label: "Tỷ Lệ Bán Thành Công",
      value: formatPercent(decision.sell_through_rate),
      icon: TrendingUp,
      color: "text-emerald-400",
    },
    {
      label: "Thời Gian Chốt Phiên",
      value: formatDays(decision.median_days_to_close),
      icon: Clock,
      color: "text-sky-400",
    },
    {
      label: "Chuyển Đổi Tim → Búa",
      value: formatPercent(decision.heart_to_hammer_rate),
      icon: HeartHandshake,
      color: "text-rose-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
      {kpis.map((kpi) => {
        const Icon = kpi.icon;
        return (
          <div
            key={kpi.label}
            className="glass-panel rounded-xl p-3.5 border border-slate-800/80 flex items-center gap-3"
          >
            <div className={`p-2 rounded-lg bg-slate-950 border border-slate-800 ${kpi.color}`}>
              <Icon className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] text-slate-400 font-medium">{kpi.label}</div>
              <div className="text-sm sm:text-base font-bold text-white tracking-tight">{kpi.value}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
