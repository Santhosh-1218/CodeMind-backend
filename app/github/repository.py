import os
import io
import shutil
import zipfile
import tempfile
import httpx
import logging
import subprocess
from typing import Tuple, Optional
from app.github.validator import validate_github_url

logger = logging.getLogger("codemind.github.repository")

async def download_github_repository(repo_url: str, target_dir: str, access_token: Optional[str] = None) -> Tuple[bool, str]:
    """
    Safely download and extract a GitHub repository into target_dir.
    Supports public repositories and authenticated private repos (if access_token provided).
    Returns (success, message).
    """
    is_valid, owner, repo, err_msg = validate_github_url(repo_url)
    if not is_valid:
        return False, err_msg

    downloaded = False
    headers = {
        "User-Agent": "CodeMind-AI-Review-Agent",
        "Accept": "application/vnd.github+json"
    }
    if access_token:
        headers["Authorization"] = f"token {access_token}"

    # Primary approach: API Zipball
    zip_urls = [
        f"https://api.github.com/repos/{owner}/{repo}/zipball",
        f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip",
        f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip",
    ]

    for zip_url in zip_urls:
        logger.info(f"Attempting download of GitHub repo archive: {zip_url}")
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60.0, headers=headers) as client:
                res = await client.get(zip_url)
                if res.status_code == 200 and len(res.content) > 0:
                    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
                        zf.extractall(target_dir)
                    downloaded = True
                    logger.info(f"Successfully downloaded and extracted GitHub archive for {owner}/{repo}")
                    break
        except Exception as e:
            logger.info(f"Failed zip download for URL '{zip_url}': {e}")

    # Fallback approach: git clone --depth 1
    if not downloaded:
        logger.info(f"Falling back to git clone --depth 1 for {repo_url}")
        try:
            clone_dir = os.path.join(target_dir, "_git_clone_tmp")
            if access_token:
                clone_url = f"https://x-access-token:{access_token}@github.com/{owner}/{repo}.git"
            else:
                clone_url = f"https://github.com/{owner}/{repo}.git"

            git_env = dict(os.environ)
            git_env["GIT_TERMINAL_PROMPT"] = "0"

            res = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, clone_dir],
                capture_output=True,
                text=True,
                timeout=60,
                env=git_env
            )
            if res.returncode == 0 and os.path.exists(clone_dir):
                for item in os.listdir(clone_dir):
                    s = os.path.join(clone_dir, item)
                    d = os.path.join(target_dir, item)
                    shutil.move(s, d)
                shutil.rmtree(clone_dir, ignore_errors=True)
                downloaded = True
            else:
                err_text = res.stderr if res.stderr else "Git clone failed"
                if any(k in err_text for k in ["could not read Username", "Authentication failed", "Repository not found", "terminal prompts disabled", "404"]):
                    return False, f"Could not access repository '{owner}/{repo}'. Please ensure the URL is correct and the repository is public (or upload as ZIP)."
                return False, f"Could not clone repository: {err_text[:180]}"
        except Exception as e:
            return False, f"Failed to download repository: {e}"

    if not downloaded:
        return False, "Failed to download GitHub repository. Ensure the repository URL is correct and public (or upload as ZIP)."

    # If extracted folder has a single top-level folder e.g. repo-main, move contents up
    extracted_items = [i for i in os.listdir(target_dir) if i != "_git_clone_tmp"]
    if len(extracted_items) == 1:
        sub_path = os.path.join(target_dir, extracted_items[0])
        if os.path.isdir(sub_path):
            for item in os.listdir(sub_path):
                s = os.path.join(sub_path, item)
                d = os.path.join(target_dir, item)
                shutil.move(s, d)
            os.rmdir(sub_path)

    return True, f"Successfully loaded repository '{owner}/{repo}'"
