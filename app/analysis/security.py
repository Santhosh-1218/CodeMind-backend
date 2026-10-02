import re
from typing import List, Dict, Any

SECURITY_RULES = [
    {
        "id": "SEC-001",
        "pattern": r"(api[_-]?key|secret|password|passwd|private[_-]?key)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]",
        "title": "Hardcoded API Key or Secret",
        "severity": "Critical",
        "category": "Security",
        "message": "Possible hardcoded secret or API key detected in source code.",
        "fix": "Store secrets in environment variables or a key management service."
    },
    {
        "id": "SEC-002",
        "pattern": r"SELECT\s+.*\s+FROM\s+.*WHERE\s+.*%|SELECT\s+.*\s+FROM\s+.*WHERE\s+.*\+\s*\w+|f['\"].*SELECT\s+.*\s+FROM",
        "title": "Potential SQL Injection",
        "severity": "Critical",
        "category": "Security",
        "message": "Dynamic string construction or interpolation in SQL query.",
        "fix": "Use parameterized queries or ORM query bindings."
    },
    {
        "id": "SEC-003",
        "pattern": r"\beval\(|\bexec\(|child_process\.exec\(",
        "title": "Unsafe Dynamic Code Execution",
        "severity": "High",
        "category": "Security",
        "message": "Use of eval() or exec() can allow arbitrary code execution.",
        "fix": "Avoid dynamic code execution; use safe parsing or explicit control logic."
    },
    {
        "id": "SEC-004",
        "pattern": r"innerHTML\s*=|dangerouslySetInnerHTML",
        "title": "Potential Cross-Site Scripting (XSS)",
        "severity": "High",
        "category": "Security",
        "message": "Direct innerHTML assignment without sanitization.",
        "fix": "Sanitize user input before DOM insertion or use safe React/DOM bindings."
    },
    {
        "id": "SEC-005",
        "pattern": r"verify\s*=\s*False|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]0['\"]",
        "title": "Disabled TLS/SSL Verification",
        "severity": "High",
        "category": "Security",
        "message": "Disabling SSL/TLS certificate validation enables Man-in-the-Middle attacks.",
        "fix": "Enable strict TLS certificate verification."
    }
]

def scan_security_rules(file_path: str, content: str) -> List[Dict[str, Any]]:
    findings = []
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        for rule in SECURITY_RULES:
            if re.search(rule["pattern"], line, re.IGNORECASE):
                findings.append({
                    "rule_id": rule["id"],
                    "title": rule["title"],
                    "severity": rule["severity"],
                    "category": rule["category"],
                    "file_path": file_path,
                    "line_number": idx,
                    "snippet": line.strip(),
                    "message": rule["message"],
                    "fix": rule["fix"]
                })
    return findings
