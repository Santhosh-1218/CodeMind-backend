import logging
from typing import List, Dict, Any
from app.hindsight.client import hindsight_client

logger = logging.getLogger("codemind.hindsight.learning")

async def retain_learnings_from_review(
    project_name: str,
    languages: List[str],
    findings: List[Dict[str, Any]]
) -> int:
    """
    Extract durable, reusable coding learnings from a completed review and retain them into Hindsight.
    Returns count of items retained.
    """
    if not findings:
        return 0

    items_to_retain = []
    
    # Filter for high-impact critical/high findings or specific patterns
    for f in findings:
        severity = f.get("severity", "Low")
        category = f.get("category", "Quality")
        title = f.get("title", "")
        desc = f.get("description", "")
        fix = f.get("fix_recommendation", "")

        if severity in ["Critical", "High", "Medium"]:
            learning_text = (
                f"CodeMind Learned Pattern ({project_name}): In {category}, issue '{title}' "
                f"was identified: {desc}. Best Practice / Fix: {fix}"
            )
            items_to_retain.append({
                "content": learning_text,
                "context": f"code_review_{category.lower()}"
            })

    if items_to_retain:
        # Retain top 5 most actionable learnings per review
        subset = items_to_retain[:5]
        success = await hindsight_client.retain(subset)
        if success:
            logger.info(f"Successfully retained {len(subset)} learnings into Hindsight.")
            return len(subset)

    return 0
