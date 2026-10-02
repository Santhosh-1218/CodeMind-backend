import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("codemind.analysis.scorer")

"""
DETERMINISTIC SCORE CALCULATION ALGORITHM
-----------------------------------------
1. Base score for each category starts at 100.0.
2. Deductions are calculated per verified finding based on severity and evidence confidence:
   - Critical: -20 points
   - High: -12 points
   - Medium: -6 points
   - Low: -2 points
   - Info: 0 points
3. Deduction is scaled by confidence ratio: deduction = severity_weight * (confidence / 100.0).
4. Category breakdown:
   - Security Score: Derived from Security findings.
   - Code Quality Score: Derived from Bug & Quality findings.
   - Maintainability Score: Derived from Maintainability & Architecture findings.
   - Reliability Score: Derived from Performance & Reliability findings.
5. Overall Score is calculated as a weighted average:
   Overall = round(Security * 0.35 + Quality * 0.30 + Reliability * 0.20 + Maintainability * 0.15)
6. All scores are strictly clamped in the range [0.0, 100.0].
"""

SEVERITY_DEDUCTIONS = {
    "critical": 20.0,
    "high": 12.0,
    "medium": 6.0,
    "low": 2.0,
    "info": 0.0
}

def calculate_deterministic_scores(findings: List[Dict[str, Any]]) -> Tuple[float, float, float, float, float]:
    """
    Calculate deterministic quality, security, maintainability, reliability, and overall scores.
    Returns: (overall_score, quality_score, security_score, maintainability_score, reliability_score)
    """
    sec_deduction = 0.0
    qual_deduction = 0.0
    maint_deduction = 0.0
    rel_deduction = 0.0

    for f in findings:
        sev = f.get("severity", "Low").lower()
        cat = f.get("category", "Quality").lower()
        conf = float(f.get("confidence", 90)) / 100.0

        base_ded = SEVERITY_DEDUCTIONS.get(sev, 2.0) * conf

        if cat == "security":
            sec_deduction += base_ded
        elif cat in ("bug", "quality"):
            qual_deduction += base_ded
        elif cat in ("maintainability", "architecture"):
            maint_deduction += base_ded
        elif cat in ("performance", "reliability"):
            rel_deduction += base_ded
        else:
            qual_deduction += base_ded

    security_score = max(0.0, min(100.0, round(100.0 - sec_deduction, 1)))
    quality_score = max(0.0, min(100.0, round(100.0 - qual_deduction, 1)))
    maintainability_score = max(0.0, min(100.0, round(100.0 - maint_deduction, 1)))
    reliability_score = max(0.0, min(100.0, round(100.0 - rel_deduction, 1)))

    overall_score = round(
        security_score * 0.35 +
        quality_score * 0.30 +
        reliability_score * 0.20 +
        maintainability_score * 0.15,
        1
    )

    logger.info(f"Calculated deterministic scores - Overall: {overall_score}, Security: {security_score}, Quality: {quality_score}, Maintainability: {maintainability_score}, Reliability: {reliability_score}")
    return overall_score, quality_score, security_score, maintainability_score, reliability_score
