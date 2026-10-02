import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger("codemind.analysis.verifier")

def verify_findings(
    files_data: List[Dict[str, Any]],
    findings: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Evidence Verification Stage.
    Validates every finding against actual source code in files_data.
    Prevents hallucinated or unsupported findings.
    """
    files_map = {f["path"]: f["content"].splitlines() for f in files_data}
    verified_findings = []

    for f in findings:
        file_path = f.get("file_path", "")
        line_no = f.get("line_number", 1)
        snippet = f.get("snippet", "").strip()

        # 1. Check if file exists
        if file_path not in files_map:
            logger.info(f"Downgrading unverified finding: file {file_path} not found in repository.")
            f["confidence"] = 30
            f["title"] = f"Possible Issue: {f.get('title')} (Manual Review Recommended)"
            f["evidence"] = ["File path not present in submitted codebase; flagged for manual review."]
            verified_findings.append(f)
            continue

        file_lines = files_map[file_path]
        total_lines = len(file_lines)

        # 2. Line number range check
        if line_no < 1 or line_no > total_lines:
            line_no = min(max(1, line_no), total_lines)
            f["line_number"] = line_no

        # 3. Locate exact line or nearby snippet match (+- 5 lines)
        matched_line_no = line_no
        found_exact = False
        actual_code_line = file_lines[line_no - 1].strip() if total_lines > 0 else ""

        if snippet:
            # Check exact line
            if snippet in actual_code_line or actual_code_line in snippet:
                found_exact = True
            else:
                # Search window +- 5 lines
                start_win = max(0, line_no - 6)
                end_win = min(total_lines, line_no + 5)
                for idx in range(start_win, end_win):
                    line_text = file_lines[idx].strip()
                    if snippet in line_text or line_text in snippet:
                        matched_line_no = idx + 1
                        actual_code_line = line_text
                        found_exact = True
                        f["line_number"] = matched_line_no
                        break

        # 4. False Positive Analysis & Safety Guards
        is_false_positive = False

        # SQL Injection FP check: if query uses parameter placeholders like `?`, `%s`, `:param` with tuple/dict args
        if "SQL" in f.get("title", "") or "SQL" in f.get("category", ""):
            # If the code line shows parameterized execute call: e.g. execute(sql, (arg,))
            if re.search(r"execute\s*\(\s*['\"].*?\?\s*['\"]\s*,\s*\(", actual_code_line) or \
               re.search(r"execute\s*\(\s*['\"].*?%s\s*['\"]\s*,\s*\(", actual_code_line):
                is_false_positive = True

        # Secret FP check: placeholder comments or env checks
        if "Secret" in f.get("title", "") or "Key" in f.get("title", ""):
            if "os.getenv" in actual_code_line or "process.env" in actual_code_line or "YOUR_API_KEY" in actual_code_line:
                is_false_positive = True

        if is_false_positive:
            logger.info(f"Filtered false positive finding at {file_path}:{matched_line_no}: {f.get('title')}")
            continue

        # 5. Build verified evidence list
        evidence_list = f.get("evidence", [])
        if not isinstance(evidence_list, list):
            evidence_list = [str(evidence_list)]

        evidence_list.append(f"Confirmed file existence: {file_path}")
        if found_exact:
            evidence_list.append(f"Matched source code snippet at line {matched_line_no}")
            f["confidence"] = max(f.get("confidence", 85), 90)
        else:
            evidence_list.append(f"Contextual code line inspected: '{actual_code_line[:60]}...'")
            f["confidence"] = min(f.get("confidence", 70), 75)

        if f.get("memory_influenced"):
            evidence_list.append("Supported by Hindsight vector memory recall")

        f["snippet"] = actual_code_line if actual_code_line else snippet
        f["evidence"] = list(dict.fromkeys(evidence_list)) # Deduplicate evidence strings
        verified_findings.append(f)

    return verified_findings
