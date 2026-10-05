import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import httpx

from app.db.database import get_db
from app.models.user import User
from app.models.oauth_account import OAuthAccount
from app.models.session import Session as UserSession
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.core.config import settings
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse, UserProfile

router = APIRouter(prefix="/auth", tags=["Auth"])

def set_session_cookie(response: Response, token: str):
    """Sets session cookie with proper cross-site settings for production HTTPS environments."""
    is_https = settings.backend_url_clean.startswith("https")
    response.set_cookie(
        key="codemind_session",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="none" if is_https else "lax",
        secure=is_https
    )

def create_db_session(db: Session, user_id: str) -> str:
    """Create a persistent user session in SQLite database."""
    token = create_access_token(user_id)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    db_session = UserSession(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    db.add(db_session)
    db.commit()
    return token

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Authenticate user via session token (HttpOnly cookie or Authorization header).
    Requires a valid, non-expired session in SQLite database.
    Strictly returns 401 Unauthorized if unauthenticated. NO DEMO USER FALLBACK.
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif request.cookies.get("codemind_session"):
        token = request.cookies.get("codemind_session")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in."
        )

    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token."
        )

    # Check database session record
    session_record = db.query(UserSession).filter(UserSession.token == token).first()
    if not session_record or session_record.expires_at < datetime.utcnow():
        if session_record:
            db.delete(session_record)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found."
        )

    return user

@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered.")

    user = User(
        email=req.email,
        full_name=req.full_name,
        password_hash=hash_password(req.password),
        provider="email"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_db_session(db, user.id)
    set_session_cookie(response, token)

    return AuthResponse(
        token=token,
        user=UserProfile(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            provider=user.provider,
            reviews_count=0,
            projects_count=0
        )
    )

@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid email or password.")

    token = create_db_session(db, user.id)
    set_session_cookie(response, token)

    return AuthResponse(
        token=token,
        user=UserProfile(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            provider=user.provider,
            reviews_count=len(user.reviews),
            projects_count=len(user.projects)
        )
    )

@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("codemind_session")
    auth_header = request.headers.get("Authorization")
    if not token and auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    if token:
        db.query(UserSession).filter(UserSession.token == token).delete()
        db.commit()

    is_https = settings.backend_url_clean.startswith("https")
    response.delete_cookie("codemind_session", samesite="none" if is_https else "lax", secure=is_https)
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserProfile)
def me(current_user: User = Depends(get_current_user)):
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

@router.get("/github")
def github_login():
    client_id = settings.github_client_id_clean
    if not client_id:
        return RedirectResponse(f"{settings.frontend_url_clean}/login?error=github_oauth_missing_config")

    redirect_uri = f"{settings.backend_url_clean}/api/auth/github/callback"
    github_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope=user:email,repo"
    return RedirectResponse(github_url)

@router.get("/github/callback")
async def github_callback(code: Optional[str] = None, error: Optional[str] = None, db: Session = Depends(get_db)):
    if error or not code:
        return RedirectResponse(f"{settings.frontend_url_clean}/login?error=github_oauth_cancelled")

    client_id = settings.github_client_id_clean
    client_secret = settings.github_client_secret_clean

    if not client_id or not client_secret:
        return RedirectResponse(f"{settings.frontend_url_clean}/login?error=github_oauth_missing_config")

    redirect_uri = f"{settings.backend_url_clean}/api/auth/github/callback"
    token_url = "https://github.com/login/oauth/access_token"

    async with httpx.AsyncClient() as client:
        res = await client.post(
            token_url,
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri
            }
        )
        data = res.json()
        access_token = data.get("access_token")
        if not access_token:
            return RedirectResponse(f"{settings.frontend_url_clean}/login?error=github_oauth_failed")

        user_res = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        gh_user = user_res.json()
        gh_id = str(gh_user.get("id"))
        email = gh_user.get("email")

        # If email is private, fetch primary email from emails endpoint
        if not email:
            try:
                emails_res = await client.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if emails_res.status_code == 200:
                    emails_data = emails_res.json()
                    for em in emails_data:
                        if em.get("primary") and em.get("verified"):
                            email = em.get("email")
                            break
            except Exception:
                pass

        if not email:
            email = f"github_{gh_id}@users.noreply.github.com"

        name = gh_user.get("name") or gh_user.get("login") or "GitHub User"
        avatar = gh_user.get("avatar_url")

    oauth = db.query(OAuthAccount).filter(OAuthAccount.provider == "github", OAuthAccount.provider_user_id == gh_id).first()
    if oauth:
        user = oauth.user
        oauth.access_token = access_token
    else:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, full_name=name, avatar_url=avatar, provider="github")
            db.add(user)
            db.commit()
            db.refresh(user)

        oauth = OAuthAccount(user_id=user.id, provider="github", provider_user_id=gh_id, access_token=access_token)
        db.add(oauth)

    # Sync active user profile details (provider, avatar, name) to matching GitHub login
    user.provider = "github"
    if avatar:
        user.avatar_url = avatar
    if name:
        user.full_name = name
    db.commit()
    db.refresh(user)

    token = create_db_session(db, user.id)
    response = RedirectResponse(f"{settings.frontend_url_clean}/app?token={token}")
    set_session_cookie(response, token)
    return response

@router.get("/google")
def google_login():
    client_id = settings.google_client_id_clean
    if not client_id:
        return RedirectResponse(f"{settings.frontend_url_clean}/login?error=google_oauth_missing_config")

    redirect_uri = f"{settings.backend_url_clean}/api/auth/google/callback"
    google_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile"
    )
    return RedirectResponse(google_url)

@router.get("/google/callback")
async def google_callback(code: Optional[str] = None, error: Optional[str] = None, db: Session = Depends(get_db)):
    if error or not code:
        return RedirectResponse(f"{settings.frontend_url_clean}/login?error=google_oauth_cancelled")

    client_id = settings.google_client_id_clean
    client_secret = settings.google_client_secret_clean

    if not client_id or not client_secret:
        return RedirectResponse(f"{settings.frontend_url_clean}/login?error=google_oauth_missing_config")

    redirect_uri = f"{settings.backend_url_clean}/api/auth/google/callback"
    token_url = "https://oauth2.googleapis.com/token"
    async with httpx.AsyncClient() as client:
        res = await client.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri
            }
        )
        data = res.json()
        access_token = data.get("access_token")
        if not access_token:
            return RedirectResponse(f"{settings.frontend_url_clean}/login?error=google_oauth_failed")

        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        g_user = user_res.json()
        g_id = str(g_user.get("id"))
        email = g_user.get("email")
        if not email:
            return RedirectResponse(f"{settings.frontend_url_clean}/login?error=google_email_missing")

        name = g_user.get("name") or "Google User"
        avatar = g_user.get("picture")

    oauth = db.query(OAuthAccount).filter(OAuthAccount.provider == "google", OAuthAccount.provider_user_id == g_id).first()
    if oauth:
        user = oauth.user
        oauth.access_token = access_token
    else:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, full_name=name, avatar_url=avatar, provider="google")
            db.add(user)
            db.commit()
            db.refresh(user)

        oauth = OAuthAccount(user_id=user.id, provider="google", provider_user_id=g_id, access_token=access_token)
        db.add(oauth)

    # Sync active user profile details (provider, avatar, name) to matching Google login
    user.provider = "google"
    if avatar:
        user.avatar_url = avatar
    if name:
        user.full_name = name
    db.commit()
    db.refresh(user)

    token = create_db_session(db, user.id)
    response = RedirectResponse(f"{settings.frontend_url_clean}/app?token={token}")
    set_session_cookie(response, token)
    return response

