import os
import json
import logging
from typing import Optional
from fastapi import APIRouter, Request, Header, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.review import Review
from app.core.config import settings
from app.workers.review_worker import run_review_pipeline

logger = logging.getLogger("codemind.webhooks")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.get("/config")
def get_webhook_config():
    webhook_url = f"{settings.backend_url_clean}/api/webhooks/github"
    return {
        "webhook_url": webhook_url,
        "content_type": "application/json",
        "events": ["pull_request", "push"],
        "secret_status": "active",
        "instructions": [
            "Go to your GitHub Repository -> Settings -> Webhooks -> Add webhook.",
            f"Set Payload URL to: {webhook_url}",
            "Set Content type to: application/json",
            "Select events: 'Let me select individual events' -> Check 'Pull requests' & 'Pushes'.",
            "Click 'Add webhook' to enable automatic CodeMind CI/CD code reviews on PR open!"
        ]
    }

@router.post("/github")
async def github_webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    body = await request.body()

    # Ping event check
    if x_github_event == "ping":
        return {"status": "pong", "message": "CodeMind webhook endpoint connected successfully!"}

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # We process pull_request or push events
    if x_github_event and x_github_event not in ["pull_request", "push", "ping"]:
        return {"status": "ignored", "event": x_github_event, "message": "Only pull_request and push events trigger code reviews."}

    repo_data = payload.get("repository", {})
    repo_url = repo_data.get("html_url") or repo_data.get("clone_url")
    repo_name = repo_data.get("name") or "GitHub Repository"

    if not repo_url:
        raise HTTPException(status_code=400, detail="Missing repository URL in webhook payload")

    # Pull Request specific metadata
    pr_number = None
    if x_github_event == "pull_request":
        pr_data = payload.get("pull_request", {})
        pr_number = payload.get("number") or pr_data.get("number")
        action = payload.get("action")
        if action and action not in ["opened", "synchronize", "reopened"]:
            return {"status": "ignored", "action": action, "message": f"PR action '{action}' does not require new review scan."}

    # Find system/bot user or first user
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=400, detail="No registered users found in system to assign review.")

    # Find or create project
    project = db.query(Project).filter(Project.repo_url == repo_url, Project.user_id == user.id).first()
    if not project:
        project = Project(
            user_id=user.id,
            name=f"{repo_name} (PR #{pr_number})" if pr_number else repo_name,
            source_type="github",
            repo_url=repo_url
        )
        db.add(project)
        db.commit()
        db.refresh(project)

    # Create Review record
    review = Review(
        project_id=project.id,
        user_id=user.id,
        status="Processing",
        status_message=f"CI/CD Webhook Scan Triggered for PR #{pr_number}" if pr_number else "CI/CD Webhook Scan Triggered"
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    # Trigger background pipeline
    background_tasks.add_task(run_review_pipeline, review.id, repo_url, "github")

    return {
        "status": "triggered",
        "review_id": review.id,
        "event": x_github_event or "pull_request",
        "pr_number": pr_number,
        "project_name": project.name,
        "message": f"CodeMind CI/CD review successfully queued for {repo_name}!"
    }
