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
import { AlertIcon, WatchIcon } from "@/components/Icons";

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
    <div className="space-y-7">
      {/* Hero Welcome Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.08]">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-white/[0.06] flex items-center justify-center text-emerald-400 shrink-0">
              <WatchIcon className="w-5 h-5" />
            </div>
            Thẩm Định & Định Giá Mua Đồng Hồ
          </h1>
          <p className="text-sm sm:text-base text-slate-400 mt-1.5 leading-relaxed">
            Định giá mua tối đa và phân tích phân vị rủi ro dựa trên dữ liệu đấu giá thực tế quốc tế
          </p>
        </div>
      </div>

      {/* 3-Breakpoint Responsive Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-7 items-start">
        {/* Left Column: Form (lg: 5 cols) */}
        <div className="lg:col-span-5 xl:col-span-4 lg:sticky lg:top-24 space-y-4">
          <DealInputForm onEvaluate={handleEvaluate} isLoading={isLoading} />
        </div>

        {/* Right Column: Analytics & Verdict (lg: 7/8 cols) */}
        <div className="lg:col-span-7 xl:col-span-8 space-y-5">
          {error && (
            <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-3">
              <AlertIcon className="w-5 h-5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {data ? (
            <>
              {/* 1. Hero Verdict Card */}
              <VerdictHero decision={data.decision} rate={data.eur_vnd_rate} />

              {/* 2. Profit Breakdown 3 Cards */}
              <ProfitCards decision={data.decision} rate={data.eur_vnd_rate} />

              {/* 3. KPI Grid */}
              <KpiMetrics decision={data.decision} />

              {/* 4. Break-Even Histogram Chart */}
              <BreakEvenChart chart={data.chart} rate={data.eur_vnd_rate} />

              {/* 5. Historical Comparables Table */}
              <ComparablesTable lots={data.comparables} rate={data.eur_vnd_rate} />
            </>
          ) : (
            <div className="glass-card rounded-2xl p-14 text-center text-slate-400">
              <WatchIcon className="w-8 h-8 text-emerald-400 mx-auto animate-pulse mb-3" />
              <p className="text-sm font-mono font-medium">Đang tính toán dữ liệu định giá...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
