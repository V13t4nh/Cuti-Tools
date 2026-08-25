"use client";

import { useState } from "react";
import { Sparkles, Loader2, DollarSign, Tag, Clock, HelpCircle } from "lucide-react";

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

const PRESETS = [
  { name: "Seiko Presage", query: "Seiko Presage SRPB41", cost: 6200000, currency: "vnd", condition: "fullset", form: "round" },
  { name: "Omega Seamaster", query: "Omega Seamaster Diver 300M 210.30.42", cost: 28000000, currency: "vnd", condition: "fullset", form: "round" },
  { name: "Citizen Tsuyosa", query: "Citizen Tsuyosa NJ0150", cost: 4500000, currency: "vnd", condition: "fullset", form: "round" },
  { name: "Rolex Datejust", query: "Rolex Datejust 126234", cost: 180000000, currency: "vnd", condition: "fullset", form: "round" },
];

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

  const applyPreset = (preset: typeof PRESETS[0]) => {
    setQuery(preset.query);
    setCurrency(preset.currency);
    setCostStr(preset.currency === "vnd" ? preset.cost.toLocaleString("vi-VN") : preset.cost.toString());
    setCondition(preset.condition);
    setForm(preset.form);

    onEvaluate({
      query: preset.query,
      cost: preset.cost,
      currency: preset.currency,
      condition: preset.condition,
      form: preset.form,
    });
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
    <div className="glass-panel rounded-2xl p-5 sm:p-6 shadow-xl border border-slate-800/80">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-400" />
          Nhập Thông Tin Deal
        </h2>
        <span className="text-[11px] text-slate-400">Dev & Đối tác</span>
      </div>

      {/* Quick Presets Pills */}
      <div className="mb-5">
        <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
          Gợi ý mẫu phổ biến:
        </label>
        <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-none">
          {PRESETS.map((p) => (
            <button
              key={p.name}
              type="button"
              onClick={() => applyPreset(p)}
              className="flex-shrink-0 text-xs font-medium px-2.5 py-1.5 rounded-lg bg-slate-900/80 hover:bg-emerald-500/10 hover:text-emerald-300 hover:border-emerald-500/30 border border-slate-800 text-slate-300 transition-all"
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Model Query */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">
            Tên / Mã Đồng Hồ (Model / Reference):
          </label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ví dụ: Seiko Presage SRPB41, Omega Seamaster 210.30.42..."
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
            required
          />
        </div>

        {/* Cost & Currency */}
        <div className="grid grid-cols-3 gap-2.5">
          <div className="col-span-2">
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Giá Người Bán Rao:
            </label>
            <div className="relative">
              <input
                type="text"
                value={costStr}
                onChange={handleCostChange}
                placeholder={currency === "vnd" ? "6.200.000" : "250"}
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-white font-medium placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
                required
              />
              <span className="absolute right-3 top-2.5 text-xs text-slate-400 font-semibold pointer-events-none">
                {currency.toUpperCase()}
              </span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Đơn Vị:
            </label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
            >
              <option value="vnd">VNĐ (₫)</option>
              <option value="eur">EUR (€)</option>
            </select>
          </div>
        </div>

        {/* Condition & Watch Form */}
        <div className="grid grid-cols-2 gap-2.5">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Tình Trạng (Condition):
            </label>
            <select
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
            >
              <option value="fullset">Fullset (Đầy đủ hộp sổ)</option>
              <option value="naked">Naked (Chỉ đồng hồ)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Dáng Vỏ (Form):
            </label>
            <select
              value={form}
              onChange={(e) => setForm(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
            >
              <option value="round">Tròn (Round)</option>
              <option value="square">Vuông (Square)</option>
              <option value="tonneau">Bầu Dục (Tonneau)</option>
              <option value="rectangular">Chữ Nhật (Tank)</option>
              <option value="other">Khác (Other)</option>
            </select>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full mt-2 py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-500 via-teal-500 to-emerald-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold text-sm shadow-lg shadow-emerald-500/20 active:scale-[0.99] transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Đang Thẩm Định...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              ⚡ ĐÁNH GIÁ DEAL NGAY
            </>
          )}
        </button>
      </form>
    </div>
  );
}
