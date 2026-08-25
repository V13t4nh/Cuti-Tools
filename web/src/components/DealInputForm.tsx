"use client";

import { useState } from "react";
import { WatchIcon } from "./Icons";

interface DealInputFormProps {
  onEvaluate: (data: {
    query: string;
    cost: number;
    currency: string;
    condition: string;
    form: string;
  }) => void;
  isLoading: boolean;
}

export default function DealInputForm({ onEvaluate, isLoading }: DealInputFormProps) {
  const [query, setQuery] = useState("Seiko Presage SRPB41");
  const [costStr, setCostStr] = useState("6.200.000");
  const [currency, setCurrency] = useState("vnd");
  const [condition, setCondition] = useState("fullset");
  const [form, setForm] = useState("round");

  const parseRawCost = (str: string): number => {
    const cleaned = str.replace(/[^\d]/g, "");
    return cleaned ? parseInt(cleaned, 10) : 0;
  };

  const handleCostChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    if (currency === "vnd") {
      const num = parseRawCost(val);
      setCostStr(num ? num.toLocaleString("vi-VN") : "");
    } else {
      setCostStr(val);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const rawCost = currency === "vnd" ? parseRawCost(costStr) : parseFloat(costStr.replace(",", "."));
    if (!query.trim() || !rawCost) return;

    onEvaluate({
      query: query.trim(),
      cost: rawCost,
      currency,
      condition,
      form,
    });
  };

  return (
    <div className="glass-card rounded-2xl p-5 sm:p-6">
      <div className="flex items-center justify-between pb-3.5 mb-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-white/[0.06] flex items-center justify-center text-slate-300">
            <WatchIcon className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-white tracking-tight">
            Thông Tin Chiếc Đồng Hồ
          </h2>
        </div>
        <span className="text-[10px] text-slate-500 font-mono uppercase tracking-wider">
          Arbitrage Gate
        </span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Model Query */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">
            Tên / Mã Đồng Hồ (Model / Reference):
          </label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ví dụ: Seiko Presage SRPB41, Omega Seamaster 210.30.42..."
            className="w-full bg-black/40 border border-white/[0.1] rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-emerald-500/70 focus:ring-1 focus:ring-emerald-500/40 transition-all font-medium"
            required
          />
        </div>

        {/* Cost & Currency */}
        <div className="grid grid-cols-3 gap-2.5">
          <div className="col-span-2">
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Giá Người Bán Rao:
            </label>
            <div className="relative">
              <input
                type="text"
                value={costStr}
                onChange={handleCostChange}
                placeholder={currency === "vnd" ? "6.200.000" : "250"}
                className="w-full bg-black/40 border border-white/[0.1] rounded-xl px-3.5 py-2.5 text-sm text-white font-mono placeholder-slate-600 focus:outline-none focus:border-emerald-500/70 focus:ring-1 focus:ring-emerald-500/40 transition-all"
                required
              />
              <span className="absolute right-3 top-2.5 text-[11px] text-slate-500 font-mono uppercase font-bold pointer-events-none">
                {currency}
              </span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Đơn Vị:
            </label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full bg-black/40 border border-white/[0.1] rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:border-emerald-500/70 transition-all font-medium cursor-pointer"
            >
              <option value="vnd">VNĐ (₫)</option>
              <option value="eur">EUR (€)</option>
            </select>
          </div>
        </div>

        {/* Condition & Watch Form */}
        <div className="grid grid-cols-2 gap-2.5">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Tình Trạng:
            </label>
            <select
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              className="w-full bg-black/40 border border-white/[0.1] rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:border-emerald-500/70 transition-all cursor-pointer"
            >
              <option value="fullset">Fullset (Hộp & Sổ)</option>
              <option value="naked">Naked (Chỉ Đồng Hồ)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Dáng Vỏ (Form):
            </label>
            <select
              value={form}
              onChange={(e) => setForm(e.target.value)}
              className="w-full bg-black/40 border border-white/[0.1] rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:border-emerald-500/70 transition-all cursor-pointer"
            >
              <option value="round">Tròn (Round)</option>
              <option value="square">Vuông (Square)</option>
              <option value="tonneau">Bầu Dục (Tonneau)</option>
              <option value="rectangular">Chữ Nhật (Tank)</option>
              <option value="other">Khác (Other)</option>
            </select>
          </div>
        </div>

        {/* Action Button */}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full mt-2 py-3 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 active:bg-emerald-600 text-black font-bold text-xs uppercase tracking-wider transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-sm"
        >
          {isLoading ? "Đang Phân Tích..." : "Thẩm Định Deal Ngay"}
        </button>
      </form>
    </div>
  );
}
