from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.models.project import Project
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("")
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.user_id == current_user.id).order_by(Project.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "source_type": p.source_type,
            "repo_url": p.repo_url,
            "created_at": p.created_at,
            "reviews_count": len(p.reviews)
        }
        for p in projects
    ]
