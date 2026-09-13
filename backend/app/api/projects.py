from datetime import datetime, timezone
from pathlib import Path
import shutil
import time
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.config import settings
from app.auth import get_current_user, require_role
from app.models.models import Project, SatelliteObservation, AIResult, Anomaly, User
from app.schemas.schemas import (
    AnalysisResultOut, EvidenceOut, IngestResultOut, KPISummary, ManualEvidenceOut,
    ProjectCreateIn, ProjectOut, ProjectSummary, RiskOut, RiskFactorOut,
    SceneOut, BoundingBox, AIAnalysis, AIUsage, AIChangeItem,
)
import cv2
from rasterio.transform import from_bounds
from app.satellite_provider import SatelliteScene
from app.imagery_processor import ImageryProcessor, ProcessedImagery
from app.change_detector import ChangeDetector
from app.change_crops import CandidateCropGenerator
from app.change_analyzer import SatelliteChangeAnalyzer
from app.geo_processor import ChangeGeoProcessor
from app.satellite_service_client import (
    run_pipeline as satellite_service_run_pipeline,
    SatelliteServiceError,
    asset_url as satellite_asset_url,
)
from app.manual_evidence_client import detect_images as manual_detect_images, ManualEvidenceError
from app import risk_engine

logger = logging.getLogger("infrawatch.api.projects")
router = APIRouter(prefix="/api/projects", tags=["projects"])

MANUAL_EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "manual_evidence"


def _manual_evidence_url(relative_path: str) -> str:
    return f"/manual-evidence/{relative_path}"


def _latest_image_url(db: Session, project_id: int) -> Optional[str]:
    """Most recent satellite observation's image, as a URL the frontend can
    hotlink directly — whether it's a bundled demo asset (served by this
    backend at /demo-assets/) or a real satellite-service result (served by
    that separate microservice at its own host)."""
    obs = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.project_id == project_id)
        .order_by(SatelliteObservation.id.desc())
        .first()
    )
    if not obs:
        return None
    if obs.image_reference.startswith("data/"):
        return satellite_asset_url(obs.image_reference)
    return f"/demo-assets/{obs.image_reference}"


