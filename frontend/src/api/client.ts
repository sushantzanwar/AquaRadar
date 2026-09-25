export type Stamp = {
  confidence: number;
  confidence_reasons: string[];
  lab_verification_required: true;
  disclaimer: string;
};

export type SceneDate = Stamp & {
  date: string;
  status: string;
  reason: string | null;
};

export type Alert = Stamp & {
  alert_id: string;
  evidence_id: string;
  water_body_id: string;
  location: string;
  datetime: string;
  affected_region: string;
  indicator: string;
  severity: "watch" | "warning" | "severe";
  template: string;
  polished_summary: string | null;
  narrative_source: string;
};

export type WaterBody = Stamp & {
  id: string;
  name: string;
  dates: SceneDate[];
  latest_alert: Alert | null;
};

export type SceneIndex = Stamp & { water_bodies: WaterBody[] };

export type Comparison = {
  indicator: string;
  value: number;
  baseline_mean: number;
  baseline_std: number | null;
  sigma: number | null;
  threshold: number;
  crossed: boolean;
  sample_count: number;
  fused: boolean;
};

export type EvidenceCard = Stamp & {
  evidence_id: string;
  water_body_id: string;
  zone_id: string;
  zone_name: string;
  date: string;
  comparisons: Comparison[];
  extent_m2: number | null;
  extent_change_m2: number | null;
  contributing_indicators: string[];
  thresholds_crossed: string[];
};

export type ZoneScore = Stamp & {
  zone_id: string;
  zone_name: string;
  date: string;
  flagged: boolean;
  fused_score: number;
  severity_label: string | null;
  contributing_indicators: string[];
  comparisons: Comparison[];
  extent_m2: number | null;
  lat: number;
  lon: number;
};

export type AnomalyResponse = Stamp & {
  water_body_id: string;
  date: string;
  status: string;
  reason: string | null;
  scene_extent_m2: number | null;
  zones: ZoneScore[];
};

export type AlertFeed = Stamp & {
  water_body_id: string;
  date: string;
  status: string;
  reason: string | null;
  alerts: Alert[];
};

export type PrioritySite = Stamp & {
  rank: number;
  zone_id: string;
  zone_name: string;
  lat: number;
  lon: number;
  priority: number;
  severity: number;
  persistence: number;
  proximity: number;
  distance_to_intake_m: number | null;
  distance_to_settlement_m: number | null;
  severity_bump: number;
  formula: string;
};

export type PriorityList = Stamp & {
  status: string;
  reason: string | null;
  sites: PrioritySite[];
};

export type TrendSeries = Stamp & {
  zone_id: string;
  indicator: string;
  points: {
    date: string;
    value: number | null;
    baseline_mean: number | null;
    baseline_std: number | null;
    status: string;
  }[];
};

export type FeatureCollection = {
  type: "FeatureCollection";
  features: { type: string; properties: Record<string, unknown>; geometry: { type: string; coordinates: unknown } }[];
  status?: string;
  reason?: string | null;
  scene_extent_m2?: number | null;
};

export type MapZones = Stamp & {
  date: FeatureCollection & Stamp;
  compare?: FeatureCollection & Stamp;
};

export type AssistantAnswer = Stamp & {
  answer: string;
  source_ids: string[];
  passages: { source_id: string; title: string; text: string }[];
  evidence_id: string | null;
  grounded: boolean;
};

export type Leaderboard = Stamp & { entries: { user_id: string; credits: number }[] };

export type CreditVerdict = Stamp & {
  report_id: string;
  accepted: boolean;
  reason: string;
  credits_awarded: number;
  zone_id: string | null;
  severity_bump: number;
  total_credits: number;
};

export type StressResponse = Stamp & {
  status: string;
  reason: string | null;
  anomalies: AnomalyResponse | null;
  alerts: AlertFeed | null;
  evidence: EvidenceCard[];
  priority: PriorityList | null;
};

function assertStamp(value: unknown): asserts value is Stamp {
  if (!value || typeof value !== "object") {
    throw new Error("Empty response");
  }
  const row = value as Partial<Stamp>;
  if (typeof row.confidence !== "number" || typeof row.disclaimer !== "string" || row.lab_verification_required !== true) {
    throw new Error("Response is missing a confidence score or the lab-verification disclaimer");
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const payload = (await response.json()) as T;
  assertStamp(payload);
  if (!response.ok) {
    const reason = (payload as { reason?: string }).reason || response.statusText;
    throw new Error(reason);
  }
  return payload;
}

export const getScenes = () => request<SceneIndex>("/api/scenes");
export const getAnomalies = (id: string, date: string) => request<AnomalyResponse>(`/api/anomalies/${id}/${date}`);
export type EvidenceIndicator = {
  indicator: string;
  value: number;
  baseline_mean: number;
  baseline_std: number | null;
  sigma: number | null;
  threshold: number;
  crossed: boolean;
  unit: string;
};

export type AlertEvidenceCard = Stamp & {
  alert_id: string;
  water_body_id: string;
  zone_id: string;
  datetime: string;
  valid_pixel_fraction: number | null;
  mask_agreement: number | null;
  thresholds_crossed: string[];
  contributing_indicators: EvidenceIndicator[];
  indicators: EvidenceIndicator[];
  summary: string;
};

export type SeriesAlert = Stamp & {
  id: string;
  water_body_id: string;
  zone_id: string;
  datetime: string;
  affected_region: string;
  indicators: string[];
  severity: "low" | "med" | "high";
  template: string;
};

export type SeriesAlertList = Stamp & { alerts: SeriesAlert[] };

export const getAlerts = (id: string, date: string) => request<AlertFeed>(`/api/alerts/${id}/${date}`);
export const getSeriesAlerts = () => request<SeriesAlertList>("/api/alerts");
export const getAlertEvidence = (alertId: string) =>
  request<AlertEvidenceCard>(`/api/alerts/${encodeURIComponent(alertId)}/evidence`);
export const getEvidence = (id: string, zone: string, date: string) =>
  request<EvidenceCard>(`/api/explain/${id}/${zone}/${date}`);
export const getPriority = (id: string, date: string) => request<PriorityList>(`/api/priority/${id}/${date}`);
export const getTrends = (id: string, zone: string, indicator: string) =>
  request<TrendSeries>(`/api/maps/${id}/trends?zone_id=${encodeURIComponent(zone)}&indicator=${indicator}`);
export const getZones = (id: string, date: string, compare?: string) => {
  const query = new URLSearchParams({ date });
  if (compare) query.set("compare", compare);
  return request<MapZones>(`/api/maps/${id}/zones?${query.toString()}`);
};
export const askAssistant = (question: string, waterBodyId?: string, zoneId?: string, date?: string) =>
  request<AssistantAnswer>("/api/assistant", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, water_body_id: waterBodyId, zone_id: zoneId, date }),
  });
export const getLeaderboard = () => request<Leaderboard>("/api/credits/leaderboard");

export async function submitPhoto(form: FormData): Promise<CreditVerdict> {
  return request<CreditVerdict>("/api/credits/reports", { method: "POST", body: form });
}

export const runStress = (body: {
  water_body_id: string;
  date: string;
  lon: number;
  lat: number;
  radius_m: number;
  indicator: string;
  magnitude: number;
}) =>
  request<StressResponse>("/api/stress/plume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
