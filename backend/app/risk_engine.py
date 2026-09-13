"""
Composite risk engine for InfraWatch.

Combines four independent, side-effect-free, deterministic anomaly signals into
one 0-100 composite risk score:
  - Satellite discrepancy (50% weight) — reported progress vs. observed change
  - Financial overrun (20% weight) — sanctioned amount vs. actual expenditure
  - Timeline / delay (15% weight) — schedule slippage and stalling
  - Duplicate works (15% weight) — text/amount/geo similarity to other projects

Key principles (worth restating, because they materially affect how the
scores should be read): missing data is never treated as an anomaly — it
lowers confidence, not risk. Observable satellite change is not the same
thing as engineering completion percentage. This is a screening
prioritization signal for human review, never proof of fraud — see
PROTOTYPE_DISCLAIMER below, which is surfaced in every API response that
includes a risk score.

There is deliberately no per-project special-casing anywhere in this module.
If a specific project needs a different treatment, that's a data problem
(feed it different inputs), not a code problem (hardcode its ID).
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Set

from app.config import RISK_WEIGHTS

PROTOTYPE_DISCLAIMER = (
    "InfraWatch prototype risk score. These are automated screening indicators to help "
    "prioritize human review — they do NOT constitute proof of statutory violation, fraud, "
    "or contractor default. Field inspection is recommended for HIGH or CRITICAL tiers."
)


# ── Component result types ───────────────────────────────────────────────

@dataclass
class CostOverrunResult:
    risk_score: float
    overrun_percentage: Optional[float]
    has_data: bool
    confidence: float
    explanation: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineRiskResult:
    risk_score: float
    delay_days: int
    has_data: bool
    is_delayed: bool
    is_stalled: bool
    confidence: float
    explanation: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DuplicateMatch:
    matched_project_id: str
    text_similarity: float
    amount_similarity: float
    composite_similarity: float
    matched_description: str
    distance_km: Optional[float] = None
    days_apart: Optional[int] = None


@dataclass
class DuplicateRiskResult:
    risk_score: float
    highest_similarity: float
    top_matches: List[DuplicateMatch] = field(default_factory=list)
    has_data: bool = True
    confidence: float = 0.8
    explanation: str = ""


@dataclass
class SatelliteDiscrepancyResult:
    risk_score: float
    discrepancy_points: Optional[float]
    has_data: bool
    is_real_satellite: bool
    satellite_source: str
    evidence_type: str  # "real_satellite" | "manual_upload" | "legacy_demo" | "unavailable"
    confidence: float
    explanation: str


# ── 1. Cost overrun ──────────────────────────────────────────────────────

def compute_cost_overrun_risk(
    sanctioned_amount: Optional[float],
    actual_expenditure: Optional[float],
    allowable_variance_pct: float = 5.0,
) -> CostOverrunResult:
    if sanctioned_amount is None or actual_expenditure is None:
        return CostOverrunResult(
            risk_score=0.0, overrun_percentage=None, has_data=False, confidence=0.20,
            explanation="Financial figures incomplete (sanctioned amount or actual expenditure not recorded).",
        )

    if sanctioned_amount <= 0:
        if actual_expenditure > 0:
            return CostOverrunResult(
                risk_score=75.0, overrun_percentage=None, has_data=True, confidence=0.70,
                explanation=f"Expenditure of Rs. {actual_expenditure:,.2f} recorded against zero/unrecorded sanctioned budget.",
                details={"unauthorized_spend": True},
            )
        return CostOverrunResult(
            risk_score=0.0, overrun_percentage=0.0, has_data=True, confidence=0.50,
            explanation="No sanctioned budget or expenditure recorded.",
        )

    overrun_pct = ((actual_expenditure - sanctioned_amount) / sanctioned_amount) * 100.0

    if overrun_pct <= allowable_variance_pct:
        risk = 0.0
        explanation = f"Expenditure within sanctioned bounds (overrun: {overrun_pct:.1f}%)."
    elif overrun_pct <= 15.0:
        risk = (overrun_pct - allowable_variance_pct) * 3.5
        explanation = f"Moderate financial overrun of {overrun_pct:.1f}%."
    elif overrun_pct <= 40.0:
        risk = 35.0 + (overrun_pct - 15.0) * 1.6
        explanation = f"Substantial financial overrun of {overrun_pct:.1f}% over sanctioned allocation."
    else:
        risk = min(100.0, 75.0 + (overrun_pct - 40.0) * 0.8)
        explanation = f"Critical expenditure overrun of {overrun_pct:.1f}% over sanctioned budget."

    return CostOverrunResult(
        risk_score=round(max(0.0, min(100.0, risk)), 2),
        overrun_percentage=round(overrun_pct, 2), has_data=True, confidence=0.90,
        explanation=explanation, details={"overrun_rupees": round(actual_expenditure - sanctioned_amount, 2)},
    )


# ── 2. Timeline / delay ──────────────────────────────────────────────────

def compute_timeline_risk(
    start_date: Optional[datetime] = None,
    expected_end_date: Optional[datetime] = None,
    reported_status: Optional[str] = None,
    reported_progress: Optional[float] = None,
    reference_date: Optional[datetime] = None,
) -> TimelineRiskResult:
    def _to_date(dt):
        if dt is None:
            return None
        return dt.date() if isinstance(dt, datetime) else dt

    ref_d = _to_date(reference_date) or date.today()
    exp_d = _to_date(expected_end_date)
    start_d = _to_date(start_date)

    status_str = (reported_status or "").strip().lower()
    is_completed = status_str in ("completed", "complete", "finished") or (
        reported_progress is not None and reported_progress >= 100.0
    )
    if is_completed:
        return TimelineRiskResult(
            risk_score=0.0, delay_days=0, has_data=True, is_delayed=False, is_stalled=False,
            confidence=0.90, explanation="Project marked completed in official records.",
        )

    if exp_d is None:
        return TimelineRiskResult(
            risk_score=0.0, delay_days=0, has_data=False, is_delayed=False, is_stalled=False,
            confidence=0.30, explanation="Target completion date not recorded.",
        )

    delay_days = (ref_d - exp_d).days
    is_delayed = delay_days > 0
    is_stalled = (
        start_d is not None and (ref_d - start_d).days > 365
        and reported_progress is not None and reported_progress < 5.0
    )

    if not is_delayed:
        if is_stalled:
            risk, explanation = 45.0, "Project started over a year ago with under 5% reported progress."
        else:
            risk, explanation = 0.0, f"Project is within its target timeline (due {exp_d.isoformat()})."
    else:
        if delay_days <= 30:
            risk = delay_days * 0.8
            explanation = f"Minor timeline slippage of {delay_days} days past target date."
        elif delay_days <= 90:
            risk = 24.0 + (delay_days - 30) * 0.45
            explanation = f"Moderate project delay of {delay_days} days past target date."
        elif delay_days <= 270:
            risk = 51.0 + (delay_days - 90) * 0.16
            explanation = f"Substantial project delay of {delay_days} days (~{delay_days // 30} months)."
        else:
            risk = min(100.0, 80.0 + (delay_days - 270) * 0.08)
            explanation = f"Severe project delay of {delay_days} days past scheduled completion."
        if is_stalled:
            risk = min(100.0, risk + 20.0)
            explanation += " Shows signs of prolonged stalling."

    return TimelineRiskResult(
        risk_score=round(max(0.0, min(100.0, risk)), 2), delay_days=max(0, delay_days),
        has_data=True, is_delayed=is_delayed, is_stalled=is_stalled, confidence=0.85, explanation=explanation,
    )


# ── 3. Duplicate / similar works ─────────────────────────────────────────

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> Set[str]:
    return set(_TOKEN_RE.findall(text.lower())) if text else set()


def _text_jaccard_similarity(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _amount_similarity(a: Optional[float], b: Optional[float]) -> float:
    if a is None or b is None or a <= 0 or b <= 0:
        return 0.5
    hi = max(a, b)
    return max(0.0, 1.0 - abs(a - b) / hi)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    d_lat, d_lon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def compute_duplicate_risk(
    target_project_id: str,
    target_description: str,
    target_amount: Optional[float] = None,
    target_category: Optional[str] = None,
    target_lat: Optional[float] = None,
    target_lon: Optional[float] = None,
    candidates: Sequence[Dict[str, Any]] = (),
    similarity_threshold: float = 0.70,
) -> DuplicateRiskResult:
    if not target_description or not candidates:
        return DuplicateRiskResult(
            risk_score=0.0, highest_similarity=0.0, has_data=bool(target_description),
            confidence=0.50 if not target_description else 0.85,
            explanation="No candidate works available for comparison.",
        )

    matches: List[DuplicateMatch] = []
    for cand in candidates:
        cand_id = str(cand.get("id", ""))
        if cand_id == str(target_project_id):
            continue
        cand_desc = cand.get("description", "")
        if not cand_desc:
            continue

        text_sim = _text_jaccard_similarity(target_description, cand_desc)
        if text_sim < 0.35:
            continue

        amt_sim = _amount_similarity(target_amount, cand.get("amount"))
        cat_match = bool(
            target_category and cand.get("category")
            and target_category.lower() == cand.get("category", "").lower()
        )
        dist_km, geo_factor = None, 0.5
        if target_lat is not None and target_lon is not None:
            c_lat, c_lon = cand.get("latitude"), cand.get("longitude")
            if c_lat is not None and c_lon is not None:
                dist_km = _haversine_km(target_lat, target_lon, c_lat, c_lon)
                geo_factor = max(0.0, 1.0 - min(dist_km, 5.0) / 5.0)

        composite = text_sim * 45.0 + amt_sim * 20.0 + (10.0 if cat_match else 0.0) + geo_factor * 15.0 + 5.0

        if composite >= (similarity_threshold * 100.0) or text_sim >= 0.75:
            matches.append(DuplicateMatch(
                matched_project_id=cand_id, text_similarity=round(text_sim, 3), amount_similarity=round(amt_sim, 3),
                composite_similarity=round(composite, 1), matched_description=cand_desc[:120],
                distance_km=round(dist_km, 2) if dist_km is not None else None,
            ))

    matches.sort(key=lambda m: m.composite_similarity, reverse=True)
    if not matches:
        return DuplicateRiskResult(
            risk_score=0.0, highest_similarity=0.0, has_data=True, confidence=0.85,
            explanation="No similar-enough works found nearby.",
        )

    top = matches[0]
    if top.composite_similarity >= 85.0:
        risk = 90.0
        explanation = f"Critical duplicate risk: {len(matches)} highly similar work(s), top match #{top.matched_project_id} ({top.composite_similarity}%)."
    elif top.composite_similarity >= 70.0:
        risk = 65.0
        explanation = f"High similarity with work #{top.matched_project_id} ({top.composite_similarity}% composite match)."
    else:
        risk = 35.0
        explanation = f"Moderate overlap with work #{top.matched_project_id} ({top.composite_similarity}% match)."

    return DuplicateRiskResult(
        risk_score=risk, highest_similarity=top.composite_similarity, top_matches=matches[:5],
        has_data=True, confidence=0.80, explanation=explanation,
    )


# ── 4. Satellite discrepancy (the core InfraWatch signal) ───────────────

def compute_satellite_discrepancy_risk(
    reported_progress: Optional[float],
    observed_change: Optional[float],
    satellite_confidence: float = 0.85,
    evidence_type: str = "real_satellite",  # "real_satellite" | "manual_upload" | "legacy_demo" | "unavailable"
) -> SatelliteDiscrepancyResult:
    is_real = evidence_type == "real_satellite"

    if reported_progress is None or observed_change is None:
        return SatelliteDiscrepancyResult(
            risk_score=0.0, discrepancy_points=None, has_data=False, is_real_satellite=is_real,
            satellite_source=evidence_type, evidence_type=evidence_type, confidence=0.15,
            explanation="No observable-change evidence available yet — discrepancy cannot be assessed.",
        )

    discrepancy = round(abs(reported_progress - observed_change), 2)
    is_over_reported = reported_progress > observed_change

    if discrepancy <= 5.0:
        risk = discrepancy * 1.5
        explanation = f"Close alignment: reported ({reported_progress}%) vs. observed ({observed_change}%), {discrepancy} pt gap."
    elif discrepancy <= 20.0:
        if is_over_reported:
            risk = 10.0 + (discrepancy - 5.0) * 1.5
            explanation = f"Minor discrepancy: reported ({reported_progress}%) exceeds observed change ({observed_change}%) by {discrepancy} pts."
        else:
            risk = 5.0 + (discrepancy - 5.0)
            explanation = f"Observed change ({observed_change}%) exceeds reported progress ({reported_progress}%)."
    elif discrepancy <= 40.0:
        if is_over_reported:
            risk = 35.0 + (discrepancy - 20.0) * 1.75
            explanation = f"Substantial discrepancy: {reported_progress}% reported vs. only {observed_change}% observed ({discrepancy} pt gap). Field verification advised."
        else:
            risk = 25.0 + (discrepancy - 20.0) * 1.25
            explanation = f"Significant unrecorded change ({observed_change}% observed vs. {reported_progress}% reported)."
    else:
        if is_over_reported:
            risk = min(100.0, 70.0 + (discrepancy - 40.0) * 1.2)
            explanation = f"Critical discrepancy: {reported_progress}% reported complete but only {observed_change}% observable change ({discrepancy} pt gap). Urgent field audit recommended."
        else:
            risk = min(80.0, 50.0 + (discrepancy - 40.0) * 0.75)
            explanation = f"Very large divergence: observed change ({observed_change}%) greatly exceeds reported progress ({reported_progress}%)."

    if not is_real:
        confidence = round(min(satellite_confidence, 0.45), 2)
        explanation += f" [Evidence type: {evidence_type}, not a real satellite pass — confidence capped accordingly.]"
    else:
        confidence = round(max(0.40, min(0.98, satellite_confidence)), 2)

    return SatelliteDiscrepancyResult(
        risk_score=round(max(0.0, min(100.0, risk)), 2), discrepancy_points=discrepancy, has_data=True,
        is_real_satellite=is_real, satellite_source=evidence_type, evidence_type=evidence_type,
        confidence=confidence, explanation=explanation,
    )


# ── Composite engine ─────────────────────────────────────────────────────

@dataclass
class CompositeRiskResult:
    project_id: str
    risk_score: float
    risk_level: str
    confidence: float
    component_breakdown: Dict[str, Any] = field(default_factory=dict)
    explanations: Dict[str, str] = field(default_factory=dict)
    disclaimer: str = PROTOTYPE_DISCLAIMER
    duplicate_candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _classify(score: float) -> str:
    if score <= 24.0:
        return "LOW"
    if score <= 49.0:
        return "MEDIUM"
    if score <= 74.0:
        return "HIGH"
    return "CRITICAL"


def evaluate_project_risk(
    project_id: str,
    sanctioned_amount: Optional[float] = None,
    actual_expenditure: Optional[float] = None,
    start_date: Optional[datetime] = None,
    expected_end_date: Optional[datetime] = None,
    reported_status: Optional[str] = None,
    description: str = "",
    category: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    candidate_works: Sequence[Dict[str, Any]] = (),
    reported_progress: Optional[float] = None,
    observed_change: Optional[float] = None,
    satellite_confidence: float = 0.85,
    evidence_type: str = "unavailable",
) -> CompositeRiskResult:
    """Runs all four component checks and combines them into one composite score.
    No project ID is ever special-cased here — every input comes from real data."""
    fin_res = compute_cost_overrun_risk(sanctioned_amount, actual_expenditure)
    time_res = compute_timeline_risk(start_date, expected_end_date, reported_status, reported_progress)
    dup_res = compute_duplicate_risk(project_id, description, sanctioned_amount, category, latitude, longitude, candidate_works)
    sat_res = compute_satellite_discrepancy_risk(reported_progress, observed_change, satellite_confidence, evidence_type)

    raw_score = (
        RISK_WEIGHTS["satellite_discrepancy"] * sat_res.risk_score
        + RISK_WEIGHTS["financial"] * fin_res.risk_score
        + RISK_WEIGHTS["timeline"] * time_res.risk_score
        + RISK_WEIGHTS["duplicate_work"] * dup_res.risk_score
    )
    clamped_score = round(max(0.0, min(100.0, raw_score)), 2)

    conf_factors = [sat_res.confidence]
    if fin_res.has_data:
        conf_factors.append(fin_res.confidence)
    if time_res.has_data:
        conf_factors.append(time_res.confidence)
    if dup_res.has_data:
        conf_factors.append(dup_res.confidence)
    base_confidence = sum(conf_factors) / len(conf_factors)
    if not sat_res.is_real_satellite:
        base_confidence = min(base_confidence, 0.45)
    composite_confidence = round(max(0.10, min(0.98, base_confidence)), 2)

    return CompositeRiskResult(
        project_id=str(project_id),
        risk_score=clamped_score,
        risk_level=_classify(clamped_score),
        confidence=composite_confidence,
        component_breakdown={
            "financial": {"score": fin_res.risk_score, "weight": RISK_WEIGHTS["financial"], "has_data": fin_res.has_data},
            "timeline": {"score": time_res.risk_score, "weight": RISK_WEIGHTS["timeline"], "delay_days": time_res.delay_days, "has_data": time_res.has_data},
            "duplicate": {"score": dup_res.risk_score, "weight": RISK_WEIGHTS["duplicate_work"], "match_count": len(dup_res.top_matches)},
            "satellite": {"score": sat_res.risk_score, "weight": RISK_WEIGHTS["satellite_discrepancy"], "discrepancy_points": sat_res.discrepancy_points, "has_data": sat_res.has_data},
        },
        explanations={
            "financial": fin_res.explanation, "timeline": time_res.explanation,
            "duplicate": dup_res.explanation, "satellite": sat_res.explanation,
        },
        duplicate_candidates=[asdict(m) for m in dup_res.top_matches],
    )
