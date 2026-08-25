import type { Metadata, Viewport } from "next";
import "./globals.css";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "CUTI-Tools — Thẩm Định & Quyết Định Mua Đồng Hồ Arbitrage",
  description: "Hệ thống ra quyết định và định giá đồng hồ xa xỉ tự động theo dữ liệu đấu giá quốc tế Catawiki.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#07090E",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className="dark">
      <body className="font-sans antialiased text-slate-100 flex flex-col min-h-screen">
        <Header />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
        <footer className="border-t border-slate-800/60 py-6 text-center text-xs text-slate-500">
          <p>© 2026 CUTI-Tools. Hệ thống định giá đồng hồ độc quyền cho Dev & Đối tác.</p>
        </footer>
      </body>
    </html>
  );
}
