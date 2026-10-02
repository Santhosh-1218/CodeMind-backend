import os
import shutil
import subprocess
import logging
from typing import List, Dict, Any, Tuple
from app.analysis.language_detector import detect_language, detect_primary_languages
from app.analysis.security import scan_security_rules
from app.analysis.ast_analyzer import analyze_python_ast

logger = logging.getLogger("codemind.analysis.scanner")

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv", ".next",
    "build", "dist", "out", ".pytest_cache", ".idea", ".vscode"
}

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".cc", ".h", ".hpp", ".sql", ".sh", ".json", ".yaml", ".yml", "dockerfile"
}

MAX_FILE_SIZE_BYTES = 500 * 1024 # 500 KB per file
MAX_TOTAL_FILES = 100

def scan_directory(target_dir: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Traverse codebase directory safely.
    Returns: (files_data, static_findings, primary_languages)
    files_data: [{'path': relative_path, 'language': lang, 'content': text, 'size': int}]
    """
    files_data = []
    static_findings = []
    all_paths = []

    for root, dirs, files in os.walk(target_dir):
        # Skip ignored directories & prevent path traversal
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in ALLOWED_EXTENSIONS and file.lower() != "dockerfile":
                continue

            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, target_dir).replace("\\", "/")

            try:
                size = os.path.getsize(full_path)
                if size > MAX_FILE_SIZE_BYTES:
                    continue

                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                lang = detect_language(rel_path)
                files_data.append({
                    "path": rel_path,
                    "language": lang,
                    "content": content,
                    "size": size
                })
                all_paths.append(rel_path)

                # 1. Python AST Analysis
                if lang == "Python":
                    ast_issues = analyze_python_ast(rel_path, content)
                    static_findings.extend(ast_issues)

                # 2. Static Security Rules
                sec_findings = scan_security_rules(rel_path, content)
                static_findings.extend(sec_findings)

                if len(files_data) >= MAX_TOTAL_FILES:
                    logger.warning(f"Reached maximum file scan cap ({MAX_TOTAL_FILES} files).")
                    break
            except Exception as e:
                logger.error(f"Error reading file {rel_path}: {e}")

        if len(files_data) >= MAX_TOTAL_FILES:
            break

    primary_languages = detect_primary_languages(all_paths)
    return files_data, static_findings, primary_languages
