const API_URL = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { headers: { "Content-Type": "application/json", ...options?.headers }, ...options });
  if (!response.ok) {
    const body = await response.text();
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      throw new Error(parsed.detail ?? `Request failed: ${response.status}`);
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error(body || `Request failed: ${response.status}`);
      throw error;
    }
  }
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<Dashboard>("/api/v1/dashboard/summary"),
  customers: () => request<Customer[]>("/api/v1/customers?limit=100"),
  customer: (id: string) => request<Customer360>(`/api/v1/customers/${id}`),
  segments: () => request<Segment[]>("/api/v1/segments"),
  opportunities: () => request<Opportunity[]>("/api/v1/opportunities"),
  models: () => request<ModelRun[]>("/api/v1/models/performance"),
  copilot: (question: string) => request<CopilotResponse>("/api/v1/copilot/chat", { method: "POST", body: JSON.stringify({ question }) }),
};

export type Dashboard = { currency: string; customers: number; lifetime_revenue: number; high_churn_risk: number; sales_opportunities: number; segments: { name: string; customers: number }[] };
export type Customer = { id: number; external_customer_id: string; country: string; first_purchase_at: string; last_purchase_at: string };
export type Customer360 = Customer & { segment_name: string; churn_probability: number; propensity_probability: number; features: Record<string, string | number>; recommendations: { product_id: number; stock_code: string; description: string; rank: number; score: number; reason: string }[]; next_action: { title: string; rationale: string; priority_score: number } };
export type Segment = { name: string; customers: number; average_distance: number };
export type Opportunity = { customer_id: number; external_customer_id: string; country: string; propensity_probability: number };
export type ModelRun = { id: string; model_type: string; version: string; metrics: Record<string, unknown>; created_at: string };
export type CopilotCitation = { source: string; chunk_id: string; excerpt: string; score?: number | null };
export type TraceEvent = { node: string; detail: string };
export type ValidationResult = { grounded: boolean; confidence: number; notes: string; unsupported_claims: string[] };
export type CopilotResponse = {
  answer: string;
  intent: string;
  route: string;
  citations: CopilotCitation[];
  data: Record<string, unknown>;
  trace: TraceEvent[];
  validation: ValidationResult;
  provider: string;
};
