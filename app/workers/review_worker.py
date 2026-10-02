import json
import logging
import datetime
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.review import Review
from app.models.finding import Finding
from app.models.review_file import ReviewFile
from app.analysis.scanner import scan_directory
from app.analysis.evidence_verifier import verify_findings
from app.analysis.deduplicator import deduplicate_findings
from app.analysis.scorer import calculate_deterministic_scores
from app.hindsight.recall import recall_learnings_for_review
from app.hindsight.learning import retain_learnings_from_review
from app.llm.groq_client import groq_client

logger = logging.getLogger("codemind.workers.review")

def update_review_status(db: Session, review_id: str, status: str, message: str):
    review = db.query(Review).filter(Review.id == review_id).first()
    if review:
        review.status = status
        review.status_message = message
        db.commit()

async def run_review_pipeline(review_id: str, target_dir: str, project_name: str):
    """
    Execute evidence-based AI Code Review Pipeline with Hindsight Memory Loop.
    Pipeline stages:
    1. Repository Scan & File Discovery
    2. Python AST & Static Analysis
    3. Recall Hindsight Vector Memories
    4. Groq LLM Code Synthesis
    5. Evidence Verification Stage
    6. Deduplication & Signal Merging
    7. Deterministic Score Calculation
    8. Retain Learnings into Hindsight
    9. Complete Review
    """
    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            logger.error(f"Review {review_id} not found in database.")
            return

        # 1. Scanning & File Discovery
        update_review_status(db, review_id, "Files Discovered", "Scanning codebase and discovering files...")
        files_data, static_findings, primary_languages = scan_directory(target_dir)

        if not files_data:
            update_review_status(db, review_id, "Failed", "No readable source files found in target directory.")
            review.completed_at = datetime.datetime.utcnow()
            db.commit()
            return

        # Save files to database
        for fd in files_data:
            rf = ReviewFile(
                review_id=review_id,
                path=fd["path"],
                language=fd["language"],
                content=fd["content"],
                size=fd["size"]
            )
            db.add(rf)

        review.file_count = len(files_data)
        review.languages = json.dumps(primary_languages)
        db.commit()

        # 2. Static Analysis & AST Scanning
        update_review_status(db, review_id, "Static Analysis", f"Ran AST and static analysis on {len(files_data)} files. Flagged {len(static_findings)} preliminary candidates.")

        # 3. Recall Hindsight Memory
        update_review_status(db, review_id, "Recall Hindsight Memory", "Querying Hindsight memory bank for past review learnings...")
        filenames = [f["path"] for f in files_data]
        recalled_memories = await recall_learnings_for_review(primary_languages, filenames)
        review.hindsight_memories_recalled = len(recalled_memories)
        db.commit()

        # 4. AI Reasoning (Groq)
        update_review_status(db, review_id, "AI Reasoning", f"Synthesizing codebase with Groq LLM & {len(recalled_memories)} recalled memories...")
        report_data = await groq_client.analyze_code(files_data, static_findings, recalled_memories)
        raw_llm_findings = report_data.get("findings", [])

        # Merge static findings and LLM findings
        all_candidate_findings = []

        for sf in static_findings:
            all_candidate_findings.append({
                "title": sf.get("title", "Static Rule Warning"),
                "category": sf.get("category", "Security"),
                "severity": sf.get("severity", "Medium"),
                "file_path": sf.get("file_path", "General"),
                "line_number": sf.get("line_number", 1),
                "snippet": sf.get("snippet", ""),
                "description": sf.get("description") or sf.get("message", "Static issue flagged during automated scanning."),
                "rationale": sf.get("rationale", "Automated code analysis rule matched target pattern."),
                "fix_recommendation": sf.get("fix") or sf.get("fix_recommendation", "Review pattern and refactor code."),
                "confidence": sf.get("confidence", 90),
                "evidence": sf.get("evidence", ["Flagged by AST static analyzer"]),
                "memory_influenced": False,
                "hindsight_memory_text": None
            })

        for lf in raw_llm_findings:
            all_candidate_findings.append({
                "title": lf.get("title", "Code Issue"),
                "category": lf.get("category", "Quality"),
                "severity": lf.get("severity", "Medium"),
                "file_path": lf.get("file_path") or lf.get("file", "General"),
                "line_number": lf.get("line_number") or lf.get("line_start", 1),
                "line_end": lf.get("line_end"),
                "snippet": lf.get("snippet") or lf.get("code_snippet", ""),
                "description": lf.get("description", ""),
                "rationale": lf.get("rationale") or lf.get("impact", ""),
                "fix_recommendation": lf.get("fix_recommendation") or lf.get("suggested_fix", ""),
                "confidence": lf.get("confidence", 85),
                "evidence": lf.get("evidence", ["Verified by Groq LLM code reasoning"]),
                "memory_influenced": lf.get("memory_influenced", False),
                "hindsight_memory_text": lf.get("hindsight_memory_text")
            })

        # 5. Evidence Verification Stage
        update_review_status(db, review_id, "Evidence Verification", "Verifying findings against source code evidence...")
        verified_candidates = verify_findings(files_data, all_candidate_findings)

        # 6. Deduplication & Signal Merging
        update_review_status(db, review_id, "Deduplication", "Merging duplicate findings and consolidating detection signals...")
        final_findings = deduplicate_findings(verified_candidates)

        # 7. Deterministic Scoring
        update_review_status(db, review_id, "Scoring", "Calculating deterministic quality and security scores...")
        overall_score, quality_score, security_score, maintainability_score, reliability_score = calculate_deterministic_scores(final_findings)

        review.summary = report_data.get("summary") or f"Executed evidence-based code review on {len(files_data)} source file(s)."
        review.quality_score = quality_score
        review.security_score = security_score
        review.maintainability_score = maintainability_score

        critical_c = 0
        high_c = 0
        medium_c = 0
        low_c = 0

        for f_data in final_findings:
            sev = f_data.get("severity", "Medium").capitalize()
            if sev == "Critical": critical_c += 1
            elif sev == "High": high_c += 1
            elif sev == "Medium": medium_c += 1
            else: low_c += 1

            evidence_val = f_data.get("evidence", [])
            evidence_json = json.dumps(evidence_val) if isinstance(evidence_val, list) else str(evidence_val)

            finding = Finding(
                review_id=review_id,
                title=f_data.get("title", "Issue"),
                category=f_data.get("category", "Quality"),
                severity=sev,
                file_path=f_data.get("file_path", "General"),
                line_number=f_data.get("line_number", 1),
                line_end=f_data.get("line_end"),
                snippet=f_data.get("snippet", ""),
                description=f_data.get("description", ""),
                rationale=f_data.get("rationale", ""),
                fix_recommendation=f_data.get("fix_recommendation", ""),
                confidence=int(f_data.get("confidence", 90)),
                evidence=evidence_json,
                memory_influenced=f_data.get("memory_influenced", False),
                hindsight_memory_text=f_data.get("hindsight_memory_text")
            )
            db.add(finding)

        review.critical_count = critical_c
        review.high_count = high_c
        review.medium_count = medium_c
        review.low_count = low_c
        db.commit()

        # 8. Retain Learnings into Hindsight
        update_review_status(db, review_id, "Retaining Learning", "Extracting new durable learnings and retaining into Hindsight...")
        retained_count = await retain_learnings_from_review(project_name, primary_languages, final_findings)
        review.hindsight_learnings_retained = retained_count
        db.commit()

        # 9. Completed
        review.completed_at = datetime.datetime.utcnow()
        update_review_status(db, review_id, "Completed", "Code review completed successfully!")
        logger.info(f"Review {review_id} completed successfully.")

    except Exception as e:
        logger.error(f"Error executing review pipeline for {review_id}: {e}", exc_info=True)
        update_review_status(db, review_id, "Failed", f"Review processing error: {str(e)}")
    finally:
        db.close()