@router.get("", response_model=List[ProjectSummary])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = 1,
    page_size: int = 50,
    data_source: Optional[str] = None,
    evidence_source: Optional[str] = None,
):
    """Registry list. `page`/`page_size` paginate (real datasets run to
    1,000+ rows); `data_source` filters to one ingestion source (e.g.
    "india-mplads-works", "pmgsy-geosadak"); `evidence_source` filters to
    "satellite" | "manual_upload" | "unavailable"."""
    query = db.query(Project)
    if data_source:
        query = query.filter(Project.data_source == data_source)
    if evidence_source:
        query = query.filter(Project.evidence_source == evidence_source)

    page = max(1, page)
    page_size = max(1, min(page_size, 500))
    projects = (
        query.order_by(Project.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [
        ProjectSummary(
            id=p.id,
            name=p.name,
            project_type=p.project_type,
            latitude=p.latitude,
            longitude=p.longitude,
            reported_progress=p.reported_progress,
            status=p.status,
            latest_image_url=_latest_image_url(db, p.id),
            work_id=p.work_id,
            state_name=p.state_name,
            district_name=p.district_name,
            evidence_source=p.evidence_source,
            data_source=p.data_source,
        )
        for p in projects
    ]


@router.get("/mine", response_model=List[ProjectSummary])
def list_my_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("contractor")),
):
    """A contractor's own registered/uploaded projects."""
    projects = db.query(Project).filter(Project.owner_user_id == current_user.id).order_by(Project.id).all()
    return [
        ProjectSummary(
            id=p.id, name=p.name, project_type=p.project_type, latitude=p.latitude, longitude=p.longitude,
            reported_progress=p.reported_progress, status=p.status, latest_image_url=_latest_image_url(db, p.id),
            work_id=p.work_id, state_name=p.state_name, district_name=p.district_name,
            evidence_source=p.evidence_source, data_source=p.data_source,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("contractor")),
):
    """Register a new project. Coordinates are mandatory here on purpose —
    every NEW project gets real satellite screening from day one; only
    legacy projects (imported without coordinates, before this rule existed)
    fall back to manual evidence upload."""
    project = Project(
        name=payload.name,
        project_type=payload.project_type,
        description=payload.description,
        latitude=payload.latitude,
        longitude=payload.longitude,
        geometry_wkt=f"POINT({payload.longitude} {payload.latitude})",
        reported_progress=payload.reported_progress,
        approved_cost=payload.approved_cost,
        start_date=payload.start_date,
        expected_end_date=payload.expected_end_date,
        status="normal",
        is_demo=0,
        evidence_source="satellite",
        owner_user_id=current_user.id,
        data_source="contractor-registered",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/kpi-summary", response_model=KPISummary)
def kpi_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    counts = {"normal": 0, "watch": 0, "high": 0, "critical": 0}
    rows = db.query(Project.status, func.count(Project.id)).group_by(Project.status).all()
    total = 0
    for status, count in rows:
        total += count
        st = (status or "").lower().strip()
        if st in ("least", "high", "critical"):
            counts["high"] += count
        elif st in ("medium", "watch", "review"):
            counts["watch"] += count
        elif st in ("normal",):
            counts["normal"] += count
        elif st in counts:
            counts[st] += count
    return KPISummary(
        total_projects=total, normal=counts["normal"], watch=counts["watch"],
        high=counts["high"], critical=counts["critical"]
    )


def _unavailable_result(project: Project, db: Session, start_time: float, reason: str) -> AnalysisResultOut:
    """Shared honest 'nothing to screen with (yet)' response — used both when
    satellite-service can't be reached / finds no imagery, and when a project
    simply has no coordinate and no manual evidence. Not an error state from
    the project's point of view; just an accurate status."""
    db.query(AIResult).filter(AIResult.project_id == project.id).delete()
    db.query(Anomaly).filter(Anomaly.project_id == project.id).delete()
    db.query(SatelliteObservation).filter(SatelliteObservation.project_id == project.id).delete()
    db.add(Anomaly(
        project_id=project.id, type="evidence_unavailable", score=0.0, severity="watch", explanation=reason,
    ))
    project.status = "watch"
    project.is_demo = 0
    db.commit()

    duration = round(time.time() - start_time, 2)
    empty_scene = SceneOut(scene_id="n/a", acquisition_date=datetime.now(timezone.utc), source="n/a", image_url="")
    return AnalysisResultOut(
        reported_progress=project.reported_progress,
        observable_change_percent=0.0,
        changed_pixel_count=0,
        total_pixel_count=0,
        bounding_boxes=[],
        recommendation="Field verification recommended",
        explanation=reason,
        before_image_url="",
        after_image_url="",
        change_mask_url="",
        change_overlay_url="",
        is_synthetic_demo=False,
        method="unavailable",
        t1_scene=empty_scene,
        t2_scene=empty_scene,
        candidate_count=0,
        analyzed_candidate_count=0,
        ai_model="n/a",
        ai_analysis=AIAnalysis(
            change_detected=False, construction_related=False, confidence=0.0,
            summary=reason, changes=[], false_positive_risks=[],
        ),
        ai_usage=AIUsage(model="n/a", input_tokens=0, output_tokens=0),
        geojson_overlay=None,
        analysis_timestamp=datetime.now(timezone.utc),
        processing_duration_sec=duration,
    )


def _execute_via_satellite_service(project: Project, db: Session, start_time: float) -> AnalysisResultOut:
    """Real (non-demo) satellite analysis, delegated to the standalone
    satellite-service microservice: real Sentinel-2 band fetch + pretrained
    CNN feature-diff change detection + Gemini/template narration.

    On a transport failure (service unreachable) or a normal "no imagery
    available for this AOI" outcome, this records a watch-severity anomaly
    explaining why, instead of crashing the request — mirroring how the old
    Esri-fallback path used to degrade gracefully.
    """
    try:
        raw = satellite_service_run_pipeline(
            project_id=project.id,
            name=project.name,
            latitude=project.latitude,
            longitude=project.longitude,
            project_type=project.project_type,
            reported_progress=project.reported_progress,
        )
    except SatelliteServiceError as exc:
        raw = {"error": str(exc)}

    duration = round(time.time() - start_time, 2)

    if raw.get("error"):
        logger.warning(f"satellite-service returned no result for project #{project.id}: {raw['error']}")
        return _unavailable_result(project, db, start_time, raw["error"])

    db.query(AIResult).filter(AIResult.project_id == project.id).delete()
    db.query(Anomaly).filter(Anomaly.project_id == project.id).delete()
    db.query(SatelliteObservation).filter(SatelliteObservation.project_id == project.id).delete()

    # SQLAlchemy DateTime columns need real datetime objects — the satellite-service
    # response carries dates as ISO strings (they crossed a JSON/HTTP boundary).
    t1_acq_dt = datetime.fromisoformat(raw["t1_scene"]["acquisition_date"])
    t2_acq_dt = datetime.fromisoformat(raw["t2_scene"]["acquisition_date"])

    t1_scene_out = SceneOut(
        scene_id=raw["t1_scene"]["scene_id"],
        acquisition_date=t1_acq_dt,
        source="sentinel-2-l2a (satellite-service)",
        image_url=satellite_asset_url(raw["before_image_path"]),
        cloud_percentage=raw["t1_scene"]["cloud_percentage"],
        bbox=raw["t1_scene"]["bbox"],
        crs="EPSG:4326",
    )
    t2_scene_out = SceneOut(
        scene_id=raw["t2_scene"]["scene_id"],
        acquisition_date=t2_acq_dt,
        source="sentinel-2-l2a (satellite-service)",
        image_url=satellite_asset_url(raw["after_image_path"]),
        cloud_percentage=raw["t2_scene"]["cloud_percentage"],
        bbox=raw["t2_scene"]["bbox"],
        crs="EPSG:4326",
    )

    obs1 = SatelliteObservation(
        project_id=project.id, acquisition_date=t1_acq_dt,
        source=t1_scene_out.source, image_reference=raw["before_image_path"],
        cloud_percentage=raw["t1_scene"]["cloud_percentage"], processing_status="ready",
    )
    obs2 = SatelliteObservation(
        project_id=project.id, acquisition_date=t2_acq_dt,
        source=t2_scene_out.source, image_reference=raw["after_image_path"],
        cloud_percentage=raw["t2_scene"]["cloud_percentage"], processing_status="ready",
    )
    db.add_all([obs1, obs2])
    db.flush()

    obs_change = raw["observable_change_percent"]
    rep_prog = project.reported_progress
    if rep_prog >= 70 and obs_change < 3.0:
        recommendation, severity = "Field verification recommended", "field_verification"
        explanation = (
            f"High reported progress ({rep_prog}%) is paired with low observable change ({obs_change}%). "
            "Field verification recommended."
        )
    elif rep_prog >= 70 and obs_change >= 10.0:
        recommendation, severity = "No significant discrepancy", "normal"
        explanation = f"High reported progress ({rep_prog}%) is supported by substantial observable ground activity ({obs_change}%)."
    else:
        recommendation, severity = "Review recommended", "watch"
        explanation = f"Reported progress ({rep_prog}%) and observable change ({obs_change}%) require regular program review."

    explanation_out = raw["explanation"]
    changes = explanation_out.get("changes", [])
    construction_related = any(
        "construction" in ch.get("type", "") or "built_up" in ch.get("type", "") for ch in changes
    )
    ai_analysis = AIAnalysis(
        change_detected=explanation_out["change_detected"],
        construction_related=construction_related,
        confidence=explanation_out["confidence"],
        summary=explanation_out["summary"],
        changes=[AIChangeItem(type=ch["type"], confidence=ch["confidence"], description=ch["description"]) for ch in changes],
        false_positive_risks=(
            ["Cloud cover, shadow, or seasonal vegetation variation not fully excluded"] if changes else []
        ),
    )

    db.add(AIResult(
        project_id=project.id, observation_a=obs1.id, observation_b=obs2.id,
        changed_area=float(raw["changed_pixel_count"]), observed_progress=obs_change,
        confidence=ai_analysis.confidence, model_version=raw["model_version"],
    ))
    db.add(Anomaly(
        project_id=project.id, type="observable_change_comparison",
        score=round(abs(rep_prog - obs_change), 2), severity=severity, explanation=explanation,
    ))
    project.status = severity if severity in ("normal", "watch", "high", "critical") else "watch"
    project.is_demo = 0
    project.evidence_source = "satellite"
    db.commit()

    logger.info(
        f"satellite-service pipeline complete for Project #{project.id} in {duration}s. "
        f"Candidates={raw['candidate_count']}, narrated_by={explanation_out['narrated_by']}"
    )

    return AnalysisResultOut(
        reported_progress=rep_prog,
        observable_change_percent=obs_change,
        changed_pixel_count=raw["changed_pixel_count"],
        total_pixel_count=raw["total_pixel_count"],
        bounding_boxes=[
            BoundingBox(x=c["bbox"][0], y=c["bbox"][1], width=c["bbox"][2], height=c["bbox"][3])
            for c in raw["candidates"]
        ],
        recommendation=recommendation,
        explanation=explanation,
        before_image_url=satellite_asset_url(raw["before_image_path"]),
        after_image_url=satellite_asset_url(raw["after_image_path"]),
        change_mask_url=satellite_asset_url(raw["mask_image_path"]),
        change_overlay_url=satellite_asset_url(raw["mask_image_path"]),
        is_synthetic_demo=False,
        method="satellite-service: Sentinel-2 10m bands + PlanAura CNN feature-diff + Gemini/template narration",
        t1_scene=t1_scene_out,
        t2_scene=t2_scene_out,
        candidate_count=raw["candidate_count"],
        analyzed_candidate_count=min(raw["candidate_count"], 15),
        ai_model=explanation_out["narrated_by"],
        ai_analysis=ai_analysis,
        ai_usage=AIUsage(model=explanation_out["narrated_by"], input_tokens=None, output_tokens=None),
        geojson_overlay=raw["geojson_overlay"],
        analysis_timestamp=datetime.now(timezone.utc),
        processing_duration_sec=duration,
    )


def _execute_via_manual_evidence(project: Project, db: Session, start_time: float) -> AnalysisResultOut:
    """Re-run detection on already-uploaded manual evidence (see
    /evidence/upload for how these files got here). Uses the exact same
    PlanAura model as the satellite path, via satellite-service's
    /model/detect-images — this is real model output, not a fabricated number,
    even though the source photos aren't a georeferenced satellite pass."""
    latest = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.project_id == project.id, SatelliteObservation.source == "manual-upload")
        .order_by(SatelliteObservation.id.desc())
        .limit(2)
        .all()
    )
    if len(latest) < 2:
        return _unavailable_result(
            project, db, start_time,
            "This project is marked for manual evidence but no before/after images "
            "have been uploaded yet.",
        )
    # SatelliteObservation rows are inserted before/after in that order; DB id
    # descending gives [after, before].
    after_obs, before_obs = latest[0], latest[1]
    before_path = MANUAL_EVIDENCE_DIR / before_obs.image_reference
    after_path = MANUAL_EVIDENCE_DIR / after_obs.image_reference

    try:
        raw = manual_detect_images(before_path, after_path, latitude=project.latitude, longitude=project.longitude)
    except ManualEvidenceError as exc:
        return _unavailable_result(project, db, start_time, str(exc))

    duration = round(time.time() - start_time, 2)

    db.query(AIResult).filter(AIResult.project_id == project.id).delete()
    db.query(Anomaly).filter(Anomaly.project_id == project.id).delete()

    obs_change = raw["observable_change_percent"]
    rep_prog = project.reported_progress
    if rep_prog >= 70 and obs_change < 3.0:
        recommendation, severity = "Field verification recommended", "field_verification"
        explanation = f"High reported progress ({rep_prog}%) is paired with low observable change ({obs_change}%) in the manually-supplied evidence."
    elif rep_prog >= 70 and obs_change >= 10.0:
        recommendation, severity = "No significant discrepancy", "normal"
        explanation = f"High reported progress ({rep_prog}%) is supported by substantial observable change ({obs_change}%) in the manually-supplied evidence."
    else:
        recommendation, severity = "Review recommended", "watch"
        explanation = f"Reported progress ({rep_prog}%) and observed change ({obs_change}%) require regular review."

    db.add(AIResult(
        project_id=project.id, observation_a=before_obs.id, observation_b=after_obs.id,
        changed_area=float(raw["changed_pixel_count"]), observed_progress=obs_change,
        confidence=0.6, model_version=raw["model_version"],
    ))
    db.add(Anomaly(
        project_id=project.id, type="observable_change_comparison",
        score=round(abs(rep_prog - obs_change), 2), severity=severity, explanation=explanation,
    ))
    project.status = severity if severity in ("normal", "watch", "high", "critical") else "watch"
    db.commit()

    before_url = _manual_evidence_url(before_obs.image_reference)
    after_url = _manual_evidence_url(after_obs.image_reference)

    return AnalysisResultOut(
        reported_progress=rep_prog,
        observable_change_percent=obs_change,
        changed_pixel_count=raw["changed_pixel_count"],
        total_pixel_count=raw["total_pixel_count"],
        bounding_boxes=[
            BoundingBox(x=c["bbox"][0], y=c["bbox"][1], width=c["bbox"][2], height=c["bbox"][3])
            for c in raw["candidates"]
        ],
        recommendation=recommendation,
        explanation=explanation,
        before_image_url=before_url,
        after_image_url=after_url,
        change_mask_url="",
        change_overlay_url="",
        is_synthetic_demo=False,
        method="Manually-supplied before/after evidence + PlanAura CNN feature-diff (no georeferenced satellite pass)",
        t1_scene=SceneOut(scene_id="manual-before", acquisition_date=before_obs.acquisition_date, source="manual-upload", image_url=before_url),
        t2_scene=SceneOut(scene_id="manual-after", acquisition_date=after_obs.acquisition_date, source="manual-upload", image_url=after_url),
        candidate_count=raw["candidate_count"],
        analyzed_candidate_count=raw["candidate_count"],
        ai_model=raw["model_version"],
        ai_analysis=AIAnalysis(
            change_detected=raw["candidate_count"] > 0,
            construction_related=raw["candidate_count"] > 0,
            confidence=0.6,
            summary=f"Detected {raw['candidate_count']} change region(s) covering {obs_change}% of the manually-supplied before/after images.",
            changes=[],
            false_positive_risks=["Manually-sourced imagery — capture angle, zoom, and date precision are not guaranteed like a satellite pass"],
        ),
        ai_usage=AIUsage(model=raw["model_version"], input_tokens=None, output_tokens=None),
        geojson_overlay=raw["geojson_overlay"],
        analysis_timestamp=datetime.now(timezone.utc),
        processing_duration_sec=duration,
    )


