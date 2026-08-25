"use client";

import { useMemo, useState } from "react";
import { ComparisonChart, ComparableLot, DealEvaluation } from "@/lib/types";
import { formatEUR, formatVND, formatDate } from "@/lib/formatters";
import { BarChartIcon, TrendingUpIcon, ShieldIcon, AlertIcon } from "./Icons";

interface BreakEvenChartProps {
  chart: ComparisonChart;
  comparables?: ComparableLot[];
  decision?: DealEvaluation;
  rate: number;
}

export default function BreakEvenChart({
  chart,
  comparables = [],
  decision,
  rate,
}: BreakEvenChartProps) {
  const { input_hammer_eur } = chart;
  const [hoveredLot, setHoveredLot] = useState<ComparableLot | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  // Extract sold lots with valid hammer prices and valid dates
  const soldLots = useMemo(() => {
    return comparables
      .filter((l) => l.hammer_eur !== null && l.hammer_eur > 0 && l.ended_at)
      .sort((a, b) => new Date(a.ended_at).getTime() - new Date(b.ended_at).getTime());
  }, [comparables]);

  // Price calculations & percentiles
  const {
    minPrice,
    maxPrice,
    p25,
    p75,
    median,
    yMin,
    yMax,
    minTime,
    maxTime,
  } = useMemo(() => {
    const prices = soldLots.map((l) => l.hammer_eur as number);
    if (input_hammer_eur) prices.push(input_hammer_eur);

    if (prices.length === 0) {
      return { minPrice: 0, maxPrice: 0, p25: 0, p75: 0, median: 0, yMin: 0, yMax: 0, minTime: 0, maxTime: 0 };
    }

    const sorted = [...prices].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];

    // Compute basic p25 and p75
    const p25Val = sorted[Math.floor(sorted.length * 0.25)] || min;
    const medVal = sorted[Math.floor(sorted.length * 0.5)] || min;
    const p75Val = sorted[Math.floor(sorted.length * 0.75)] || max;

    const pad = Math.max((max - min) * 0.2, 30);
    const yMinVal = Math.max(0, min - pad);
    const yMaxVal = max + pad;

    const times = soldLots.map((l) => new Date(l.ended_at).getTime());
    const minT = times.length > 0 ? Math.min(...times) : Date.now() - 365 * 86400000;
    const maxT = times.length > 0 ? Math.max(...times) : Date.now();

    return {
      minPrice: min,
      maxPrice: max,
      p25: p25Val,
      median: medVal,
      p75: p75Val,
      yMin: yMinVal,
      yMax: yMaxVal,
      minTime: minT,
      maxTime: maxT === minT ? minT + 86400000 : maxT,
    };
  }, [soldLots, input_hammer_eur]);

  if (soldLots.length === 0) return null;

  // Chart Dimensions
  const svgWidth = 800;
  const svgHeight = 260;
  const padding = { top: 30, right: 30, bottom: 40, left: 60 };
  const chartW = svgWidth - padding.left - padding.right;
  const chartH = svgHeight - padding.top - padding.bottom;

  // Helper coordinate mappers
  const getX = (dateStr: string) => {
    const t = new Date(dateStr).getTime();
    const ratio = (t - minTime) / (maxTime - minTime || 1);
    return padding.left + ratio * chartW;
  };

  const getY = (val: number) => {
    const ratio = (val - yMin) / (yMax - yMin || 1);
    return padding.top + chartH - ratio * chartH;
  };

  // Generate trendline SVG path
  const trendlinePath = soldLots.reduce((acc, lot, idx) => {
    const x = getX(lot.ended_at);
    const y = getY(lot.hammer_eur as number);
    return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
  }, "");

  // Corridor (p25 to p75) Y bounds
  const p75Y = getY(p75);
  const p25Y = getY(p25);
  const corridorH = Math.max(p25Y - p75Y, 4);

  // Break-even Y line
  const breakEvenY = input_hammer_eur ? getY(input_hammer_eur) : null;

  // Percentile of break-even relative to historical sales
  const historicalPrices = soldLots.map((l) => l.hammer_eur as number).sort((a, b) => a - b);
  const lowerCount = input_hammer_eur
    ? historicalPrices.filter((p) => p < input_hammer_eur).length
    : 0;
  const breakEvenPercentile = Math.round((lowerCount / (historicalPrices.length || 1)) * 100);

  // Risk gauge position percentage (0% to 100%)
  const gaugePercent = input_hammer_eur && maxPrice > minPrice
    ? Math.max(5, Math.min(95, ((input_hammer_eur - minPrice) / (maxPrice - minPrice)) * 100))
    : 50;

  return (
    <div className="glass-card rounded-2xl p-6 sm:p-7 border border-white/[0.08] space-y-6">
      {/* Header */}
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
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto overflow-visible"
        >
          {/* Horizontal Gridlines & Y-Axis Labels */}
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
            fill="rgba(16, 185, 129, 0.7)"
            fontSize="10"
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
                width="150"
                height="20"
                rx="4"
                fill="#4C0519"
                stroke="#F43F5E"
                strokeWidth="1"
              />
              <text
                x={padding.left + 16}
                y={breakEvenY - 4}
                fill="#FDA4AF"
                fontSize="10.5"
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
                className="cursor-pointer transition-transform"
                onMouseEnter={(e) => {
                  setHoveredLot(lot);
                  const rect = e.currentTarget.getBoundingClientRect();
                  setTooltipPos({ x: rect.left + window.scrollX, y: rect.top + window.scrollY });
                }}
                onMouseLeave={() => setHoveredLot(null)}
              >
                {/* Outer Glow on hover */}
                {isHovered && (
                  <circle cx={x} cy={y} r="10" fill="rgba(16, 185, 129, 0.3)" />
                )}
                {/* Main point */}
                <circle
                  cx={x}
                  cy={y}
                  r={isHovered ? "6" : "4.5"}
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
              <text
                x={padding.left}
                y={svgHeight - 10}
                textAnchor="start"
                fill="#64748B"
                fontSize="11"
                fontFamily="monospace"
              >
                {formatDate(soldLots[0].ended_at)}
              </text>
              {soldLots.length > 2 && (
                <text
                  x={padding.left + chartW / 2}
                  y={svgHeight - 10}
                  textAnchor="middle"
                  fill="#64748B"
                  fontSize="11"
                  fontFamily="monospace"
                >
                  {formatDate(soldLots[Math.floor(soldLots.length / 2)].ended_at)}
                </text>
              )}
              <text
                x={svgWidth - padding.right}
                y={svgHeight - 10}
                textAnchor="end"
                fill="#64748B"
                fontSize="11"
                fontFamily="monospace"
              >
                {formatDate(soldLots[soldLots.length - 1].ended_at)}
              </text>
            </>
          )}
        </svg>

        {/* Hover Details Card (Overlay) */}
        {hoveredLot && (
          <div className="absolute top-2 right-2 p-3 rounded-xl bg-black/90 border border-emerald-500/40 shadow-2xl backdrop-blur-md max-w-[280px] pointer-events-none text-xs space-y-1 z-20">
            <div className="text-[10px] text-slate-400 font-mono flex items-center justify-between">
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

      {/* PART 2: THƯỚC ĐO PHÂN VỊ RỦI RO (PRICE RISK GAUGE) */}
      <div className="pt-3 border-t border-white/[0.06] space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldIcon className="w-4 h-4 text-emerald-400" />
            <span className="text-xs sm:text-sm font-bold text-white tracking-tight">
              Thước Đo Phân Vị & Biên Độ An Toàn
            </span>
          </div>
          {input_hammer_eur && (
            <span className="text-xs font-mono text-slate-400">
              Vị thế hòa vốn: <strong className="text-emerald-400">{breakEvenPercentile}%</strong> (Chỉ {lowerCount}/{soldLots.length} lô quá khứ thấp hơn giá này)
            </span>
          )}
        </div>

        {/* Gauge Bar */}
        <div className="relative pt-6 pb-2">
          {/* Needle / Pin Indicator */}
          {input_hammer_eur && (
            <div
              style={{ left: `${gaugePercent}%` }}
              className="absolute top-0 -translate-x-1/2 flex flex-col items-center transition-all z-10 pointer-events-none"
            >
              <div className="px-2.5 py-0.5 rounded-md bg-white text-black font-mono font-black text-[10px] shadow-lg whitespace-nowrap">
                Vị Trí Mua: {formatEUR(input_hammer_eur)}
              </div>
              <div className="w-0 h-0 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent border-t-[5px] border-t-white" />
            </div>
          )}

          {/* Continuum Gradient Track */}
          <div className="h-3.5 w-full rounded-full bg-slate-900 overflow-hidden flex p-0.5 border border-white/[0.1]">
            <div className="h-full bg-rose-500/80 rounded-l-full" style={{ width: "25%" }} title="Vùng Lỗ" />
            <div className="h-full bg-amber-500/80" style={{ width: "25%" }} title="Vùng Lãi Mỏng" />
            <div className="h-full bg-emerald-500/80 rounded-r-full" style={{ width: "50%" }} title="Vùng Lãi An Toàn & Đậm" />
          </div>

          {/* Zone Legend Labels */}
          <div className="flex justify-between text-[11px] font-medium text-slate-400 mt-2 px-1">
            <span className="text-rose-400 font-semibold">🔴 Vùng Lỗ (&lt; Hòa vốn)</span>
            <span className="text-amber-400 font-semibold">🟡 Lãi Mỏng (Hòa vốn → p25)</span>
            <span className="text-emerald-400 font-semibold">🟢 Lãi An Toàn (p25 → Max)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
