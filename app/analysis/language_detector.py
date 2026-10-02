import os
from typing import Dict, List

EXTENSION_MAP: Dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C/C++ Header",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".sql": "SQL",
    ".sh": "Shell",
    ".yaml": "YAML",
    ".yml": "YAML"
}

def detect_language(file_path: str) -> str:
    """Detect language based on file extension."""
    _, ext = os.path.splitext(file_path.lower())
    return EXTENSION_MAP.get(ext, "Text")

def detect_primary_languages(file_paths: List[str]) -> List[str]:
    """Return unique list of primary programming languages found in codebase."""
    lang_counts: Dict[str, int] = {}
    for path in file_paths:
        lang = detect_language(path)
        if lang not in ["Text", "JSON", "HTML", "CSS", "YAML"]:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    
    sorted_langs = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)
    return [lang for lang, count in sorted_langs] or ["Text"]