def execute_pipeline(project: Project, db: Session) -> AnalysisResultOut:
    start_time = time.time()
    logger.info(f"Executing dynamic satellite pipeline for Project #{project.id} ({project.name})")

    processor = ImageryProcessor()
    demo_b_path = processor.asset_dir / f"project_{project.id}_before.png"
    demo_a_path = processor.asset_dir / f"project_{project.id}_after.png"

    uses_demo_assets = (
        settings.satellite_mode != "real"
        and demo_b_path.exists()
        and demo_a_path.exists()
    )
    if uses_demo_assets:
        logger.info(f"Loading bundled demo image pair for Project #{project.id}")
        t1_arr = cv2.imread(str(demo_b_path))
        t2_arr = cv2.imread(str(demo_a_path))
        delta = 0.0025
        bounds = (project.longitude - delta, project.latitude - delta, project.longitude + delta, project.latitude + delta)
        transform = from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], 512, 512)

        t1_date = project.start_date or datetime(2024, 4, 1, tzinfo=timezone.utc)
        t2_date = datetime(2025, 2, 15, tzinfo=timezone.utc)

        t1_scene = SatelliteScene(
            scene_id=f"demo-t1-{project.id}",
            acquisition_date=t1_date,
            cloud_percentage=0.0,
            source="bundled-demo-image",
            image_href=f"/demo-assets/{demo_b_path.name}",
            bbox=bounds,
            crs="EPSG:4326",
            resolution=0.5,
        )
        t2_scene = SatelliteScene(
            scene_id=f"demo-t2-{project.id}",
            acquisition_date=t2_date,
            cloud_percentage=0.0,
            source="bundled-demo-image",
            image_href=f"/demo-assets/{demo_a_path.name}",
            bbox=bounds,
            crs="EPSG:4326",
            resolution=0.5,
        )
        processed = ProcessedImagery(
            t1_array=t1_arr,
            t2_array=t2_arr,
            transform=transform,
            crs="EPSG:4326",
            bounds=bounds,
            t1_scene=t1_scene,
            t2_scene=t2_scene,
            t1_image_path=demo_b_path,
            t2_image_path=demo_a_path,
        )
    elif project.evidence_source == "manual_upload":
        # Legacy project with no usable coordinate — a contractor supplied
        # before/after photos instead (see /evidence/upload). Re-run detection
        # on the stored files (same real model, via satellite-service).
        return _execute_via_manual_evidence(project, db, start_time)
    elif project.latitude is not None and project.longitude is not None:
        # Real (non-demo) projects are analyzed by the standalone satellite-service
        # microservice (separate repo/folder) instead of the legacy in-process
        # Sentinel2Provider/EsriProvider/ChangeDetector/SatelliteChangeAnalyzer chain
        # below — that chain now only runs for bundled demo image pairs. See
        # satellite-service/docs/04-integration.md for the full contract.
        return _execute_via_satellite_service(project, db, start_time)
    else:
        # Honest terminal state: no coordinate, and no manual evidence uploaded
        # yet. This is common for bulk-imported real government records (most
        # published datasets don't include GPS) — it is not an error, just an
        # accurate "nothing to screen with yet" status.
        return _unavailable_result(
            project, start_time,
            "No GPS coordinate is on record for this project, and no before/after "
            "evidence has been uploaded yet. This project cannot be satellite-screened "
            "until either becomes available — see the Contractor evidence-upload flow.",
        )

    # 3. Local Computer Vision Candidate Region Change Detector
    detector = ChangeDetector(min_cv_confidence=settings.ai_min_cv_confidence)
    detection = detector.detect(
        t1=processed.t1_array,
        t2=processed.t2_array,
        project_id=project.id,
        asset_dir=processor.asset_dir,
    )

    # 4. Candidate Crop Extraction (Cost-optimized for Vision AI input)
    crop_generator = CandidateCropGenerator(
        context_margin=settings.ai_context_margin,
        max_candidates=settings.ai_max_candidates,
    )
    crops = crop_generator.generate_crops(
        t1=processed.t1_array,
        t2=processed.t2_array,
        candidates=detection.candidates,
    )

    # 5. Gemini 2.5 Flash-Lite Vision AI Analyzer
    analyzer = SatelliteChangeAnalyzer()
    analyzer_output = analyzer.analyze_candidates(
        crops=crops,
        t1_date=t1_scene.acquisition_date,
        t2_date=t2_scene.acquisition_date,
        project_name=project.name,
        project_type=project.project_type,
    )

    # 6. GeoJSON Converter (candidate pixel coords -> EPSG:4326 polygons)
    geo_processor = ChangeGeoProcessor()
    geojson_overlay = geo_processor.candidates_to_geojson(
        candidates=detection.candidates,
        transform=processed.transform,
        candidate_statuses=analyzer_output.candidate_statuses,
        detection_date=t2_scene.acquisition_date.isoformat(),
    )

    # 7. Update Database Observations & Anomaly Evidence Records
    db.query(AIResult).filter(AIResult.project_id == project.id).delete()
    db.query(Anomaly).filter(Anomaly.project_id == project.id).delete()
    db.query(SatelliteObservation).filter(SatelliteObservation.project_id == project.id).delete()

    obs1 = SatelliteObservation(
        project_id=project.id,
        acquisition_date=t1_scene.acquisition_date,
        source=t1_scene.source,
        image_reference=processed.t1_image_path.name,
        cloud_percentage=t1_scene.cloud_percentage,
        processing_status="ready",
    )
    obs2 = SatelliteObservation(
        project_id=project.id,
        acquisition_date=t2_scene.acquisition_date,
        source=t2_scene.source,
        image_reference=processed.t2_image_path.name,
        cloud_percentage=t2_scene.cloud_percentage,
        processing_status="ready",
    )
    db.add_all([obs1, obs2])
    db.flush()

    # Determine recommendation & severity
    obs_change = detection.observable_change_percent
    rep_prog = project.reported_progress
    if rep_prog >= 70 and obs_change < 3.0:
        recommendation = "Field verification recommended"
        severity = "field_verification"
        explanation = (
            f"High reported progress ({rep_prog}%) is paired with low observable change ({obs_change}%). "
            "Field verification recommended."
        )
    elif rep_prog >= 70 and obs_change >= 10.0:
        recommendation = "No significant discrepancy"
        severity = "normal"
        explanation = (
            f"High reported progress ({rep_prog}%) is supported by substantial observable ground activity ({obs_change}%)."
        )
    else:
        recommendation = "Review recommended"
        severity = "watch"
        explanation = (
            f"Reported progress ({rep_prog}%) and observable change ({obs_change}%) require regular program review."
        )

    db.add(
        AIResult(
            project_id=project.id,
            observation_a=obs1.id,
            observation_b=obs2.id,
            changed_area=float(detection.changed_pixel_count),
            observed_progress=obs_change,
            confidence=analyzer_output.analysis.confidence,
            model_version=f"{settings.ai_vision_provider}:{settings.ai_vision_model}",
        )
    )
    db.add(
        Anomaly(
            project_id=project.id,
            type="observable_change_comparison",
            score=round(abs(rep_prog - obs_change), 2),
            severity=severity,
            explanation=explanation,
        )
    )
    project.status = severity if severity in ("normal", "watch", "high", "critical") else "watch"
    project.evidence_source = "satellite"
    if not uses_demo_assets:
        project.is_demo = 0
    db.commit()

    duration = round(time.time() - start_time, 2)
    logger.info(
        f"Pipeline complete for Project #{project.id} in {duration}s. Candidates={len(detection.candidates)}, AI={analyzer_output.analysis.summary}"
    )

    base = "/demo-assets/"
    t1_scene_out = SceneOut(
        scene_id=t1_scene.scene_id,
        acquisition_date=t1_scene.acquisition_date,
        source=t1_scene.source,
        image_url=f"{base}{processed.t1_image_path.name}",
        cloud_percentage=t1_scene.cloud_percentage,
        bbox=list(t1_scene.bbox),
        crs=t1_scene.crs,
    )
    t2_scene_out = SceneOut(
        scene_id=t2_scene.scene_id,
        acquisition_date=t2_scene.acquisition_date,
        source=t2_scene.source,
        image_url=f"{base}{processed.t2_image_path.name}",
        cloud_percentage=t2_scene.cloud_percentage,
        bbox=list(t2_scene.bbox),
        crs=t2_scene.crs,
    )

    boxes = [BoundingBox(x=c.bbox[0], y=c.bbox[1], width=c.bbox[2], height=c.bbox[3]) for c in detection.candidates]

    return AnalysisResultOut(
        reported_progress=rep_prog,
        observable_change_percent=obs_change,
        changed_pixel_count=detection.changed_pixel_count,
        total_pixel_count=detection.total_pixel_count,
        bounding_boxes=boxes,
        recommendation=recommendation,
        explanation=explanation,
        before_image_url=f"{base}{processed.t1_image_path.name}",
        after_image_url=f"{base}{processed.t2_image_path.name}",
        change_mask_url=f"{base}{detection.mask_path.name}",
        change_overlay_url=f"{base}{detection.overlay_path.name}",
        is_synthetic_demo=uses_demo_assets,
        method=f"Local OpenCV differencing with {analyzer_output.usage.model} and GeoJSON overlay",
        t1_scene=t1_scene_out,
        t2_scene=t2_scene_out,
        candidate_count=len(detection.candidates),
        analyzed_candidate_count=len(crops),
        ai_model=analyzer_output.usage.model,
        ai_analysis=analyzer_output.analysis,
        ai_usage=analyzer_output.usage,
        geojson_overlay=geojson_overlay,
        analysis_timestamp=datetime.now(timezone.utc),
        processing_duration_sec=duration,
    )


