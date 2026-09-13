export type RiskStatus = "normal" | "watch" | "medium" | "least" | "high" | "critical";
export type EvidenceSource = "satellite" | "manual_upload" | "unavailable";
export type UserRole = "analyst" | "contractor";

export interface ProjectSummary {
  id: number;
  name: string;
  project_type: string;
  latitude: number | null;
  longitude: number | null;
  reported_progress: number;
  status: RiskStatus;
  latest_image_url?: string | null;
  work_id?: string | null;
  state_name?: string | null;
  district_name?: string | null;
  evidence_source: EvidenceSource;
  data_source?: string | null;
}

export interface User {
  id: number;
  email: string;
  role: UserRole;
  full_name: string;
  organization?: string | null;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RiskFactor {
  name: string;
  score: number;
  weight: number;
  explanation: string;
}

export interface Risk {
  project_id: number;
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  factors: RiskFactor[];
  duplicate_candidates: Record<string, unknown>[];
}

export interface Milestone {
  id: number;
  milestone_date: string;
  expected_progress: number;
  description: string;
}

export interface FinancialRecord {
  id: number;
  date: string;
  amount: number;
  category: string;
}

export interface SatelliteObservation {
  id: number;
  acquisition_date: string;
  source: string;
  image_reference: string;
  cloud_percentage: number | null;
  processing_status: string;
}

export interface AIResult {
  id: number;
  changed_area: number | null;
  observed_progress: number | null;
  confidence: number | null;
  model_version: string;
}

export interface Anomaly {
  id: number;
  type: string;
  score: number;
  severity: string;
  explanation: string;
  created_at: string | null;
}

export interface ProjectDetail extends ProjectSummary {
  description: string;
  start_date: string | null;
  expected_end_date: string | null;
  approved_cost: number | null;
  is_demo: boolean;
  milestones?: Milestone[];
  financial_records?: FinancialRecord[];
  satellite_observations?: SatelliteObservation[];
  ai_results?: AIResult[];
  anomalies?: Anomaly[];
}

export interface KPISummary {
  total_projects: number;
  normal: number;
  watch: number;
  high: number;
  critical: number;
}

export interface SceneMeta {
  scene_id?: string;
  acquisition_date: string;
  source: string;
  image_url: string;
  cloud_percentage?: number | null;
  bbox?: number[];
  crs?: string;
}

export interface AIChangeItem {
  type: string;
  confidence: number;
  description: string;
}

export interface AIUsage {
  model: string;
  input_tokens?: number;
  output_tokens?: number;
}

export interface AIAnalysis {
  change_detected: boolean;
  construction_related: boolean;
  confidence: number;
  summary: string;
  changes: AIChangeItem[];
  false_positive_risks: string[];
}

export interface GeoJSONFeature {
  type: "Feature";
  id?: string;
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
  properties: {
    candidate_id: string;
    change_type: string;
    confidence: number;
    cv_confidence: number;
    ai_confidence: number;
    estimated_area_m2: number;
    pixel_area?: number;
    detection_date?: string;
    label: string;
  };
}

export interface GeoJSONFeatureCollection {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
}

export interface AnalysisResult {
  reported_progress: number;
  observable_change_percent: number;
  changed_pixel_count: number;
  total_pixel_count: number;
  bounding_boxes: { x: number; y: number; width: number; height: number }[];
  recommendation: string;
  explanation: string;
  before_image_url: string;
  after_image_url: string;
  change_mask_url: string;
  change_overlay_url: string;
  is_synthetic_demo: boolean;
  method: string;
  t1_scene?: SceneMeta;
  t2_scene?: SceneMeta;
  candidate_count?: number;
  analyzed_candidate_count?: number;
  ai_model?: string;
  ai_analysis?: AIAnalysis;
  ai_usage?: AIUsage;
  geojson_overlay?: GeoJSONFeatureCollection;
  analysis_timestamp?: string;
  processing_duration_sec?: number;
}

export interface Evidence {
  project_id: number;
  project_name: string;
  reported_progress: number;
  observable_change_percent: number | null;
  discrepancy_points: number | null;
  severity: string | null;
  recommendation: string;
  explanation: string;
  generated_at: string;
  is_synthetic_demo: boolean;
}
