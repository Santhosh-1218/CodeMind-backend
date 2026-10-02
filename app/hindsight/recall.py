import logging
from typing import List, Dict, Any
from app.hindsight.client import hindsight_client

logger = logging.getLogger("codemind.hindsight.recall")

async def recall_learnings_for_review(languages: List[str], filenames: List[str]) -> List[Dict[str, Any]]:
    """
    Recall relevant past review learnings from Hindsight bank based on project languages and key file patterns.
    """
    queries = []
    if languages:
        queries.append(f"Recurring coding bugs security vulnerabilities for {', '.join(languages)}")
    queries.append("General code quality security rules developer preferences")

    recalled_items = []
    seen_texts = set()

    for q in queries:
        memories = await hindsight_client.recall(query=q)
        for m in memories:
            text = m.get("text") or m.get("content") or ""
            if text and text not in seen_texts:
                seen_texts.add(text)
                recalled_items.append({
                    "id": m.get("id"),
                    "text": text,
                    "score": m.get("scores", {}).get("final", 0.0),
                    "entities": m.get("entities", []),
                    "type": m.get("type", "observation")
                })

    logger.info(f"Recalled {len(recalled_items)} total distinct memories for review.")
    return recalled_items
