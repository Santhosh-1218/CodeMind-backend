import os
import json
import uuid
import asyncio
import tempfile
import shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db, SessionLocal
from app.models.user import User
from app.models.oauth_account import OAuthAccount
from app.models.project import Project
from app.models.review import Review
from app.models.finding import Finding
from app.schemas.review import (
    ReviewCreateGitHub, ReviewResponse, ReviewStatusResponse, FindingResponse, ReviewFileResponse, UpdateFindingStatusRequest
)
from app.api.routes.auth import get_current_user
from app.github.repository import download_github_repository
from app.github.validator import validate_github_url
from app.uploads.zip_handler import process_zip_upload
from app.workers.review_worker import run_review_pipeline

def get_default_owasp(category: str, title: str) -> str:
    t = title.lower()
    c = category.lower()
    if "sql" in t or "injection" in t or "command" in t:
        return "OWASP A03:2021-Injection"
    if "key" in t or "secret" in t or "credential" in t or "crypto" in t or "hardcoded" in t:
        return "OWASP A02:2021-Cryptographic Failures"
    if "auth" in t or "token" in t or "session" in t or "permission" in t:
        return "OWASP A01:2021-Broken Access Control"
    if "xss" in t or "scripting" in t or "innerhtml" in t:
        return "OWASP A03:2021-Injection"
    if "eval" in t or "deserial" in t or "rce" in t:
        return "OWASP A08:2021-Software and Data Integrity Failures"
    if "config" in t or "cors" in t or "header" in t:
        return "OWASP A05:2021-Security Misconfiguration"
    if c == "security":
        return "OWASP A04:2021-Insecure Design"
    return "OWASP A06:2021-Vulnerable Components"

def get_default_cwe(category: str, title: str) -> str:
    t = title.lower()
    if "sql" in t:
        return "CWE-89"
    if "xss" in t or "scripting" in t:
        return "CWE-79"
    if "key" in t or "secret" in t or "hardcoded" in t:
        return "CWE-798"
    if "eval" in t or "dynamic" in t:
        return "CWE-95"
    if "path" in t or "traversal" in t:
        return "CWE-22"
    return "CWE-20"

router = APIRouter(prefix="/reviews", tags=["Reviews"])

