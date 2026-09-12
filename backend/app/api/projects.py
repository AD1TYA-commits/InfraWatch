from datetime import datetime, timezone
from pathlib import Path
import time
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.config import settings
from app.models.models import Project, SatelliteObservation, AIResult, Anomaly
from app.schemas.schemas import (
    AnalysisResultOut, EvidenceOut, IngestResultOut, KPISummary, ProjectOut,
    ProjectSummary, SceneOut, BoundingBox, AIAnalysis, AIUsage, AIChangeItem,
)
import cv2
from rasterio.transform import from_bounds
from app.satellite_provider import Sentinel2Provider, EsriProvider, SatelliteProviderError, SatelliteScene
from app.imagery_processor import ImageryProcessor, ProcessedImagery
from app.change_detector import ChangeDetector
from app.change_crops import CandidateCropGenerator
from app.change_analyzer import SatelliteChangeAnalyzer
from app.geo_processor import ChangeGeoProcessor

logger = logging.getLogger("infrawatch.api.projects")
router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=List[ProjectSummary])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.id).all()


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
        esri_fallback = False
    else:
        # 1. Satellite Provider (Sentinel-2 L2A STAC query up to current date 2026, or Esri fallback)
        provider_used = "sentinel-2-l2a-planetary-computer"
        esri_fallback = False
        try:
            provider = Sentinel2Provider()
            t1_scene, t2_scene = provider.get_scene_pair(project.latitude, project.longitude)
        except Exception as exc:
            logger.warning(f"Sentinel-2 STAC provider failed: {exc}. Switching to Esri World Imagery export fallback.")
            fallback = EsriProvider()
            t1_scene, t2_scene = fallback.get_scene_pair(project.latitude, project.longitude)
            provider_used = EsriProvider.ESRI_FALLBACK_SOURCE
            esri_fallback = True

        # 2. Imagery Processor (streaming, cropping, reprojecting, co-registering & transform tracking)
        processed = processor.process(
            project_id=project.id,
            latitude=project.latitude,
            longitude=project.longitude,
            t1_scene=t1_scene,
            t2_scene=t2_scene,
        )

    # --- Esri fallback: no temporal data available — skip change detection — ---
    if esri_fallback:
        logger.warning(
            f"Esri fallback active for project #{project.id}: no temporal comparison available. "
            "Skipping CV change detection and AI analysis to avoid false positives."
        )
        # Persist placeholder DB records so evidence endpoint has something to return
        db.query(AIResult).filter(AIResult.project_id == project.id).delete()
        db.query(Anomaly).filter(Anomaly.project_id == project.id).delete()
        db.query(SatelliteObservation).filter(SatelliteObservation.project_id == project.id).delete()
        obs1 = SatelliteObservation(
            project_id=project.id,
            acquisition_date=t1_scene.acquisition_date,
            source=t1_scene.source,
            image_reference=processed.t1_image_path.name,
            cloud_percentage=t1_scene.cloud_percentage,
            processing_status="no_temporal_data",
        )
        obs2 = SatelliteObservation(
            project_id=project.id,
            acquisition_date=t2_scene.acquisition_date,
            source=t2_scene.source,
            image_reference=processed.t2_image_path.name,
            cloud_percentage=t2_scene.cloud_percentage,
            processing_status="no_temporal_data",
        )
        db.add_all([obs1, obs2])
        db.flush()
        db.add(AIResult(
            project_id=project.id,
            observation_a=obs1.id,
            observation_b=obs2.id,
            changed_area=0.0,
            observed_progress=0.0,
            confidence=0.0,
            model_version="esri-fallback-no-temporal",
        ))
        db.add(Anomaly(
            project_id=project.id,
            type="no_temporal_data",
            score=0.0,
            severity="watch",
            explanation=(
                "Sentinel-2 imagery could not be retrieved for this location. "
                "Esri World Imagery fallback was used, but it provides only a static mosaic — "
                "no temporal comparison is available. Field verification is recommended."
            ),
        ))
        if not project.is_demo or not project.status:
            project.status = "watch"
        project.is_demo = 0
        db.commit()

        duration = round(time.time() - start_time, 2)
        no_temporal_analysis = AIAnalysis(
            change_detected=False,
            construction_related=False,
            confidence=0.0,
            summary=(
                "No temporal comparison available: Sentinel-2 imagery could not be retrieved. "
                "Esri World Imagery is a static mosaic and cannot be used for change detection. "
                "Field verification is recommended."
            ),
            changes=[
                AIChangeItem(
                    type="no_significant_change",
                    confidence=0.0,
                    description="Change detection skipped — both T1 and T2 are the same static Esri export image.",
                )
            ],
            false_positive_risks=["Static imagery source — no temporal comparison possible"],
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
        return AnalysisResultOut(
            reported_progress=project.reported_progress,
            observable_change_percent=0.0,
            changed_pixel_count=0,
            total_pixel_count=512 * 512,
            bounding_boxes=[],
            recommendation="Field verification recommended",
            explanation=(
                "Sentinel-2 scenes unavailable for this location. "
                "Esri World Imagery fallback is a static mosaic with no temporal depth — "
                "change detection and AI analysis were skipped to avoid false results."
            ),
            before_image_url=f"{base}{processed.t1_image_path.name}",
            after_image_url=f"{base}{processed.t2_image_path.name}",
            change_mask_url="",
            change_overlay_url="",
            is_synthetic_demo=False,
            method=f"Esri World Imagery static fallback (no temporal comparison available)",
            t1_scene=t1_scene_out,
            t2_scene=t2_scene_out,
            candidate_count=0,
            analyzed_candidate_count=0,
            ai_model="esri-fallback-no-temporal",
            ai_analysis=no_temporal_analysis,
            ai_usage=AIUsage(model="esri-fallback-no-temporal", input_tokens=0, output_tokens=0),
            geojson_overlay=None,
            analysis_timestamp=datetime.now(timezone.utc),
            processing_duration_sec=duration,
        )
    # --- End Esri fallback early-return — — — — — — — — — — — — — — ---

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
