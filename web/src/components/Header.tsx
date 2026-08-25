"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchStatus } from "@/lib/api";
import { StatusResponse } from "@/lib/types";
import { Watch, BarChart3, Radio, Database, TrendingUp, Menu, X } from "lucide-react";

export default function Header() {
  const pathname = usePathname();
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    fetchStatus()
      .then(setStatus)
      .catch((err) => console.error("Error fetching header status:", err));
  }, []);

  const navLinks = [
    { href: "/", label: "Thẩm Định Deal", icon: Watch },
    { href: "/liquidity", label: "Thanh Khoản Hãng", icon: BarChart3 },
    { href: "/live", label: "2.500 Lô Đang Mở", icon: Radio },
  ];

  return (
    <header className="sticky top-0 z-50 bg-[#0B0F17]/85 backdrop-blur-xl border-b border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400/20 to-emerald-600/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform">
                <Watch className="w-5 h-5" />
              </div>
              <div>
                <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-emerald-300 bg-clip-text text-transparent">
                  CUTI<span className="text-emerald-400 font-extrabold">.TOOLS</span>
                </span>
                <span className="hidden sm:inline-block ml-2 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                  Luxury Arbitrage
                </span>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center ml-6 space-x-1">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const active = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      active
                        ? "bg-slate-800 text-white shadow-sm border border-slate-700"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                    }`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${active ? "text-emerald-400" : ""}`} />
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Real-time Status Badges */}
          <div className="hidden lg:flex items-center gap-2.5 text-xs">
            {status ? (
              <>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-slate-300">
                  <Database className="w-3.5 h-3.5 text-emerald-400" />
                  <span>
                    <strong className="text-white">{status.lots_count.toLocaleString()}</strong> Lô Lịch Sử
                  </span>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-slate-300">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500"></span>
                  </span>
                  <span>
                    <strong className="text-white">{status.live_watch_count.toLocaleString()}</strong> Lô Đang Quét
                  </span>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-amber-300">
                  <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
                  <span>1 € = {status.eur_vnd_rate.toLocaleString("vi-VN")} ₫</span>
                </div>
              </>
            ) : (
              <div className="h-6 w-48 bg-slate-800/50 animate-pulse rounded-full" />
            )}
          </div>

          {/* Mobile Menu Button */}
          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white"
              aria-label="Toggle Menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden py-3 border-t border-slate-800/80 space-y-1">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium ${
                    active ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "text-slate-300"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {link.label}
                </Link>
              );
            })}
            {status && (
              <div className="pt-2 mt-2 border-t border-slate-800/60 grid grid-cols-2 gap-2 text-[11px] text-slate-400">
                <div className="px-2 py-1 rounded bg-slate-900 border border-slate-800">
                  Kho: <strong className="text-white">{status.lots_count}</strong> lô
                </div>
                <div className="px-2 py-1 rounded bg-slate-900 border border-slate-800">
                  Hàng đợi: <strong className="text-white">{status.live_watch_count}</strong> lô
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
