from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.models.review import Review
from app.models.project import Project
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/history", tags=["History"])

@router.get("")
def get_history_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reviews = db.query(Review).filter(Review.user_id == current_user.id).order_by(Review.created_at.desc()).all()
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()

    total_reviews = len(reviews)
    total_projects = len(projects)
    total_files = sum(r.file_count for r in reviews)
    total_issues = sum(r.critical_count + r.high_count + r.medium_count + r.low_count for r in reviews)

    return {
        "total_reviews": total_reviews,
        "total_projects": total_projects,
        "total_files": total_files,
        "total_issues": total_issues,
        "recent_reviews": [
            {
                "id": r.id,
                "project_name": r.project.name if r.project else "Project",
                "source_type": r.project.source_type if r.project else "zip",
                "status": r.status,
                "quality_score": r.quality_score,
                "security_score": r.security_score,
                "file_count": r.file_count,
                "total_issues": r.critical_count + r.high_count + r.medium_count + r.low_count,
                "created_at": r.created_at
            }
            for r in reviews
        ]
    }
