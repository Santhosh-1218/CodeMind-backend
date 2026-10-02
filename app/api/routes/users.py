from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import UserProfile, UserUpdate
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/profile", response_model=UserProfile)
def get_profile(current_user: User = Depends(get_current_user)):
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        provider=current_user.provider,
        reviews_count=len(current_user.reviews),
        projects_count=len(current_user.projects),
        files_analyzed=sum(r.file_count for r in current_user.reviews),
        issues_detected=sum(r.critical_count + r.high_count + r.medium_count + r.low_count for r in current_user.reviews)
    )

@router.patch("/profile", response_model=UserProfile)
def update_profile(
    req: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.full_name is not None:
        current_user.full_name = req.full_name
    if req.email is not None and req.email != current_user.email:
        existing = db.query(User).filter(User.email == req.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email is already in use.")
        current_user.email = req.email

    db.commit()
    db.refresh(current_user)

    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        provider=current_user.provider,
        reviews_count=len(current_user.reviews),
        projects_count=len(current_user.projects)
    )
