"""
Candidate Crop Generator for InfraWatch.

Extracts matching spatial crops from T1 and T2 rasters with context margins
for cost-optimized Gemini 2.5 Flash-Lite reasoning.
"""
from dataclasses import dataclass
from typing import List, Tuple
import cv2
import numpy as np

from app.config import settings
from app.change_detector import CVCandidate


@dataclass
class CandidateCrop:
    candidate: CVCandidate
    t1_crop_bgr: np.ndarray
    t2_crop_bgr: np.ndarray
    crop_bbox_pixel: Tuple[int, int, int, int]  # (crop_x, crop_y, crop_w, crop_h)

    def encode_crops_png(self) -> Tuple[bytes, bytes]:
        """Returns (t1_png_bytes, t2_png_bytes) ready for Vision AI input."""
        _, t1_enc = cv2.imencode(".png", self.t1_crop_bgr)
        _, t2_enc = cv2.imencode(".png", self.t2_crop_bgr)
        return t1_enc.tobytes(), t2_enc.tobytes()


class CandidateCropGenerator:
    def __init__(self, context_margin: int = 64, max_candidates: int = 20):
        self.context_margin = context_margin
        self.max_candidates = max_candidates

    def generate_crops(
        self, t1: np.ndarray, t2: np.ndarray, candidates: List[CVCandidate]
    ) -> List[CandidateCrop]:
        if not candidates:
            return []

        # Cap candidates to max_candidates
        selected_candidates = candidates[: self.max_candidates]
        h, w = t1.shape[:2]

        crop_list: List[CandidateCrop] = []
        for cand in selected_candidates:
            cx, cy, cw, ch = cand.bbox

            # Add context margin
            x1 = max(0, cx - self.context_margin)
            y1 = max(0, cy - self.context_margin)
            x2 = min(w, cx + cw + self.context_margin)
            y2 = min(h, cy + ch + self.context_margin)

            t1_crop = t1[y1:y2, x1:x2]
            t2_crop = t2[y1:y2, x1:x2]

            # Ensure non-empty crop
            if t1_crop.size == 0 or t2_crop.size == 0:
                continue

            crop_list.append(
                CandidateCrop(
                    candidate=cand,
                    t1_crop_bgr=t1_crop,
                    t2_crop_bgr=t2_crop,
                    crop_bbox_pixel=(x1, y1, x2 - x1, y2 - y1),
                )
            )

        return crop_list
