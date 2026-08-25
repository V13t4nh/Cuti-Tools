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
        p25: 0, p75: 0, yMin: 0, yMax: 0, minTime: 0, maxTime: 0,
        p25WidthPct: 33, midWidthPct: 34, highWidthPct: 33, needlePct: 50, riskZone: "safe"
      };
    }

    const sorted = [...prices].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];

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

    const totalRange = globalMax - globalMin || 1;
    const p25Ratio = Math.max(0.15, Math.min(0.5, (p25Val - globalMin) / totalRange));
    const p75Ratio = Math.max(p25Ratio + 0.15, Math.min(0.85, (p75Val - globalMin) / totalRange));

    const p25Pct = p25Ratio * 100;
    const midPct = (p75Ratio - p25Ratio) * 100;
    const highPct = 100 - p25Pct - midPct;

    let needleRatio = 0.5;
    let zone: "safe" | "marginal" | "risk" = "safe";

    if (input_hammer_eur) {
      needleRatio = Math.max(0.02, Math.min(0.98, (input_hammer_eur - globalMin) / totalRange));
      if (input_hammer_eur <= p25Val) {
        zone = "safe";
      } else if (input_hammer_eur <= p75Val) {
        zone = "marginal";
      } else {
        zone = "risk";
      }
    }

    return {
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

      {/* PART 2: THƯỚC ĐO PHÂN VỊ RỦI RO (CLEAN & CONTAINED) */}
      <div className="pt-4 border-t border-white/[0.06] space-y-2.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
          <div className="flex items-center gap-2">
            <ShieldIcon className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-bold text-white tracking-tight">
              Thước Đo Phân Vị Rủi Ro
            </span>
          </div>

          {input_hammer_eur && (
            <div className="text-xs font-mono text-slate-300">
              Điểm hòa vốn: <strong className="text-white font-bold">{formatEUR(input_hammer_eur)}</strong>
              {" — "}
              {riskZone === "safe" ? (
                <span className="text-emerald-400 font-bold">🟢 Vùng Rất An Toàn</span>
              ) : riskZone === "marginal" ? (
                <span className="text-amber-400 font-bold">🟡 Vùng Trung Bình</span>
              ) : (
                <span className="text-rose-400 font-bold">🔴 Vùng Rủi Ro Cao</span>
              )}
              <span className="text-slate-500 text-[11px] ml-1.5">
                (Chỉ {lowerCount}/{soldLots.length} lô rẻ hơn)
              </span>
            </div>
          )}
        </div>

        {/* Compact, Contained Gauge Track with Sleek Pin */}
        <div className="relative py-2">
          {/* Dynamic Continuum Track */}
          <div className="h-3.5 w-full rounded-full bg-slate-950 overflow-hidden flex p-0.5 border border-white/[0.12] shadow-inner relative">
            {/* Safe Zone (Min -> p25) */}
            <div
              style={{ width: `${p25WidthPct}%` }}
              className="h-full bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-l-full"
              title="Vùng Giá Nhập Rẻ & An Toàn"
            />
            {/* Marginal Zone (p25 -> p75) */}
            <div
              style={{ width: `${midWidthPct}%` }}
              className="h-full bg-gradient-to-r from-amber-500 to-amber-600"
              title="Vùng Giá Trung Bình Thị Trường"
            />
            {/* High Risk Zone (p75 -> Max) */}
            <div
              style={{ width: `${highWidthPct}%` }}
              className="h-full bg-gradient-to-r from-rose-600 to-rose-700 rounded-r-full"
              title="Vùng Giá Cao / Nguy Cơ Lỗ"
            />

            {/* Sleek Integrated White Cursor Indicator (Never Overflows) */}
            {input_hammer_eur && (
              <div
                style={{ left: `${needlePct}%` }}
                className="absolute top-0 bottom-0 w-1.5 -translate-x-1/2 bg-white rounded-full shadow-[0_0_8px_rgba(255,255,255,0.9)] z-10 transition-all duration-300 pointer-events-none"
              />
            )}
          </div>

          {/* Scale Legend Labels */}
          <div className="flex justify-between text-xs font-semibold mt-2 px-1 font-mono">
            <span className="text-emerald-400 flex items-center gap-1">
              🟢 An Toàn (&lt; {formatEUR(p25)})
            </span>
            <span className="text-amber-400 flex items-center gap-1">
              🟡 Trung Bình ({formatEUR(p25)} - {formatEUR(p75)})
            </span>
            <span className="text-rose-400 flex items-center gap-1">
              🔴 Rủi Ro (&gt; {formatEUR(p75)})
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
