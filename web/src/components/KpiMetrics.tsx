"use client";

import { DealEvaluation } from "@/lib/types";
import { formatPercent, formatDays } from "@/lib/formatters";
import { WatchIcon, TrendingUpIcon, ClockIcon, HeartIcon } from "./Icons";

interface KpiMetricsProps {
  decision: DealEvaluation;
}

export default function KpiMetrics({ decision }: KpiMetricsProps) {
  const kpis = [
    {
      label: "Số Mẫu Đã Bán",
      value: `${decision.sample_size} lô`,
      icon: WatchIcon,
      color: "text-slate-400",
    },
    {
      label: "Tỷ Lệ Bán Được",
      value: formatPercent(decision.sell_through_rate),
      icon: TrendingUpIcon,
      color: "text-emerald-400",
    },
    {
      label: "Thời Gian Chốt Phiên",
      value: formatDays(decision.median_days_to_close),
      icon: ClockIcon,
      color: "text-slate-300",
    },
    {
      label: "Chuyển Đổi Tim → Búa",
      value: formatPercent(decision.heart_to_hammer_rate),
      icon: HeartIcon,
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
            className="glass-card rounded-xl p-3.5 flex items-center gap-3"
          >
            <div className={`p-2 rounded-lg bg-white/[0.04] border border-white/[0.06] ${kpi.color}`}>
              <Icon className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] text-slate-400 font-medium">{kpi.label}</div>
              <div className="text-sm sm:text-base font-bold font-mono text-white tracking-tight">{kpi.value}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
