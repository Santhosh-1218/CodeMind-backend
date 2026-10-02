import re
from typing import Tuple, Optional

GITHUB_URL_REGEX = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+?)(?:\.git)?(?:/)?$"
)

def validate_github_url(url: str) -> Tuple[bool, Optional[str], Optional[str], str]:
    """
    Validate public GitHub repository URL and extract owner & repo.
    Returns: (is_valid, owner, repo, error_message)
    """
    if not url:
        return False, None, None, "Repository URL cannot be empty."

    cleaned_url = url.strip()
    match = GITHUB_URL_REGEX.match(cleaned_url)
    if not match:
        return False, None, None, "Invalid GitHub repository URL. Format must be https://github.com/owner/repository"

    owner, repo = match.group(1), match.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]

    # SSRF & path sanity checks
    if ".." in owner or ".." in repo or "/" in owner or "/" in repo or "@" in owner or "@" in repo:
        return False, None, None, "Malicious repository path detected."

    return True, owner, repo, ""