@router.post("/{project_id}/ingest", response_model=IngestResultOut)
def ingest_real_imagery(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    try:
        res = execute_pipeline(project, db)
        return IngestResultOut(
            mode="demo" if res.is_synthetic_demo else "real",
            scenes=[res.t1_scene, res.t2_scene],
            message=f"Analyzed image pair ({res.t1_scene.source}).",
        )
    except Exception as exc:
        logger.error(f"Ingestion failed for project {project_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"Satellite ingestion failed: {exc}") from exc


@router.post("/{project_id}/analyze", response_model=AnalysisResultOut)
def analyze_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    try:
        return execute_pipeline(project, db)
    except Exception as exc:
        logger.error(f"Analysis failed for project {project_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Satellite analysis error: {exc}") from exc


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


@router.get("/{project_id}/evidence", response_model=EvidenceOut)
def project_evidence(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    result = db.query(AIResult).filter(AIResult.project_id == project_id).order_by(AIResult.id.desc()).first()
    anomaly = db.query(Anomaly).filter(Anomaly.project_id == project_id).order_by(Anomaly.id.desc()).first()

    if not result or not anomaly:
        # Auto-trigger pipeline if no evidence exists
        res = execute_pipeline(project, db)
        return EvidenceOut(
            project_id=project.id,
            project_name=project.name,
            reported_progress=project.reported_progress,
            observable_change_percent=res.observable_change_percent,
            discrepancy_points=round(abs(project.reported_progress - res.observable_change_percent), 2),
            severity=project.status,
            recommendation=res.recommendation,
            explanation=res.explanation,
            generated_at=datetime.now(timezone.utc),
            is_synthetic_demo=project.is_demo == 1,
        )

    observable = result.observed_progress
    return EvidenceOut(
        project_id=project.id,
        project_name=project.name,
        reported_progress=project.reported_progress,
        observable_change_percent=observable,
        discrepancy_points=round(abs(project.reported_progress - observable), 2) if observable is not None else None,
        severity=anomaly.severity,
        recommendation=("Field verification recommended" if anomaly.severity == "field_verification" else "Review recommended"),
        explanation=anomaly.explanation,
        generated_at=datetime.now(timezone.utc),
        is_synthetic_demo=project.is_demo == 1,
    )


def _guess_ext(upload: UploadFile) -> str:
    name = (upload.filename or "").lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if name.endswith(ext):
            return ext
    return ".png"


@router.post("/{project_id}/evidence/upload", response_model=ManualEvidenceOut)
def upload_manual_evidence(
    project_id: int,
    before: UploadFile = File(...),
    after: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("contractor")),
):
    """Contractor uploads before/after photos for a project that has no
    usable GPS coordinate (typically a legacy record bulk-imported without
    one). Runs the same real change-detection model as the satellite path —
    see app/manual_evidence_client.py — and stores the result immediately."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    if project.owner_user_id is not None and project.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This project is owned by a different contractor account")
    if project.latitude is not None and project.longitude is not None:
        raise HTTPException(
            status_code=400,
            detail="This project already has a GPS coordinate — it is screened automatically via satellite imagery.",
        )

    project_dir = MANUAL_EVIDENCE_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    before_name = f"before{_guess_ext(before)}"
    after_name = f"after{_guess_ext(after)}"
    with open(project_dir / before_name, "wb") as f:
        shutil.copyfileobj(before.file, f)
    with open(project_dir / after_name, "wb") as f:
        shutil.copyfileobj(after.file, f)

    db.query(SatelliteObservation).filter(
        SatelliteObservation.project_id == project.id, SatelliteObservation.source == "manual-upload"
    ).delete()
    now = datetime.now(timezone.utc)
    obs_before = SatelliteObservation(
        project_id=project.id, acquisition_date=now, source="manual-upload",
        image_reference=f"{project_id}/{before_name}", processing_status="ready",
    )
    obs_after = SatelliteObservation(
        project_id=project.id, acquisition_date=now, source="manual-upload",
        image_reference=f"{project_id}/{after_name}", processing_status="ready",
    )
    db.add_all([obs_before, obs_after])
    project.evidence_source = "manual_upload"
    project.owner_user_id = project.owner_user_id or current_user.id
    db.commit()

    result = execute_pipeline(project, db)
    return ManualEvidenceOut(
        project_id=project.id,
        before_image_url=result.before_image_url,
        after_image_url=result.after_image_url,
        observable_change_percent=result.observable_change_percent,
        candidate_count=result.candidate_count,
        explanation=result.explanation,
    )


@router.get("/{project_id}/risk", response_model=RiskOut)
def project_risk(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    ai_result = db.query(AIResult).filter(AIResult.project_id == project_id).order_by(AIResult.id.desc()).first()
    observed_change = ai_result.observed_progress if ai_result else None

    candidates = []
    if project.district_name:
        others = (
            db.query(Project)
            .filter(Project.district_name == project.district_name, Project.id != project.id)
            .limit(100)
            .all()
        )
        candidates = [
            {
                "id": o.id, "description": o.description, "amount": o.sanctioned_amount,
                "category": o.project_type, "latitude": o.latitude, "longitude": o.longitude,
            }
            for o in others
        ]

    result = risk_engine.evaluate_project_risk(
        project_id=str(project.id),
        sanctioned_amount=project.sanctioned_amount,
        actual_expenditure=project.actual_expenditure,
        start_date=project.start_date,
        expected_end_date=project.expected_end_date,
        description=project.description,
        category=project.project_type,
        latitude=project.latitude,
        longitude=project.longitude,
        candidate_works=candidates,
        reported_progress=project.reported_progress,
        observed_change=observed_change,
        evidence_type=project.evidence_source,
    )

    return RiskOut(
        project_id=project.id,
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        factors=[
            RiskFactorOut(
                name=name, score=data["score"], weight=data["weight"],
                explanation=result.explanations.get(name, ""),
            )
            for name, data in result.component_breakdown.items()
        ],
        duplicate_candidates=result.duplicate_candidates,
    )
