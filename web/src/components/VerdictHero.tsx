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
      bg: "bg-emerald-950/20",
      badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
      icon: CheckIcon,
      iconColor: "text-emerald-400",
      title: "NÊN MUA NGAY (RECOMMENDED DEAL)",
      subtitle: "Mức giá nhập này đảm bảo lợi nhuận ròng an toàn (p25) vượt ngưỡng mục tiêu thanh khoản.",
    },
    yellow: {
      border: "border-amber-500/30",
      bg: "bg-amber-950/20",
      badge: "bg-amber-500/15 text-amber-400 border-amber-500/30",
      icon: AlertIcon,
      iconColor: "text-amber-400",
      title: "CÂN NHẮC RỦI RO (MARGINAL DEAL)",
      subtitle: "Deal có lãi trung vị nhưng biên lợi nhuận an toàn (p25) mỏng hoặc biến động giá cao.",
    },
    red: {
      border: "border-rose-500/30",
      bg: "bg-rose-950/20",
      badge: "bg-rose-500/15 text-rose-400 border-rose-500/30",
      icon: CloseIcon,
      iconColor: "text-rose-400",
      title: "KHÔNG NÊN MUA (HIGH RISK / OVERPRICED)",
      subtitle: "Giá người bán đưa ra quá cao so với lịch sử giá búa thực tế trên sàn quốc tế.",
    },
    insufficient_data: {
      border: "border-white/[0.08]",
      bg: "bg-white/[0.02]",
      badge: "bg-white/[0.06] text-slate-300 border-white/[0.1]",
      icon: InfoIcon,
      iconColor: "text-slate-400",
      title: "CHƯA ĐỦ DỮ LIỆU (INSUFFICIENT COMPARABLES)",
      subtitle: `Cần tối thiểu 5 mẫu giao dịch cùng mã trong 2 năm qua để định giá an toàn. Hiện có ${sample_size} mẫu.`,
    },
  }[verdict];

  const IconComponent = config.icon;

  return (
    <div className={`glass-card rounded-2xl p-5 sm:p-6 border ${config.border} ${config.bg}`}>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
        {/* Left: Verdict Text */}
        <div className="flex items-start gap-3.5">
          <div className={`p-2.5 rounded-xl bg-black/40 border border-white/[0.08] ${config.iconColor} shrink-0`}>
            <IconComponent className="w-5 h-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded border font-mono ${config.badge}`}>
                {verdict.toUpperCase()}
              </span>
              <span className="text-sm font-bold tracking-tight text-white">{config.title}</span>
            </div>
            <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">{config.subtitle}</p>
            {reason && (
              <p className="text-[11px] text-slate-400 mt-1.5 font-mono">
                <span className="text-slate-500">Lý do:</span> {reason}
              </p>
            )}
          </div>
        </div>

        {/* Right: Max Buy Price */}
        {max_buy_cost_vnd !== null && (
          <div className="shrink-0 bg-black/40 border border-white/[0.08] rounded-xl p-3.5 sm:text-right min-w-[200px]">
            <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center sm:justify-end gap-1.5">
              <ShieldIcon className="w-3.5 h-3.5 text-emerald-400" />
              Giá Trần Khuyên Mua
            </div>
            <div className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 font-mono tracking-tight">
              {formatVND(max_buy_cost_vnd)}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
              ~ {formatEUR(max_buy_cost_vnd / rate)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
