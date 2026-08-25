"use client";

import { DealEvaluation } from "@/lib/types";
import { formatVND, formatEUR } from "@/lib/formatters";
import { CheckCircle2, AlertTriangle, XCircle, Info, ShieldCheck, ArrowDownRight } from "lucide-react";

interface VerdictHeroProps {
  decision: DealEvaluation;
  rate: number;
}

export default function VerdictHero({ decision, rate }: VerdictHeroProps) {
  const { verdict, max_buy_cost_vnd, reason, sample_size } = decision;

  const config = {
    green: {
      border: "border-emerald-500/40",
      bg: "bg-gradient-to-br from-emerald-950/70 via-slate-900/90 to-slate-950/90",
      glow: "shadow-glow",
      badgeBg: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
      icon: CheckCircle2,
      iconColor: "text-emerald-400",
      title: "NÊN MUA NGAY (RECOMMENDED DEAL)",
      subtitle: "Mức giá nhập này đảm bảo lợi nhuận ròng an toàn (p25) vượt ngưỡng mục tiêu thanh khoản.",
    },
    yellow: {
      border: "border-amber-500/40",
      bg: "bg-gradient-to-br from-amber-950/70 via-slate-900/90 to-slate-950/90",
      glow: "shadow-glow-gold",
      badgeBg: "bg-amber-500/20 text-amber-300 border-amber-500/30",
      icon: AlertTriangle,
      iconColor: "text-amber-400",
      title: "CÂN NHẮC RỦI RO (MARGINAL DEAL)",
      subtitle: "Deal có lãi trung vị nhưng biên lợi nhuận an toàn (p25) mỏng hoặc biến động giá cao.",
    },
    red: {
      border: "border-rose-500/40",
      bg: "bg-gradient-to-br from-rose-950/70 via-slate-900/90 to-slate-950/90",
      glow: "shadow-glow-red",
      badgeBg: "bg-rose-500/20 text-rose-300 border-rose-500/30",
      icon: XCircle,
      iconColor: "text-rose-400",
      title: "KHÔNG NÊN MUA (HIGH RISK / OVERPRICED)",
      subtitle: "Giá người bán đưa ra quá cao so với lịch sử giá búa thực tế trên sàn quốc tế.",
    },
    insufficient_data: {
      border: "border-slate-700/60",
      bg: "bg-gradient-to-br from-slate-900/80 via-slate-900/90 to-slate-950/90",
      glow: "shadow-none",
      badgeBg: "bg-slate-800 text-slate-300 border-slate-700",
      icon: Info,
      iconColor: "text-slate-400",
      title: "CHƯA ĐỦ DỮ LIỆU (INSUFFICIENT COMPARABLES)",
      subtitle: `Cần tối thiểu 5 mẫu giao dịch cùng mã trong 2 năm qua để định giá an toàn. Hiện chỉ có ${sample_size} mẫu.`,
    },
  }[verdict];

  const IconComponent = config.icon;

  return (
    <div
      className={`rounded-2xl p-5 sm:p-6 border backdrop-blur-xl transition-all ${config.border} ${config.bg} ${config.glow}`}
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Left: Verdict Info */}
        <div className="flex items-start gap-3.5">
          <div className={`p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 ${config.iconColor} shrink-0`}>
            <IconComponent className="w-6 h-6" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${config.badgeBg}`}>
                {verdict.toUpperCase()}
              </span>
              <span className="text-sm font-extrabold tracking-tight text-white">{config.title}</span>
            </div>
            <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">{config.subtitle}</p>
            {reason && (
              <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1 font-mono">
                <span className="text-slate-500">Lý do thuật toán:</span> {reason}
              </p>
            )}
          </div>
        </div>

        {/* Right: Max Buy Price Card */}
        {max_buy_cost_vnd !== null && (
          <div className="shrink-0 bg-slate-950/80 border border-slate-800/90 rounded-xl p-3.5 sm:text-right min-w-[200px]">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center sm:justify-end gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              Giá Trần Khuyên Mua
            </div>
            <div className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 tracking-tight">
              {formatVND(max_buy_cost_vnd)}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
              ~ {formatEUR(max_buy_cost_vnd / rate)} (EUR)
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
