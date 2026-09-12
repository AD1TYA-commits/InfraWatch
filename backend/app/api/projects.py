from datetime import datetime, timezone
from pathlib import Path
import time
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.config import settings
from app.models.models import Project, SatelliteObservation, AIResult, Anomaly
from app.schemas.schemas import (
    AnalysisResultOut, EvidenceOut, IngestResultOut, KPISummary, ProjectCreateIn, ProjectOut,
    ProjectSummary, SceneOut, BoundingBox, AIAnalysis, AIUsage, AIChangeItem,
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

logger = logging.getLogger("infrawatch.api.projects")
router = APIRouter(prefix="/api/projects", tags=["projects"])


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
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.id).all()
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
        )
        for p in projects
    ]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreateIn, db: Session = Depends(get_db)):
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
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/kpi-summary", response_model=KPISummary)
def kpi_summary(db: Session = Depends(get_db)):
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

    db.query(AIResult).filter(AIResult.project_id == project.id).delete()
    db.query(Anomaly).filter(Anomaly.project_id == project.id).delete()
    db.query(SatelliteObservation).filter(SatelliteObservation.project_id == project.id).delete()

    if raw.get("error"):
        logger.warning(f"satellite-service returned no result for project #{project.id}: {raw['error']}")
        db.add(Anomaly(
            project_id=project.id,
            type="satellite_service_unavailable",
            score=0.0,
            severity="watch",
            explanation=raw["error"],
        ))
        project.status = "watch"
        project.is_demo = 0
        db.commit()

        empty_scene = SceneOut(
            scene_id="n/a", acquisition_date=datetime.now(timezone.utc), source="n/a", image_url="",
        )
        return AnalysisResultOut(
            reported_progress=project.reported_progress,
            observable_change_percent=0.0,
            changed_pixel_count=0,
            total_pixel_count=0,
            bounding_boxes=[],
            recommendation="Field verification recommended",
            explanation=raw["error"],
            before_image_url="",
            after_image_url="",
            change_mask_url="",
            change_overlay_url="",
            is_synthetic_demo=False,
            method="satellite-service (no result — see explanation)",
            t1_scene=empty_scene,
            t2_scene=empty_scene,
            candidate_count=0,
            analyzed_candidate_count=0,
            ai_model="n/a",
            ai_analysis=AIAnalysis(
                change_detected=False, construction_related=False, confidence=0.0,
                summary=raw["error"], changes=[], false_positive_risks=[],
            ),
            ai_usage=AIUsage(model="n/a", input_tokens=0, output_tokens=0),
            geojson_overlay=None,
            analysis_timestamp=datetime.now(timezone.utc),
            processing_duration_sec=duration,
        )

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
    else:
        # Real (non-demo) projects are analyzed by the standalone satellite-service
        # microservice (separate repo/folder) instead of the legacy in-process
        # Sentinel2Provider/EsriProvider/ChangeDetector/SatelliteChangeAnalyzer chain
        # below — that chain now only runs for bundled demo image pairs. See
        # satellite-service/docs/04-integration.md for the full contract.
        return _execute_via_satellite_service(project, db, start_time)

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
def ingest_real_imagery(project_id: int, db: Session = Depends(get_db)):
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
def analyze_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    try:
        return execute_pipeline(project, db)
    except Exception as exc:
        logger.error(f"Analysis failed for project {project_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Satellite analysis error: {exc}") from exc


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


@router.get("/{project_id}/evidence", response_model=EvidenceOut)
def project_evidence(project_id: int, db: Session = Depends(get_db)):
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
