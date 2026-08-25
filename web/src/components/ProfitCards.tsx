"use client";

import { DealEvaluation } from "@/lib/types";
import { formatVND, formatEUR } from "@/lib/formatters";
import { Shield, Target, Rocket } from "lucide-react";

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
      desc: "25% trường hợp giá búa thấp nhất",
      eur: net_p25_eur,
      vnd: net_p25_eur ? net_p25_eur * rate : null,
      icon: Shield,
      color: "text-emerald-400",
      border: "border-emerald-500/20",
      bg: "bg-emerald-950/20",
    },
    {
      title: "Lãi Ròng Kỳ Vọng (Median)",
      desc: "Mức lãi ròng trung bình kỳ vọng",
      eur: net_median_eur,
      vnd: net_median_eur ? net_median_eur * rate : null,
      icon: Target,
      color: "text-sky-400",
      border: "border-sky-500/20",
      bg: "bg-sky-950/20",
    },
    {
      title: "Lãi Ròng Tối Ưu (p75)",
      desc: "25% trường hợp giá búa cao nhất",
      eur: net_p75_eur,
      vnd: net_p75_eur ? net_p75_eur * rate : null,
      icon: Rocket,
      color: "text-amber-400",
      border: "border-amber-500/20",
      bg: "bg-amber-950/20",
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
            className={`glass-panel rounded-xl p-4 border ${c.border} ${c.bg} flex flex-col justify-between`}
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">{c.title}</span>
                <Icon className={`w-4 h-4 ${c.color}`} />
              </div>
              <p className="text-[10px] text-slate-400 mt-0.5">{c.desc}</p>
            </div>

            <div className="mt-3">
              <div
                className={`text-lg sm:text-xl font-bold tracking-tight ${
                  isPositive ? "text-white" : "text-rose-400"
                }`}
              >
                {c.vnd !== null ? `${isPositive ? "+" : ""}${formatVND(c.vnd)}` : "—"}
              </div>
              <div className="text-xs text-slate-400 font-mono mt-0.5">
                {c.eur !== null ? `${isPositive ? "+" : ""}${formatEUR(c.eur)}` : "—"}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
