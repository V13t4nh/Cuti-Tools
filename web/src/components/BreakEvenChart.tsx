"use client";

import { useMemo, useState } from "react";
import { ComparisonChart, ComparableLot, DealEvaluation } from "@/lib/types";
import { formatEUR, formatVND, formatDate } from "@/lib/formatters";
import { BarChartIcon, ShieldIcon } from "./Icons";

interface BreakEvenChartProps {
  chart: ComparisonChart;
  comparables?: ComparableLot[];
  decision?: DealEvaluation;
  rate: number;
}

export default function BreakEvenChart({
  chart,
  comparables = [],
  rate,
}: BreakEvenChartProps) {
  const { input_hammer_eur } = chart;
  const [hoveredLot, setHoveredLot] = useState<ComparableLot | null>(null);

  // Extract sold lots with valid hammer prices and valid dates
  const soldLots = useMemo(() => {
    return comparables
      .filter((l) => l.hammer_eur !== null && l.hammer_eur > 0 && l.ended_at)
      .sort((a, b) => new Date(a.ended_at).getTime() - new Date(b.ended_at).getTime());
  }, [comparables]);

  // Price calculations & dynamic percentiles
  const {
    minPrice,
    maxPrice,
    p25,
    p75,
    yMin,
    yMax,
    minTime,
    maxTime,
    p25WidthPct,
    midWidthPct,
    highWidthPct,
    needlePct,
    riskZone,
  } = useMemo(() => {
    const prices = soldLots.map((l) => l.hammer_eur as number);
    if (prices.length === 0) {
      return {
        minPrice: 0, maxPrice: 0, p25: 0, p75: 0, yMin: 0, yMax: 0, minTime: 0, maxTime: 0,
        p25WidthPct: 33, midWidthPct: 34, highWidthPct: 33, needlePct: 50, riskZone: "safe"
      };
    }

    const sorted = [...prices].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];

    // True mathematical percentiles
    const p25Val = sorted[Math.max(0, Math.floor(sorted.length * 0.25))] || min;
    const p75Val = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.75))] || max;

    const allWithInput = input_hammer_eur ? [...prices, input_hammer_eur] : prices;
    const globalMin = Math.min(...allWithInput);
    const globalMax = Math.max(...allWithInput);

    const pad = Math.max((globalMax - globalMin) * 0.2, 30);
    const yMinVal = Math.max(0, globalMin - pad);
    const yMaxVal = globalMax + pad;

    const times = soldLots.map((l) => new Date(l.ended_at).getTime());
    const minT = times.length > 0 ? Math.min(...times) : Date.now() - 365 * 86400000;
    const maxT = times.length > 0 ? Math.max(...times) : Date.now();

    // Calculate dynamic continuum segment widths
    const totalRange = globalMax - globalMin || 1;
    const p25Ratio = Math.max(0.15, Math.min(0.5, (p25Val - globalMin) / totalRange));
    const p75Ratio = Math.max(p25Ratio + 0.15, Math.min(0.85, (p75Val - globalMin) / totalRange));

    const p25Pct = p25Ratio * 100;
    const midPct = (p75Ratio - p25Ratio) * 100;
    const highPct = 100 - p25Pct - midPct;

    // Calculate needle position based on input_hammer_eur
    let needleRatio = 0.5;
    let zone: "safe" | "marginal" | "risk" = "safe";

    if (input_hammer_eur) {
      needleRatio = Math.max(0.04, Math.min(0.96, (input_hammer_eur - globalMin) / totalRange));
      if (input_hammer_eur <= p25Val) {
        zone = "safe";
      } else if (input_hammer_eur <= p75Val) {
        zone = "marginal";
      } else {
        zone = "risk";
      }
    }

    return {
      minPrice: globalMin,
      maxPrice: globalMax,
      p25: p25Val,
      p75: p75Val,
      yMin: yMinVal,
      yMax: yMaxVal,
      minTime: minT,
      maxTime: maxT === minT ? minT + 86400000 : maxT,
      p25WidthPct: p25Pct,
      midWidthPct: midPct,
      highWidthPct: highPct,
      needlePct: needleRatio * 100,
      riskZone: zone,
    };
  }, [soldLots, input_hammer_eur]);

  if (soldLots.length === 0) return null;

  // Chart Dimensions
  const svgWidth = 800;
  const svgHeight = 260;
  const padding = { top: 30, right: 30, bottom: 40, left: 65 };
  const chartW = svgWidth - padding.left - padding.right;
  const chartH = svgHeight - padding.top - padding.bottom;

  // Coordinate mappers
  const getX = (dateStr: string) => {
    const t = new Date(dateStr).getTime();
    const ratio = (t - minTime) / (maxTime - minTime || 1);
    return padding.left + ratio * chartW;
  };

  const getY = (val: number) => {
    const ratio = (val - yMin) / (yMax - yMin || 1);
    return padding.top + chartH - ratio * chartH;
  };

  const trendlinePath = soldLots.reduce((acc, lot, idx) => {
    const x = getX(lot.ended_at);
    const y = getY(lot.hammer_eur as number);
    return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
  }, "");

  const p75Y = getY(p75);
  const p25Y = getY(p25);
  const corridorH = Math.max(p25Y - p75Y, 6);
  const breakEvenY = input_hammer_eur ? getY(input_hammer_eur) : null;

  // Real historical count of sales cheaper than break-even
  const lowerCount = input_hammer_eur
    ? soldLots.filter((l) => (l.hammer_eur as number) < input_hammer_eur).length
    : 0;

  return (
    <div className="glass-card rounded-2xl p-6 sm:p-7 border border-white/[0.08] space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/[0.06]">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2.5 tracking-tight">
            <BarChartIcon className="w-5 h-5 text-emerald-400" />
            Biểu Đồ Lịch Sử Giá Búa & Phân Tích Điểm Hòa Vốn
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Theo dõi dòng giá thực tế qua từng phiên đấu giá và đo lường khoảng an toàn lợi nhuận
          </p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-3.5 text-xs text-slate-400 font-medium">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-sm" />
            <span>Lô đã bán</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-2 rounded bg-emerald-500/20 border border-emerald-500/40" />
            <span>Dải an toàn (p25–p75)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 border-t-2 border-dashed border-rose-500" />
            <span className="text-rose-400 font-semibold">Giá hòa vốn</span>
          </div>
        </div>
      </div>

      {/* PART 1: TIMELINE PRICE SCATTER & CORRIDOR CHART */}
      <div className="relative w-full overflow-hidden select-none">
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-auto overflow-visible">
          {/* Horizontal Gridlines & Y-Axis */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const val = yMin + ratio * (yMax - yMin);
            const y = padding.top + chartH - ratio * chartH;
            return (
              <g key={ratio}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={svgWidth - padding.right}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.05)"
                  strokeDasharray="3 3"
                />
                <text
                  x={padding.left - 10}
                  y={y + 4}
                  textAnchor="end"
                  fill="#64748B"
                  fontSize="11"
                  fontFamily="monospace"
                >
                  {formatEUR(val)}
                </text>
              </g>
            );
          })}

          {/* Dải An Toàn (Corridor p25 -> p75) */}
          <rect
            x={padding.left}
            y={p75Y}
            width={chartW}
            height={corridorH}
            fill="rgba(16, 185, 129, 0.08)"
            stroke="rgba(16, 185, 129, 0.25)"
            strokeDasharray="4 4"
            rx="4"
          />
          <text
            x={svgWidth - padding.right - 8}
            y={p75Y + corridorH / 2 + 3}
            textAnchor="end"
            fill="rgba(16, 185, 129, 0.75)"
            fontSize="11"
            fontWeight="600"
          >
            Dải Giao Dịch Chủ Đạo (p25–p75)
          </text>

          {/* Trendline */}
          {soldLots.length > 1 && (
            <path
              d={trendlinePath}
              fill="none"
              stroke="rgba(255, 255, 255, 0.25)"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Break-Even Horizontal Line */}
          {breakEvenY !== null && input_hammer_eur !== null && (
            <g>
              <line
                x1={padding.left}
                y1={breakEvenY}
                x2={svgWidth - padding.right}
                y2={breakEvenY}
                stroke="#F43F5E"
                strokeWidth="1.75"
                strokeDasharray="5 4"
              />
              <rect
                x={padding.left + 8}
                y={breakEvenY - 18}
                width="160"
                height="22"
                rx="4"
                fill="#4C0519"
                stroke="#F43F5E"
                strokeWidth="1"
              />
              <text
                x={padding.left + 16}
                y={breakEvenY - 3}
                fill="#FDA4AF"
                fontSize="11"
                fontFamily="monospace"
                fontWeight="700"
              >
                HÒA VỐN: {formatEUR(input_hammer_eur)}
              </text>
            </g>
          )}

          {/* Data Points (Scatter Dots) */}
          {soldLots.map((lot) => {
            const x = getX(lot.ended_at);
            const y = getY(lot.hammer_eur as number);
            const isHovered = hoveredLot?.lot_id === lot.lot_id;
            return (
              <g
                key={lot.lot_id}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredLot(lot)}
                onMouseLeave={() => setHoveredLot(null)}
              >
                {isHovered && <circle cx={x} cy={y} r="10" fill="rgba(16, 185, 129, 0.3)" />}
                <circle
                  cx={x}
                  cy={y}
                  r={isHovered ? "6.5" : "5"}
                  fill="#10B981"
                  stroke="#090A0E"
                  strokeWidth="2"
                  className="transition-all"
                />
              </g>
            );
          })}

          {/* X-Axis Date Labels */}
          {soldLots.length > 0 && (
            <>
              <text x={padding.left} y={svgHeight - 10} textAnchor="start" fill="#64748B" fontSize="11" fontFamily="monospace">
                {formatDate(soldLots[0].ended_at)}
              </text>
              {soldLots.length > 2 && (
                <text x={padding.left + chartW / 2} y={svgHeight - 10} textAnchor="middle" fill="#64748B" fontSize="11" fontFamily="monospace">
                  {formatDate(soldLots[Math.floor(soldLots.length / 2)].ended_at)}
                </text>
              )}
              <text x={svgWidth - padding.right} y={svgHeight - 10} textAnchor="end" fill="#64748B" fontSize="11" fontFamily="monospace">
                {formatDate(soldLots[soldLots.length - 1].ended_at)}
              </text>
            </>
          )}
        </svg>

        {/* Hover Details Card */}
        {hoveredLot && (
          <div className="absolute top-2 right-2 p-3.5 rounded-xl bg-black/95 border border-emerald-500/40 shadow-2xl backdrop-blur-md max-w-[290px] pointer-events-none text-xs space-y-1 z-20">
            <div className="text-[11px] text-slate-400 font-mono flex items-center justify-between">
              <span>{formatDate(hoveredLot.ended_at)}</span>
              <span className="text-rose-400">❤️ {hoveredLot.hearts} tim</span>
            </div>
            <div className="font-bold text-white text-sm line-clamp-1">{hoveredLot.title}</div>
            <div className="flex items-baseline gap-2 pt-1 font-mono">
              <span className="text-emerald-400 font-black text-base">{formatEUR(hoveredLot.hammer_eur)}</span>
              <span className="text-slate-400 text-xs">({formatVND(hoveredLot.hammer_eur ? hoveredLot.hammer_eur * rate : 0)})</span>
            </div>
          </div>
        )}
      </div>

      {/* PART 2: THƯỚC ĐO PHÂN VỊ RỦI RO CHUẨN XÁC THEO LOGIC MUA HÀNG */}
      <div className="pt-4 border-t border-white/[0.06] space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div className="flex items-center gap-2">
            <ShieldIcon className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-bold text-white tracking-tight">
              Thước Đo Phân Vị Giá Hòa Vốn (Giá Nhập So Với Toàn Bộ Thị Trường)
            </span>
          </div>

          {input_hammer_eur && (
            <span className="text-xs font-mono text-slate-300">
              {riskZone === "safe" ? (
                <span className="text-emerald-400 font-bold">🟢 Vùng Lãi Rất An Toàn</span>
              ) : riskZone === "marginal" ? (
                <span className="text-amber-400 font-bold">🟡 Vùng Giá Trung Bình</span>
              ) : (
                <span className="text-rose-400 font-bold">🔴 Vùng Rủi Ro Cao</span>
              )}
              {" — "}Chỉ có {lowerCount}/{soldLots.length} lô quá khứ chốt rẻ hơn mức này.
            </span>
          )}
        </div>

        {/* Dynamic Risk Gauge Container */}
        <div className="relative pt-8 pb-3">
          {/* Dynamic Needle Marker */}
          {input_hammer_eur && (
            <div
              style={{ left: `${needlePct}%` }}
              className="absolute top-0 -translate-x-1/2 flex flex-col items-center z-10 pointer-events-none transition-all duration-300"
            >
              <div
                className={`px-3 py-1 rounded-lg font-mono font-bold text-xs shadow-xl whitespace-nowrap border ${
                  riskZone === "safe"
                    ? "bg-emerald-950 text-emerald-300 border-emerald-500/50"
                    : riskZone === "marginal"
                    ? "bg-amber-950 text-amber-300 border-amber-500/50"
                    : "bg-rose-950 text-rose-300 border-rose-500/50"
                }`}
              >
                Điểm Hòa Vốn Của Bạn: {formatEUR(input_hammer_eur)}
              </div>
              <div
                className={`w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[6px] ${
                  riskZone === "safe"
                    ? "border-t-emerald-500"
                    : riskZone === "marginal"
                    ? "border-t-amber-500"
                    : "border-t-rose-500"
                }`}
              />
            </div>
          )}

          {/* Dynamic Continuum Track */}
          {/* Trái = Thấp = An Toàn (Xanh) | Giữa = Trung Bình (Vàng) | Phải = Đắt/Nguy Hiểm (Đỏ) */}
          <div className="h-4 w-full rounded-full bg-slate-950 overflow-hidden flex p-0.5 border border-white/[0.12] shadow-inner">
            {/* Safe Zone (Min -> p25) */}
            <div
              style={{ width: `${p25WidthPct}%` }}
              className="h-full bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-l-full relative group cursor-help"
              title="Vùng Giá Nhập Rẻ & An Toàn (Dưới p25)"
            />
            {/* Marginal Zone (p25 -> p75) */}
            <div
              style={{ width: `${midWidthPct}%` }}
              className="h-full bg-gradient-to-r from-amber-500 to-amber-600 relative group cursor-help"
              title="Vùng Giá Trung Bình Thị Trường (p25 đến p75)"
            />
            {/* High Risk Zone (p75 -> Max) */}
            <div
              style={{ width: `${highWidthPct}%` }}
              className="h-full bg-gradient-to-r from-rose-600 to-rose-700 rounded-r-full relative group cursor-help"
              title="Vùng Giá Cao / Nguy Cơ Lỗ (Trên p75)"
            />
          </div>

          {/* Scale Legend Labels */}
          <div className="flex justify-between text-xs font-semibold mt-2.5 px-1 font-mono">
            <span className="text-emerald-400 flex items-center gap-1">
              🟢 Vùng An Toàn (&lt; {formatEUR(p25)})
            </span>
            <span className="text-amber-400 flex items-center gap-1">
              🟡 Vùng Trung Bình ({formatEUR(p25)} - {formatEUR(p75)})
            </span>
            <span className="text-rose-400 flex items-center gap-1">
              🔴 Vùng Rủi Ro Cao (&gt; {formatEUR(p75)})
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
