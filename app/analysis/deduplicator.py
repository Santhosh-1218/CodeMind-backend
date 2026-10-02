import logging
from typing import List, Dict, Any

logger = logging.getLogger("codemind.analysis.deduplicator")

def deduplicate_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplication Engine.
    Merges duplicate findings pointing to the same file, line, or root cause.
    Aggregates evidence signals (AST static analysis, LLM reasoning, Hindsight memory).
    """
    merged_map: Dict[str, Dict[str, Any]] = {}

    for f in findings:
        file_path = f.get("file_path", "general")
        line_no = f.get("line_number", 1)
        category = f.get("category", "General").lower()
        title_key = f.get("title", "").lower()[:20]

        # Deduplication key grouping by file, line proximity (+-2 lines), and category
        key = f"{file_path}:{line_no // 3}:{category}:{title_key}"

        if key in merged_map:
            existing = merged_map[key]
            # Merge evidence list
            existing_ev = existing.get("evidence", [])
            new_ev = f.get("evidence", [])
            combined_ev = list(dict.fromkeys(existing_ev + new_ev))
            existing["evidence"] = combined_ev

            # Keep higher severity
            sev_rank = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "Info": 0}
            if sev_rank.get(f.get("severity", "Low"), 1) > sev_rank.get(existing.get("severity", "Low"), 1):
                existing["severity"] = f.get("severity")

            # Merge memory influence
            if f.get("memory_influenced"):
                existing["memory_influenced"] = True
                if f.get("hindsight_memory_text"):
                    existing["hindsight_memory_text"] = f.get("hindsight_memory_text")

            # Boost confidence score
            existing["confidence"] = min(99, max(existing.get("confidence", 85), f.get("confidence", 85)) + 5)
        else:
            # Ensure evidence list exists
            if "evidence" not in f or not isinstance(f["evidence"], list):
                f["evidence"] = ["Pattern detected by code analysis"]
            merged_map[key] = f

    deduped = list(merged_map.values())
    logger.info(f"Deduplicated {len(findings)} findings down to {len(deduped)} canonical issues.")
    return deduped
