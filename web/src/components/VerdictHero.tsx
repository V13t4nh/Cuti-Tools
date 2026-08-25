"use client";

import { DealEvaluation } from "@/lib/types";
import { formatVND, formatEUR } from "@/lib/formatters";
import { CheckIcon, AlertIcon, CloseIcon, InfoIcon, ShieldIcon } from "./Icons";

interface VerdictHeroProps {
  decision: DealEvaluation;
  rate: number;
}

export default function VerdictHero({ decision, rate }: VerdictHeroProps) {
  const { verdict, max_buy_cost_vnd, reason, sample_size } = decision;

  const config = {
    green: {
      border: "border-emerald-500/30",
      bg: "bg-emerald-950/25",
      badge: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
      icon: CheckIcon,
      iconColor: "text-emerald-400",
      title: "NÊN MUA NGAY (RECOMMENDED DEAL)",
      subtitle: "Mức giá nhập này đảm bảo lợi nhuận ròng an toàn (p25) vượt ngưỡng mục tiêu thanh khoản.",
    },
    yellow: {
      border: "border-amber-500/30",
      bg: "bg-amber-950/25",
      badge: "bg-amber-500/20 text-amber-400 border-amber-500/40",
      icon: AlertIcon,
      iconColor: "text-amber-400",
      title: "CÂN NHẮC RỦI RO (MARGINAL DEAL)",
      subtitle: "Deal có lãi trung vị nhưng biên lợi nhuận an toàn (p25) mỏng hoặc biến động giá cao.",
    },
    red: {
      border: "border-rose-500/30",
      bg: "bg-rose-950/25",
      badge: "bg-rose-500/20 text-rose-400 border-rose-500/40",
      icon: CloseIcon,
      iconColor: "text-rose-400",
      title: "KHÔNG NÊN MUA (HIGH RISK / OVERPRICED)",
      subtitle: "Giá người bán đưa ra quá cao so với lịch sử giá búa thực tế trên sàn quốc tế.",
    },
    insufficient_data: {
      border: "border-white/[0.12]",
      bg: "bg-white/[0.03]",
      badge: "bg-white/[0.08] text-slate-300 border-white/[0.14]",
      icon: InfoIcon,
      iconColor: "text-slate-400",
      title: "CHƯA ĐỦ DỮ LIỆU (INSUFFICIENT COMPARABLES)",
      subtitle: `Cần tối thiểu 5 mẫu giao dịch cùng mã trong 2 năm qua để định giá an toàn. Hiện có ${sample_size} mẫu.`,
    },
  }[verdict];

  const IconComponent = config.icon;

  return (
    <div className={`glass-card rounded-2xl p-6 sm:p-7 border ${config.border} ${config.bg}`}>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        {/* Left: Verdict Text */}
        <div className="flex items-start gap-4">
          <div className={`p-3 rounded-xl bg-black/50 border border-white/[0.1] ${config.iconColor} shrink-0`}>
            <IconComponent className="w-6 h-6" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <span className={`text-xs font-bold px-2.5 py-1 rounded-md border font-mono ${config.badge}`}>
                {verdict.toUpperCase()}
              </span>
              <span className="text-base sm:text-lg font-extrabold tracking-tight text-white">
                {config.title}
              </span>
            </div>
            <p className="text-sm text-slate-200 mt-2 leading-relaxed font-normal">
              {config.subtitle}
            </p>
            {reason && (
              <p className="text-xs text-slate-400 mt-2 font-mono">
                <span className="text-slate-500 font-semibold">Lý do:</span> {reason}
              </p>
            )}
          </div>
        </div>

        {/* Right: Max Buy Price */}
        {max_buy_cost_vnd !== null && (
          <div className="shrink-0 bg-black/50 border border-white/[0.1] rounded-2xl p-4 sm:p-5 sm:text-right min-w-[220px]">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center sm:justify-end gap-1.5">
              <ShieldIcon className="w-4 h-4 text-emerald-400" />
              Giá Trần Khuyên Mua
            </div>
            <div className="text-2xl sm:text-3xl font-black text-emerald-400 mt-1.5 font-mono tracking-tight">
              {formatVND(max_buy_cost_vnd)}
            </div>
            <div className="text-xs text-slate-400 mt-1 font-mono">
              ~ {formatEUR(max_buy_cost_vnd / rate)} (EUR)
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
