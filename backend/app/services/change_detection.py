"""Transparent OpenCV baseline for synthetic before/after image comparison."""
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np


@dataclass
class DetectionResult:
    changed_pixel_count: int
    total_pixel_count: int
    observable_change_percent: float
    bounding_boxes: list[dict[str, int]]
    mask: np.ndarray
    overlay: np.ndarray


def detect_change(before_path: str | Path, after_path: str | Path) -> DetectionResult:
    before = cv2.imread(str(before_path), cv2.IMREAD_COLOR)
    after = cv2.imread(str(after_path), cv2.IMREAD_COLOR)
    if before is None or after is None:
        raise ValueError("Synthetic demo image could not be loaded")
    if before.shape[:2] != after.shape[:2]:
        after = cv2.resize(after, (before.shape[1], before.shape[0]), interpolation=cv2.INTER_AREA)

    difference = cv2.absdiff(cv2.cvtColor(before, cv2.COLOR_BGR2GRAY), cv2.cvtColor(after, cv2.COLOR_BGR2GRAY))
    _, mask = cv2.threshold(difference, 25, 255, cv2.THRESH_BINARY)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[dict[str, int]] = []
    cleaned_mask = np.zeros_like(mask)
    for contour in contours:
        if cv2.contourArea(contour) < 80:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        boxes.append({"x": int(x), "y": int(y), "width": int(width), "height": int(height)})
        cv2.drawContours(cleaned_mask, [contour], -1, 255, -1)
    changed = int(np.count_nonzero(cleaned_mask))
    total = int(cleaned_mask.size)
    overlay = after.copy()
    overlay[cleaned_mask > 0] = (0, 0, 255)
    overlay = cv2.addWeighted(after, 0.62, overlay, 0.38, 0)
    for box in boxes:
        cv2.rectangle(overlay, (box["x"], box["y"]), (box["x"] + box["width"], box["y"] + box["height"]), (0, 0, 255), 2)
    return DetectionResult(changed, total, round(changed / total * 100, 2), boxes, cleaned_mask, overlay)
