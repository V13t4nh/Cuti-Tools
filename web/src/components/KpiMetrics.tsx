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
      color: "text-slate-300",
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
      color: "text-slate-200",
    },
    {
      label: "Chuyển Đổi Tim → Búa",
      value: formatPercent(decision.heart_to_hammer_rate),
      icon: HeartIcon,
      color: "text-rose-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {kpis.map((kpi) => {
        const Icon = kpi.icon;
        return (
          <div
            key={kpi.label}
            className="glass-card rounded-2xl p-4 sm:p-5 flex items-center gap-3.5"
          >
            <div className={`p-2.5 rounded-xl bg-white/[0.05] border border-white/[0.08] ${kpi.color}`}>
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs sm:text-sm text-slate-400 font-medium">{kpi.label}</div>
              <div className="text-base sm:text-lg font-bold font-mono text-white tracking-tight mt-0.5">{kpi.value}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
