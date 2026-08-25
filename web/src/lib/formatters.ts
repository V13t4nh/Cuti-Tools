export function formatVND(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return "—";
  }
  const rounded = Math.round(amount);
  return `${rounded.toLocaleString("vi-VN")} ₫`;
}

export function formatEUR(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return "—";
  }
  return `${amount.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

export function formatPercent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || isNaN(rate)) {
    return "—";
  }
  return `${(rate * 100).toFixed(1)}%`;
}

export function formatDays(days: number | null | undefined): string {
  if (days === null || days === undefined || isNaN(days)) {
    return "—";
  }
  return `${days.toFixed(1)} ngày`;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("vi-VN");
  } catch {
    return dateStr;
  }
}
