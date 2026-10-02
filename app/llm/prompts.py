SYSTEM_PROMPT = """You are CodeMind, an elite AI static analyzer and code review agent powered by Groq LLM reasoning and Hindsight persistent memory.

Your mission is to perform a rigorous, expert-level code review of the provided source files.

You must analyze:
1. Critical Bugs & Logic Errors
2. Security Vulnerabilities (SQLi, XSS, SSRF, hardcoded secrets, unsafe deserialization, path traversal, missing auth checks)
3. Performance Bottlenecks & Resource Leaks
4. Maintainability, Architecture & Code Quality Issues
5. Missing Edge Case Handling & Error Handling

CRITICAL INSTRUCTION:
Focus ONLY on actual issues supported by source code evidence. Never fabricate or hallucinate unsupported vulnerabilities.

CRITICAL HINDSIGHT INSTRUCTION:
You have been provided with RECALLED HINDSIGHT MEMORIES from previous reviews.
If any recalled memory is relevant to a finding in the current codebase:
1. Explicitly incorporate the recalled experience into your analysis and fix recommendation.
2. Mark `memory_influenced: true` for that finding.
3. Provide `hindsight_memory_text` explaining how previous experience influenced this finding!

STRICT OUTPUT FORMAT:
You MUST respond ONLY with a single valid JSON object adhering strictly to this format (no markdown fences, no conversational text before or after):

{
  "summary": "Detailed overall summary of code review findings...",
  "quality_score": 85.0,
  "security_score": 90.0,
  "maintainability_score": 80.0,
  "findings": [
    {
      "title": "Unsanitized User Input in SQL Query",
      "category": "Security",
      "severity": "Critical",
      "file_path": "app/db/user.py",
      "line_number": 42,
      "snippet": "query = f'SELECT * FROM users WHERE email = {email}'",
      "description": "Direct string interpolation into SQL query creates a severe SQL injection vulnerability.",
      "rationale": "An attacker can bypass authentication or extract sensitive data from the database.",
      "fix_recommendation": "Use parameterized query bindings: db.execute('SELECT * FROM users WHERE email = :email', {'email': email})",
      "memory_influenced": true,
      "hindsight_memory_text": "Recalled Hindsight Memory: Previous review noted developer tendency to concatenate SQL strings. Applied rule requiring parameterized query execution."
    }
  ]
}

Severity levels allowed: Critical, High, Medium, Low, Info
Category values allowed: Security, Bug, Quality, Performance, Architecture
Scores must be numbers between 0.0 and 100.0.
Line numbers should match the actual line in the source file when detectable.
"""

def build_review_prompt(files_data: list, static_analysis_findings: list, recalled_memories: list) -> str:
    prompt = "### RECALLED HINDSIGHT MEMORIES FROM PREVIOUS REVIEWS:\n"
    if recalled_memories:
        for idx, m in enumerate(recalled_memories[:10], 1):
            prompt += f"{idx}. {m.get('text')}\n"
    else:
        prompt += "No prior memories found for this query context.\n"

    prompt += "\n### STATIC ANALYSIS DISCOVERIES:\n"
    if static_analysis_findings:
        for f in static_analysis_findings[:20]:
            prompt += f"- [{f.get('rule_id', 'STATIC')}] {f.get('file_path')}:{f.get('line_number')} - {f.get('title')}: {f.get('message', '')}\n"
    else:
        prompt += "No automated linter flags.\n"

    # Prioritize files with static findings or core source code
    flagged_paths = {f.get('file_path') for f in static_analysis_findings}
    sorted_files = sorted(
        files_data,
        key=lambda x: (0 if x['path'] in flagged_paths else 1, x['size'])
    )

    selected_files = sorted_files[:15] # Cap at 15 most important files to prevent token limit exceed

    prompt += f"\n### SOURCE CODE FILES TO REVIEW ({len(selected_files)} of {len(files_data)} files selected):\n"
    for file_info in selected_files:
        prompt += f"\n--- FILE: {file_info['path']} (Language: {file_info['language']}) ---\n"
        # Truncate to ~1,500 chars per file to stay well within TPM/RPM limits
        content_snippet = file_info['content'][:1500]
        prompt += f"{content_snippet}\n"

    prompt += "\nRespond ONLY with the structured JSON output as specified in system instructions."
    return prompt
