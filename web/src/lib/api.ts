import { EvaluateResponse, StatusResponse, BrandLiquidity, LiveLot } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchStatus(): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE}/api/status`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch status: ${res.statusText}`);
  }
  return res.json();
}

export async function evaluateDeal(payload: {
  query: string;
  cost: number;
  currency: string;
  condition: string;
  form: string;
}): Promise<EvaluateResponse> {
  const res = await fetch(`${API_BASE}/api/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || `Evaluation failed (${res.status})`);
  }
  return res.json();
}

export async function fetchLiquidity(): Promise<{ brands: BrandLiquidity[] }> {
  const res = await fetch(`${API_BASE}/api/liquidity`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch liquidity: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchLiveLots(): Promise<{ lots: LiveLot[] }> {
  const res = await fetch(`${API_BASE}/api/live-lots`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch live lots: ${res.statusText}`);
  }
  return res.json();
}
