"use client";

import { useEffect, useState } from "react";
import DealInputForm from "@/components/DealInputForm";
import VerdictHero from "@/components/VerdictHero";
import ProfitCards from "@/components/ProfitCards";
import KpiMetrics from "@/components/KpiMetrics";
import BreakEvenChart from "@/components/BreakEvenChart";
import ComparablesTable from "@/components/ComparablesTable";
import { evaluateDeal } from "@/lib/api";
import { EvaluateResponse } from "@/lib/types";
import { Sparkles, AlertCircle } from "lucide-react";

export default function Home() {
  const [data, setData] = useState<EvaluateResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEvaluate = async (payload: {
    query: string;
    cost: number;
    currency: string;
    condition: string;
    form: string;
  }) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await evaluateDeal(payload);
      setData(res);
    } catch (err: any) {
      setError(err.message || "Đã xảy ra lỗi khi thẩm định deal");
    } finally {
      setIsLoading(false);
    }
  };

  // Initial evaluation on mount for default Seiko deal
  useEffect(() => {
    handleEvaluate({
      query: "Seiko Presage SRPB41",
      cost: 6200000,
      currency: "vnd",
      condition: "fullset",
      form: "round",
    });
  }, []);

  return (
    <div className="space-y-6">
      {/* Hero Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-800/80">
        <div>
          <h1 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
            <span>🔍</span> Thẩm Định & Quyết Định Deal Đồng Hồ
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Định giá mua tức thì và phân tích lợi nhuận dựa trên hàng nghìn phiên đấu giá quốc tế
          </p>
        </div>
      </div>

      {/* Responsive 3-Breakpoint Layout */}
      {/* Desktop (lg: 2 cols), Tablet/Mobile (1 col stacked) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Input Form (lg: 4 cols) */}
        <div className="lg:col-span-5 xl:col-span-4 lg:sticky lg:top-24 space-y-4">
          <DealInputForm onEvaluate={handleEvaluate} isLoading={isLoading} />
        </div>

        {/* Right Column: Decision Results (lg: 8 cols) */}
        <div className="lg:col-span-7 xl:col-span-8 space-y-5">
          {error && (
            <div className="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {data ? (
            <>
              {/* 1. Hero Verdict Card */}
              <VerdictHero decision={data.decision} rate={data.eur_vnd_rate} />

              {/* 2. Profit Breakdown 3 Cards */}
              <ProfitCards decision={data.decision} rate={data.eur_vnd_rate} />

              {/* 3. KPI Grid (4 Metrics) */}
              <KpiMetrics decision={data.decision} />

              {/* 4. Interactive Break-Even Histogram Chart */}
              <BreakEvenChart chart={data.chart} rate={data.eur_vnd_rate} />

              {/* 5. Historical Comparables Table */}
              <ComparablesTable lots={data.comparables} rate={data.eur_vnd_rate} />
            </>
          ) : (
            <div className="glass-panel rounded-2xl p-12 text-center text-slate-400 space-y-3">
              <Sparkles className="w-8 h-8 text-emerald-400 mx-auto animate-pulse" />
              <p className="text-sm font-medium">Đang tải dữ liệu thẩm định...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
