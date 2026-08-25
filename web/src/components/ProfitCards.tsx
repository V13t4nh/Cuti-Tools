"use client";

import { DealEvaluation } from "@/lib/types";
import { formatVND, formatEUR } from "@/lib/formatters";
import { ShieldIcon, TargetIcon, TrendingUpIcon } from "./Icons";

interface ProfitCardsProps {
  decision: DealEvaluation;
  rate: number;
}

export default function ProfitCards({ decision, rate }: ProfitCardsProps) {
  if (decision.verdict === "insufficient_data") return null;

  const { net_p25_eur, net_median_eur, net_p75_eur } = decision;

  const cards = [
    {
      title: "Lãi Ròng An Toàn (p25)",
      desc: "25% thấp nhất thị trường",
      eur: net_p25_eur,
      vnd: net_p25_eur ? net_p25_eur * rate : null,
      icon: ShieldIcon,
      color: "text-emerald-400",
      accent: "text-emerald-400",
    },
    {
      title: "Lãi Ròng Kỳ Vọng (Median)",
      desc: "Mức lãi ròng trung vị",
      eur: net_median_eur,
      vnd: net_median_eur ? net_median_eur * rate : null,
      icon: TargetIcon,
      color: "text-slate-200",
      accent: "text-white",
    },
    {
      title: "Lãi Ròng Tối Ưu (p75)",
      desc: "25% cao nhất thị trường",
      eur: net_p75_eur,
      vnd: net_p75_eur ? net_p75_eur * rate : null,
      icon: TrendingUpIcon,
      color: "text-amber-400",
      accent: "text-amber-300",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {cards.map((c) => {
        const Icon = c.icon;
        const isPositive = c.eur !== null && c.eur > 0;
        return (
          <div
            key={c.title}
            className="glass-card rounded-2xl p-4 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">{c.title}</span>
                <div className={`p-1.5 rounded-lg bg-white/[0.04] ${c.color}`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
              </div>
              <p className="text-[10px] text-slate-500 mt-0.5">{c.desc}</p>
            </div>

            <div className="mt-4">
              <div
                className={`text-lg sm:text-xl font-bold font-mono tracking-tight ${
                  isPositive ? c.accent : "text-rose-400"
                }`}
              >
                {c.vnd !== null ? `${isPositive ? "+" : ""}${formatVND(c.vnd)}` : "—"}
              </div>
              <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                {c.eur !== null ? `${isPositive ? "+" : ""}${formatEUR(c.eur)}` : "—"}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
