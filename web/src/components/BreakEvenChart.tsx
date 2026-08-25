"use client";

import { useMemo, useState } from "react";
import { ComparisonChart } from "@/lib/types";
import { formatEUR, formatVND } from "@/lib/formatters";
import { BarChart2 } from "lucide-react";

interface BreakEvenChartProps {
  chart: ComparisonChart;
  rate: number;
}

export default function BreakEvenChart({ chart, rate }: BreakEvenChartProps) {
  const { hammer_prices_eur, input_hammer_eur } = chart;
  const [hoveredBin, setHoveredBin] = useState<number | null>(null);

  const { bins, minVal, maxVal, maxCount } = useMemo(() => {
    if (!hammer_prices_eur || hammer_prices_eur.length === 0) {
      return { bins: [], minVal: 0, maxVal: 0, maxCount: 0 };
    }

    const min = Math.min(...hammer_prices_eur, input_hammer_eur || Infinity);
    const max = Math.max(...hammer_prices_eur, input_hammer_eur || -Infinity);
    const binCount = 8;
    const step = (max - min) / binCount || 1;

    const b = Array.from({ length: binCount }, (_, i) => ({
      start: min + i * step,
      end: min + (i + 1) * step,
      count: 0,
    }));

    hammer_prices_eur.forEach((price) => {
      const idx = Math.min(Math.floor((price - min) / step), binCount - 1);
      if (b[idx]) b[idx].count++;
    });

    const highest = Math.max(...b.map((x) => x.count), 1);
    return { bins: b, minVal: min, maxVal: max, maxCount: highest };
  }, [hammer_prices_eur, input_hammer_eur]);

  if (!hammer_prices_eur || hammer_prices_eur.length === 0) return null;

  // Calculate Break-Even line X percentage
  const breakEvenPercent = input_hammer_eur !== null && maxVal > minVal
    ? Math.max(0, Math.min(100, ((input_hammer_eur - minVal) / (maxVal - minVal)) * 100))
    : null;

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800/80">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-sky-400" />
            Phân Phối Giá Búa Lịch Sử (€) & Vạch Hòa Vốn
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">
            So sánh giá búa cần đạt để bạn hòa vốn so với lịch sử thực tế của thị trường
          </p>
        </div>
      </div>

      {/* Chart Container */}
      <div className="relative h-44 w-full pt-4 pb-6 select-none">
        {/* Bars Container */}
        <div className="absolute inset-0 pb-6 flex items-end gap-1.5 px-2">
          {bins.map((bin, idx) => {
            const heightPercent = (bin.count / maxCount) * 85;
            const isHovered = hoveredBin === idx;
            return (
              <div
                key={idx}
                className="flex-1 h-full flex flex-col justify-end items-center relative group"
                onMouseEnter={() => setHoveredBin(idx)}
                onMouseLeave={() => setHoveredBin(null)}
              >
                {/* Tooltip */}
                {isHovered && (
                  <div className="absolute -top-12 z-20 px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-700 text-[11px] text-white whitespace-nowrap shadow-xl">
                    <span className="font-semibold">{formatEUR(bin.start)} - {formatEUR(bin.end)}</span>
                    <span className="text-emerald-400 ml-1.5 font-bold">({bin.count} lô)</span>
                  </div>
                )}

                {/* The Bar */}
                <div
                  style={{ height: `${Math.max(heightPercent, 6)}%` }}
                  className={`w-full rounded-t-md transition-all duration-200 ${
                    isHovered
                      ? "bg-sky-400 shadow-lg shadow-sky-500/30"
                      : "bg-sky-600/70 hover:bg-sky-500/90"
                  }`}
                />
              </div>
            );
          })}
        </div>

        {/* Break-Even Vertical Line */}
        {breakEvenPercent !== null && input_hammer_eur !== null && (
          <div
            style={{ left: `${breakEvenPercent}%` }}
            className="absolute top-0 bottom-6 w-0.5 bg-rose-500 border-l-2 border-dashed border-rose-500 z-10 pointer-events-none"
          >
            <div className="absolute -top-3.5 -left-16 bg-rose-950/90 text-rose-300 border border-rose-600/60 px-2 py-0.5 rounded text-[10px] font-bold whitespace-nowrap shadow-md">
              Hòa vốn: {formatEUR(input_hammer_eur)} ({formatVND(input_hammer_eur * rate)})
            </div>
          </div>
        )}

        {/* X-Axis labels */}
        <div className="absolute bottom-0 inset-x-0 flex justify-between text-[10px] text-slate-500 font-mono px-2 pt-1 border-t border-slate-800">
          <span>{formatEUR(minVal)}</span>
          <span>{formatEUR((minVal + maxVal) / 2)}</span>
          <span>{formatEUR(maxVal)}</span>
        </div>
      </div>
    </div>
  );
}