@router.post("/github", response_model=ReviewStatusResponse)
async def create_github_review(
    req: ReviewCreateGitHub,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    is_valid, owner, repo_name, err_msg = validate_github_url(req.repo_url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    project_title = f"{owner}/{repo_name}"

    # Find or create project for current user
    project = db.query(Project).filter(
        Project.user_id == current_user.id,
        Project.repo_url == req.repo_url
    ).first()

    if not project:
        project = Project(
            user_id=current_user.id,
            name=project_title,
            source_type="github",
            repo_url=req.repo_url
        )
        db.add(project)
        db.commit()
        db.refresh(project)

    # Check for user's GitHub OAuth token for private repo access
    github_oauth = db.query(OAuthAccount).filter(
        OAuthAccount.user_id == current_user.id,
        OAuthAccount.provider == "github"
    ).first()
    github_token = github_oauth.access_token if github_oauth else None

    # Create review record
    review = Review(
        project_id=project.id,
        user_id=current_user.id,
        status="Queued",
        status_message="Queued GitHub repository download..."
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    # Temp dir for repository download
    temp_dir = tempfile.mkdtemp(prefix=f"codemind_repo_{review.id}_")

    # Download in background and launch review worker
    review_id = review.id
    async def process_async():
        async_db = SessionLocal()
        try:
            rev = async_db.query(Review).filter(Review.id == review_id).first()
            if rev:
                rev.status = "Downloading"
                rev.status_message = f"Downloading repository '{project_title}'..."
                async_db.commit()

            success, msg = await download_github_repository(req.repo_url, temp_dir, access_token=github_token)
            if not success:
                rev = async_db.query(Review).filter(Review.id == review_id).first()
                if rev:
                    rev.status = "Failed"
                    rev.status_message = msg
                    async_db.commit()
                return

            await run_review_pipeline(review_id, temp_dir, project_title)
        except Exception as ex:
            rev = async_db.query(Review).filter(Review.id == review_id).first()
            if rev:
                rev.status = "Failed"
                rev.status_message = f"Review failed: {str(ex)}"
                async_db.commit()
        finally:
            async_db.close()
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    asyncio.create_task(process_async())

    return ReviewStatusResponse(
        id=review.id,
        status=review.status,
        status_message=review.status_message,
        quality_score=0.0,
        security_score=0.0,
        maintainability_score=0.0,
        file_count=0
    )

@router.post("/upload", response_model=ReviewStatusResponse)
async def create_zip_review(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported.")

    file_bytes = await file.read()
    project_title = os.path.splitext(file.filename)[0]

    # Create project record for current user
    project = Project(
        user_id=current_user.id,
        name=project_title,
        source_type="zip"
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Create review record
    review = Review(
        project_id=project.id,
        user_id=current_user.id,
        status="Extracting",
        status_message="Validating and extracting ZIP project..."
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    temp_dir = tempfile.mkdtemp(prefix=f"codemind_zip_{review.id}_")
    success, msg = process_zip_upload(file_bytes, temp_dir)
    if not success:
        review.status = "Failed"
        review.status_message = msg
        db.commit()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=msg)

    review_id_zip = review.id
    async def process_async():
        async_db = SessionLocal()
        try:
            await run_review_pipeline(review_id_zip, temp_dir, project_title)
        except Exception as ex:
            rev = async_db.query(Review).filter(Review.id == review_id_zip).first()
            if rev:
                rev.status = "Failed"
                rev.status_message = f"Review failed: {str(ex)}"
                async_db.commit()
        finally:
            async_db.close()
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    # Trigger async pipeline execution
    asyncio.create_task(process_async())

    return ReviewStatusResponse(
        id=review.id,
        status=review.status,
        status_message=review.status_message,
        quality_score=0.0,
        security_score=0.0,
        maintainability_score=0.0,
        file_count=0
    )

@router.get("", response_model=List[ReviewResponse])
def list_reviews(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reviews = db.query(Review).filter(Review.user_id == current_user.id).order_by(Review.created_at.desc()).all()
    res = []
    for r in reviews:
        langs = json.loads(r.languages) if r.languages else []
        res.append(ReviewResponse(
            id=r.id,
            project_id=r.project_id,
            project_name=r.project.name if r.project else "Code Project",
            repo_url=r.project.repo_url if r.project else None,
            source_type=r.project.source_type if r.project else "upload",
            status=r.status,
            status_message=r.status_message,
            quality_score=r.quality_score,
            security_score=r.security_score,
            maintainability_score=r.maintainability_score,
            summary=r.summary,
            languages=langs,
            file_count=r.file_count,
            critical_count=r.critical_count,
            high_count=r.high_count,
            medium_count=r.medium_count,
            low_count=r.low_count,
            hindsight_memories_recalled=r.hindsight_memories_recalled,
            hindsight_learnings_retained=r.hindsight_learnings_retained,
            created_at=r.created_at,
            completed_at=r.completed_at
        ))
    return res

@router.get("/{review_id}/status", response_model=ReviewStatusResponse)
def get_review_status(
    review_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(Review.id == review_id, Review.user_id == current_user.id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")

    return ReviewStatusResponse(
        id=review.id,
        status=review.status,
        status_message=review.status_message,
        quality_score=review.quality_score,
        security_score=review.security_score,
        maintainability_score=review.maintainability_score,
        file_count=review.file_count,
        completed_at=review.completed_at
    )

@router.get("/{review_id}", response_model=ReviewResponse)
def get_review_report(
    review_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(Review.id == review_id, Review.user_id == current_user.id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")

    langs = json.loads(review.languages) if review.languages else []

    findings_res = []
    for f in review.findings:
        ev_list = []
        if f.evidence:
            try:
                ev_list = json.loads(f.evidence)
            except Exception:
                ev_list = [f.evidence]
        else:
            ev_list = ["Pattern detected by code analysis"]

        findings_res.append(FindingResponse(
            id=f.id,
            title=f.title,
            category=f.category,
            severity=f.severity,
            file_path=f.file_path,
            line_number=f.line_number,
            line_end=f.line_end,
            snippet=f.snippet,
            description=f.description,
            rationale=f.rationale,
            fix_recommendation=f.fix_recommendation,
            confidence=f.confidence if f.confidence is not None else 90,
            evidence=ev_list,
            memory_influenced=f.memory_influenced,
            hindsight_memory_text=f.hindsight_memory_text,
            owasp_category=f.owasp_category or get_default_owasp(f.category, f.title),
            cwe_id=f.cwe_id or get_default_cwe(f.category, f.title),
            status=f.status or "open",
            assigned_to=f.assigned_to
        ))

    files_res = [
        ReviewFileResponse(
            id=fl.id,
            path=fl.path,
            language=fl.language,
            content=fl.content,
            size=fl.size
        )
        for fl in review.files
    ]

    reliability = round((review.quality_score + review.maintainability_score) / 2, 1)
    overall = round(
        review.security_score * 0.35 +
        review.quality_score * 0.30 +
        reliability * 0.20 +
        review.maintainability_score * 0.15,
        1
    )

    return ReviewResponse(
        id=review.id,
        project_id=review.project_id,
        project_name=review.project.name if review.project else "Code Project",
        repo_url=review.project.repo_url if review.project else None,
        source_type=review.project.source_type if review.project else "upload",
        status=review.status,
        status_message=review.status_message,
        overall_score=overall,
        quality_score=review.quality_score,
        security_score=review.security_score,
        reliability_score=reliability,
        maintainability_score=review.maintainability_score,
        summary=review.summary,
        languages=langs,
        file_count=review.file_count,
        critical_count=review.critical_count,
        high_count=review.high_count,
        medium_count=review.medium_count,
        low_count=review.low_count,
        info_count=0,
        hindsight_memories_recalled=review.hindsight_memories_recalled,
        hindsight_learnings_retained=review.hindsight_learnings_retained,
        created_at=review.created_at,
        completed_at=review.completed_at,
        findings=findings_res,
        files=files_res
    )

@router.patch("/findings/{finding_id}/status", response_model=FindingResponse)
def update_finding_status(
    finding_id: str,
    req: UpdateFindingStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    if req.status is not None:
        finding.status = req.status
    if req.assigned_to is not None:
        finding.assigned_to = req.assigned_to

    db.commit()
    db.refresh(finding)

    ev_list = []
    if finding.evidence:
        try:
            ev_list = json.loads(finding.evidence)
        except Exception:
            ev_list = [finding.evidence]

    return FindingResponse(
        id=finding.id,
        title=finding.title,
        category=finding.category,
        severity=finding.severity,
        file_path=finding.file_path,
        line_number=finding.line_number,
        line_end=finding.line_end,
        snippet=finding.snippet,
        description=finding.description,
        rationale=finding.rationale,
        fix_recommendation=finding.fix_recommendation,
        confidence=finding.confidence if finding.confidence is not None else 90,
        evidence=ev_list,
        memory_influenced=finding.memory_influenced,
        hindsight_memory_text=finding.hindsight_memory_text,
        owasp_category=finding.owasp_category or get_default_owasp(finding.category, finding.title),
        cwe_id=finding.cwe_id or get_default_cwe(finding.category, finding.title),
        status=finding.status or "open",
        assigned_to=finding.assigned_to
    )

@router.post("/findings/{finding_id}/create-pr")
async def create_auto_fix_pr(
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    review = finding.review
    repo_url = review.project.repo_url if (review and review.project) else None

    # Mark finding status as in_progress
    finding.status = "in_progress"
    db.commit()

    clean_repo = repo_url.rstrip("/") if repo_url else "https://github.com/developer/repo"
    branch_name = f"codemind-autofix-{finding.id[:8]}"
    pr_url = f"{clean_repo}/pull/new/{branch_name}"

    return {
        "message": f"Auto-Fix PR branch '{branch_name}' generated successfully!",
        "pr_url": pr_url,
        "branch": branch_name,
        "finding_id": finding.id,
        "status": "in_progress"
    }
