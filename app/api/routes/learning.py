from typing import List, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.models.review import Review
from app.models.finding import Finding
from app.hindsight.client import hindsight_client
from app.api.routes.auth import get_current_user
from app.schemas.learning import LearningStatsResponse, RecurringIssueItem, LearnedPreferenceItem, LearningTimelineItem, MemoryItem

router = APIRouter(prefix="/learning", tags=["Learning"])

@router.get("", response_model=LearningStatsResponse)
async def get_learning_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reviews = db.query(Review).filter(Review.user_id == current_user.id).order_by(Review.created_at.asc()).all()

    # Fetch live memories from Hindsight Cloud API
    raw_hindsight_memories = await hindsight_client.list_memories(limit=50)

    recent_memories = []
    for idx, m in enumerate(raw_hindsight_memories):
        txt = m.get("text") or m.get("content") or ""
        if txt:
            recent_memories.append(MemoryItem(
                id=str(m.get("id") or idx),
                text=txt,
                type=str(m.get("type", "observation")),
                context=str(m.get("context", "code_review")),
                created_at=m.get("mentioned_at", None)
            ))

    # Calculate recurring issues from DB findings for current user
    all_findings = db.query(Finding).join(Review).filter(Review.user_id == current_user.id).all()
    
    issue_counts: Dict[str, Dict] = {}
    for f in all_findings:
        key = f"{f.category}:{f.title}"
        if key not in issue_counts:
            issue_counts[key] = {
                "category": f.category,
                "title": f.title,
                "count": 0,
                "severity": f.severity,
                "description": f.description,
                "fix": f.fix_recommendation
            }
        issue_counts[key]["count"] += 1

    sorted_issues = sorted(issue_counts.values(), key=lambda x: x["count"], reverse=True)
    recurring_issues = [
        RecurringIssueItem(
            category=item["category"],
            title=item["title"],
            count=item["count"],
            severity=item["severity"],
            description=item["description"]
        )
        for item in sorted_issues[:6]
    ]

    # Generate real learned preferences dynamically from actual user findings & Hindsight memory
    learned_preferences = []
    for item in sorted_issues[:4]:
        conf = min(0.99, 0.70 + (item["count"] * 0.05))
        learned_preferences.append(
            LearnedPreferenceItem(
                category=item["category"],
                preference=f"Enforce {item['title']} Prevention",
                confidence=round(conf, 2),
                example=item["fix"] or item["description"]
            )
        )

    # Timeline of reviews showing score evolution over time
    timeline = []
    for r in reviews:
        timeline.append(LearningTimelineItem(
            date=r.created_at.strftime("%Y-%m-%d %H:%M"),
            project_name=r.project.name if r.project else "Project",
            quality_score=r.quality_score,
            security_score=r.security_score,
            memories_recalled=r.hindsight_memories_recalled,
            learnings_retained=r.hindsight_learnings_retained
        ))

    return LearningStatsResponse(
        total_memories=len(recent_memories),
        total_reviews_analyzed=len(reviews),
        recurring_issues=recurring_issues,
        learned_preferences=learned_preferences,
        timeline=timeline,
        recent_memories=recent_memories
    )
