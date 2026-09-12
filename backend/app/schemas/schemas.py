from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    milestone_date: datetime
    expected_progress: float
    description: str


class FinancialRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: datetime
    amount: float
    category: str


class SatelliteObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    acquisition_date: datetime
    source: str
    image_reference: str
    cloud_percentage: Optional[float] = None
    processing_status: str


class AIResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    changed_area: Optional[float] = None
    observed_progress: Optional[float] = None
    confidence: Optional[float] = None
    model_version: str


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    score: float
    severity: str
    explanation: str
    created_at: Optional[datetime] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    project_type: str
    description: str
    latitude: float
    longitude: float
    start_date: Optional[datetime] = None
    expected_end_date: Optional[datetime] = None
    approved_cost: Optional[float] = None
    reported_progress: float
    status: str
    is_demo: bool
    milestones: List[MilestoneOut] = []
    financial_records: List[FinancialRecordOut] = []
    satellite_observations: List[SatelliteObservationOut] = []
    ai_results: List[AIResultOut] = []
    anomalies: List[AnomalyOut] = []


class ProjectCreateIn(BaseModel):
    name: str
    project_type: str
    description: str = ""
    latitude: float
    longitude: float
    reported_progress: float = 0.0
    approved_cost: Optional[float] = None
    start_date: Optional[datetime] = None
    expected_end_date: Optional[datetime] = None


class ProjectSummary(BaseModel):
    """Lightweight shape used for the dashboard map/list."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    project_type: str
    latitude: float
    longitude: float
    reported_progress: float
    status: str
    latest_image_url: Optional[str] = None


class KPISummary(BaseModel):
    total_projects: int
    normal: int
    watch: int
    high: int
    critical: int


class HealthOut(BaseModel):
    status: str
    version: str
    database: str


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class SceneOut(BaseModel):
    scene_id: Optional[str] = None
    acquisition_date: datetime
    source: str
    image_url: str
    cloud_percentage: Optional[float] = None
    bbox: Optional[List[float]] = None
    crs: Optional[str] = None


class AIChangeItem(BaseModel):
    type: str
    confidence: float
    description: str


class AIUsage(BaseModel):
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class AIAnalysis(BaseModel):
    change_detected: bool
    construction_related: bool
    confidence: float
    summary: str
    changes: List[AIChangeItem] = []
    false_positive_risks: List[str] = []


class AnalysisResultOut(BaseModel):
    reported_progress: float
    observable_change_percent: float
    changed_pixel_count: int
    total_pixel_count: int
    bounding_boxes: List[BoundingBox]
    recommendation: str
    explanation: str
    before_image_url: str
    after_image_url: str
    change_mask_url: str
    change_overlay_url: str
    is_synthetic_demo: bool = True
    method: str
    t1_scene: Optional[SceneOut] = None
    t2_scene: Optional[SceneOut] = None
    candidate_count: int = 0
    analyzed_candidate_count: int = 0
    ai_model: Optional[str] = None
    ai_analysis: Optional[AIAnalysis] = None
    ai_usage: Optional[AIUsage] = None
    geojson_overlay: Optional[dict] = None
    analysis_timestamp: Optional[datetime] = None
    processing_duration_sec: Optional[float] = None


class IngestResultOut(BaseModel):
    mode: str
    scenes: List[SceneOut]
    message: str


class EvidenceOut(BaseModel):
    project_id: int
    project_name: str
    reported_progress: float
    observable_change_percent: Optional[float] = None
    discrepancy_points: Optional[float] = None
    severity: Optional[str] = None
    recommendation: str
    explanation: str
    generated_at: datetime
    is_synthetic_demo: bool
