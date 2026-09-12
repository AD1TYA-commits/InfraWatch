"""
Local Computer Vision Change Detector for InfraWatch.

Runs fast, cost-efficient image differencing, morphological filtering, and contour extraction
on co-registered T1 and T2 satellite scenes before sending candidates to Gemini.
"""
from dataclasses import dataclass, field
from pathlib import Path
import logging
from typing import List, Tuple, Dict, Any

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger("infrawatch.change_detector")


@dataclass
class CVCandidate:
    candidate_id: str
    bbox: Tuple[int, int, int, int]  # (x, y, width, height) in pixel coords
    pixel_area: int
    estimated_area_m2: float
    cv_confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "bbox": list(self.bbox),
            "pixel_area": self.pixel_area,
            "estimated_area_m2": round(self.estimated_area_m2, 2),
            "cv_confidence": round(self.cv_confidence, 2),
        }


@dataclass
class DetectionOutput:
    changed_pixel_count: int
    total_pixel_count: int
    observable_change_percent: float
    candidates: List[CVCandidate]
    mask: np.ndarray
    overlay: np.ndarray
    mask_path: Path
    overlay_path: Path


class ChangeDetector:
    def __init__(self, min_cv_confidence: float = 0.50):
        self.min_cv_confidence = min_cv_confidence

    def detect(
        self,
        t1: np.ndarray,
        t2: np.ndarray,
        project_id: int,
        asset_dir: Path,
        pixel_res_m: float = 3.0,  # ~3 meters per pixel for 512x512 1.5km window
    ) -> DetectionOutput:
        height, width = t1.shape[:2]
        if t2.shape[:2] != (height, width):
            t2 = cv2.resize(t2, (width, height), interpolation=cv2.INTER_AREA)

        # Convert to grayscale & apply Gaussian blur to suppress sensor noise
        g1 = cv2.GaussianBlur(cv2.cvtColor(t1, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        g2 = cv2.GaussianBlur(cv2.cvtColor(t2, cv2.COLOR_BGR2GRAY), (5, 5), 0)

        # Compute absolute difference
        diff = cv2.absdiff(g1, g2)

        # Adaptive thresholding — 40 suppresses JPEG/sensor noise better than 28
        _, mask = cv2.threshold(diff, 40, 255, cv2.THRESH_BINARY)

        # Morphological opening/closing to filter out tiny noisy specks & seasonal grass changes
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Find connected contour regions
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates: List[CVCandidate] = []
        cleaned_mask = np.zeros_like(mask)

        cid = 1
        for contour in contours:
            area = cv2.contourArea(contour)
            # Filter out noise (< 200 px area) — raised from 60 to suppress seasonal grass changes
            if area < 200:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            area_m2 = area * (pixel_res_m ** 2)

            # Estimate candidate confidence based on region size and average pixel delta intensity
            roi_diff = diff[y : y + h, x : x + w]
            mean_intensity = float(np.mean(roi_diff[roi_diff > 0])) if np.any(roi_diff > 0) else 30.0
            confidence = min(0.99, max(0.40, (mean_intensity / 100.0) * 0.7 + min(area / 1000.0, 0.3)))

            if confidence >= self.min_cv_confidence or cid <= 3:  # Always include top candidates
                cv2.drawContours(cleaned_mask, [contour], -1, 255, -1)
                candidates.append(
                    CVCandidate(
                        candidate_id=f"candidate-{cid:03d}",
                        bbox=(int(x), int(y), int(w), int(h)),
                        pixel_area=int(area),
                        estimated_area_m2=float(area_m2),
                        cv_confidence=round(confidence, 2),
                    )
                )
                cid += 1

        # Sort candidates descending by confidence & area
        candidates.sort(key=lambda c: (c.cv_confidence, c.pixel_area), reverse=True)

        changed_pixels = int(np.count_nonzero(cleaned_mask))
        total_pixels = int(cleaned_mask.size)
        change_pct = round((changed_pixels / total_pixels) * 100, 2)

        # Sanity check: if > 50% of the image is flagged as changed, this is almost
        # certainly a false positive caused by identical images, JPEG re-compression
        # artifacts, or a lighting/colour shift between scenes — not real ground change.
        if change_pct > 50.0:
            logger.warning(
                f"Change mask covers {change_pct}% of the image — exceeds 50% sanity threshold. "
                "Treating as false positive and resetting detection output."
            )
            cleaned_mask = np.zeros_like(mask)
            candidates = []
            changed_pixels = 0
            change_pct = 0.0

        # Build overlay visualization
        overlay = t2.copy()
        overlay[cleaned_mask > 0] = (0, 0, 255)  # Red highlight
        overlay = cv2.addWeighted(t2, 0.60, overlay, 0.40, 0)

        for cand in candidates:
            x, y, w, h = cand.bbox
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 230, 255), 2)
            cv2.putText(
                overlay,
                cand.candidate_id,
                (x, max(15, y - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 255),
                1,
            )

        # Save output artifacts
        mask_path = asset_dir / f"project_{project_id}_change_mask.png"
        overlay_path = asset_dir / f"project_{project_id}_change_overlay.png"

        cv2.imwrite(str(mask_path), cleaned_mask)
        cv2.imwrite(str(overlay_path), overlay)

        logger.info(
            f"Local CV detection complete: {len(candidates)} candidate regions found, change={change_pct}%"
        )
        return DetectionOutput(
            changed_pixel_count=changed_pixels,
            total_pixel_count=total_pixels,
            observable_change_percent=change_pct,
            candidates=candidates,
            mask=cleaned_mask,
            overlay=overlay,
            mask_path=mask_path,
            overlay_path=overlay_path,
        )


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    asset_dir = Path(__file__).resolve().parent / "demo_assets"
    detector = ChangeDetector()
    
    print("=" * 60)
    print("Running InfraWatch Computer Vision Change Detector")
    print(f"Asset directory: {asset_dir}")
    print("=" * 60)

    # Detect for all available project pairs or project 1
    found_any = False
    for pid in range(1, 7):
        before_file = asset_dir / f"project_{pid}_before.png"
        after_file = asset_dir / f"project_{pid}_after.png"
        if not before_file.exists() or not after_file.exists():
            continue
        
        found_any = True
        t1 = cv2.imread(str(before_file))
        t2 = cv2.imread(str(after_file))
        
        print(f"\n[Project #{pid}] Analyzing T1 -> T2 differencing...")
        result = detector.detect(t1, t2, project_id=pid, asset_dir=asset_dir)
        
        print(f"  Changed pixels: {result.changed_pixel_count:,} / {result.total_pixel_count:,}")
        print(f"  Observable change: {result.observable_change_percent}%")
        print(f"  Candidate regions found: {len(result.candidates)}")
        for c in result.candidates[:5]:
            print(f"    - {c.candidate_id}: bbox={c.bbox}, area={c.estimated_area_m2:.1f} m², cv_conf={c.cv_confidence}")
        print(f"  Mask saved: {result.mask_path.name}")
        print(f"  Overlay saved: {result.overlay_path.name}")

    if not found_any:
        print("No demo assets found in demo_assets directory.")
    print("\n" + "=" * 60)
    print("Change detection run completed successfully.")
    print("=" * 60)

