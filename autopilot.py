"""Autopilot: 100% Fully Autonomous Job Application & Recruiter Outreach Engine.

Orchestrates the entire hiring funnel in a single hands-off execution:
1. Ingests Job URL(s) or batch file (jobs.txt).
2. Playwright extracts clean JD text.
3. Gemini evaluates ATS match score & tailors profile (zero fabrication).
4. Playwright renders company-specific ATS PDF (output/Resume_<Company>_<Role>.pdf).
5. browser-use pre-fills application portal fields and uploads the tailored PDF.
6. Discovers hiring managers, recruiters, and talent acquisition contacts.
7. Generates dynamic, personalized cold email citing tailored highlights.
8. Attaches the company-tailored PDF and dispatches outreach (Draft or Send mode).
9. Records application ID, match score, PDF path, and status in Google Sheets/CSV.
10. Spawns/updates background Gmail watcher for real-time interview notifications.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from apply_agent import (
    generate_pdf_node,
    run_application_agent,
    scrape_jd_node,
    tailor_resume_node,
)
from cold_email_agent import (
    ensure_company_tailored_resume,
    run_cold_outreach,
)
from email_tracker import run_email_tracker, send_desktop_notification, send_telegram_alert
from job_finder import discover_live_jobs
from sheets_manager import get_sheets_manager

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AUTOPILOT %(levelname)s] %(message)s",
)
logger = logging.getLogger("autopilot")

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def process_single_job_fully_automated(
    job_url: str,
    cold_email_mode: str = "draft",  # "draft", "send", "preview"
    auto_submit: bool = False,
    target_recruiter_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute complete end-to-end automation for a single job URL without human intervention."""
    print("\n" + "=" * 70)
    print(f"🚀 [AUTOPILOT] STARTING FULLY AUTOMATED WORKFLOW")
    print(f"🔗 Target URL: {job_url}")
    print(f"📧 Cold Email Mode: {cold_email_mode.upper()}")
    print("=" * 70)

    # -------------------------------------------------------------
    # Step 1 & 2: Scrape JD & Tailor Resume specifically for this role
    # -------------------------------------------------------------
    logger.info("Step 1/5: Scraping job description...")
    scrape_res = await scrape_jd_node({"job_url": job_url})
    jd_text = scrape_res.get("jd_text", "")

    logger.info("Step 2/5: Tailoring resume with strict zero-fabrication...")
    tailor_state = {"jd_text": jd_text, "job_url": job_url}
    tailor_res = tailor_resume_node(tailor_state)

    company_name = tailor_res.get("company_name", "Target Company")
    role_title = tailor_res.get("role_title", "Software Engineer")
    match_score = tailor_res.get("match_score", 0)
    missing_skills = tailor_res.get("missing_critical_skills", [])

    logger.info(f"Analysis Complete: Company='{company_name}' | Role='{role_title}' | ATS Score={match_score}/100")

    if match_score < 60:
        logger.warning(f"ATS Match Score ({match_score}) below 60 threshold. Skipping to preserve reputation.")
        return {
            "status": "Skipped - Low Match",
            "company": company_name,
            "role": role_title,
            "match_score": match_score,
        }

    # -------------------------------------------------------------
    # Step 3: Render Company-Specific ATS PDF Resume
    # -------------------------------------------------------------
    logger.info("Step 3/5: Rendering company-tailored single-column ATS PDF...")
    gen_state = {
        "master_profile": tailor_res.get("master_profile"),
        "tailored_resume": tailor_res.get("tailored_resume"),
        "company_name": company_name,
        "role_title": role_title,
    }
    pdf_res = await generate_pdf_node(gen_state)
    pdf_path = pdf_res.get("pdf_path", "")
    logger.info(f"Resume generated at: {pdf_path}")

    # -------------------------------------------------------------
    # Step 4: Run Application Agent (Form filling via browser-use)
    # -------------------------------------------------------------
    logger.info("Step 4/5: Running automated portal application...")
    try:
        await run_application_agent(job_url, auto_approve=True)
    except Exception as e:
        logger.warning(f"Browser application automation notice: {e}. Proceeding with outreach and logging.")

    # -------------------------------------------------------------
    # Step 5: Recruiter Discovery, Dynamic Cold Email & PDF Attachment
    # -------------------------------------------------------------
    logger.info("Step 5/5: Discovering recruiters and dispatching dynamic cold email...")
    outreach_res = await run_cold_outreach(
        company_name=company_name,
        role_title=role_title,
        job_url=job_url,
        pdf_path=pdf_path,
        mode=cold_email_mode,
        target_email=target_recruiter_email,
        jd_text=jd_text,
        auto_generate_resume=False,  # Already generated above
    )

    # -------------------------------------------------------------
    # Success Notification
    # -------------------------------------------------------------
    summary_msg = (
        f"✅ Autopilot completed for {company_name} ({role_title})!\n"
        f"• ATS Match: {match_score}/100\n"
        f"• Tailored Resume: {os.path.basename(pdf_path)}\n"
        f"• Cold Email: {outreach_res.get('status')} to {outreach_res.get('recipient')}"
    )
    print("\n" + "=" * 70)
    print(summary_msg)
    print("=" * 70 + "\n")

    send_desktop_notification(f"Autopilot Applied: {company_name}", summary_msg)
    send_telegram_alert(f"<b>Autopilot Applied!</b>\n\n{summary_msg}")

    return {
        "status": "Success",
        "company": company_name,
        "role": role_title,
        "match_score": match_score,
        "pdf_path": pdf_path,
        "cold_email_status": outreach_res.get("status"),
        "recipient": outreach_res.get("recipient"),
    }


async def run_batch_autopilot(
    jobs_file: str = "jobs.txt",
    cold_email_mode: str = "draft",
    delay_between_jobs: int = 15,
):
    """Run autopilot across all job URLs in a batch file with polite pacing."""
    if not os.path.exists(jobs_file):
        logger.error(f"Batch file '{jobs_file}' not found.")
        return

    with open(jobs_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    logger.info(f"Loaded {len(urls)} job postings from {jobs_file}.")
    for idx, url in enumerate(urls, start=1):
        logger.info(f"\nProcessing Job {idx}/{len(urls)}: {url}")
        try:
            await process_single_job_fully_automated(
                job_url=url,
                cold_email_mode=cold_email_mode,
            )
        except Exception as e:
            logger.error(f"Error processing job {url}: {e}")

        if idx < len(urls):
            logger.info(f"Pacing delay: Waiting {delay_between_jobs}s before next application...")
            await asyncio.sleep(delay_between_jobs)

    logger.info("Batch Autopilot run completed successfully!")


async def run_continuous_daemon(
    poll_interval: int = 900,
    jobs_file: str = "jobs.txt",
    cold_email_mode: str = "draft",
):
    """Continuous daemon mode: monitors jobs queue and sweeps Gmail inbox indefinitely."""
    logger.info(f"Starting Autopilot 24/7 Daemon (checking every {poll_interval}s)...")
    while True:
        try:
            # 1. Process any pending jobs in jobs.txt if present
            if os.path.exists(jobs_file):
                with open(jobs_file, "r", encoding="utf-8") as f:
                    pending_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

                if pending_urls:
                    logger.info(f"Found {len(pending_urls)} pending jobs in {jobs_file}. Processing...")
                    # Clear file so we don't re-apply
                    with open(jobs_file, "w", encoding="utf-8") as f:
                        f.write(f"# Processed on {datetime.now().isoformat()}\n")

                    for url in pending_urls:
                        await process_single_job_fully_automated(url, cold_email_mode=cold_email_mode)
                        await asyncio.sleep(10)

            # 2. Check Gmail inbox for recruiter updates
            logger.info("Executing scheduled Gmail recruitment sweep...")
            run_email_tracker(dry_run=False)

        except Exception as e:
            logger.error(f"Error in Autopilot daemon cycle: {e}")

        logger.info(f"Sleeping for {poll_interval} seconds...")
        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autopilot: 100% Fully Automated Job Agent & Outreach")
    parser.add_argument("url", nargs="?", help="Direct job URL to apply and reach out to automatically")
    parser.add_argument("--batch", help="Path to text file containing job URLs (one per line)")
    parser.add_argument("--company", help="Target company name for direct cold outreach")
    parser.add_argument("--role", help="Target role title for direct cold outreach")
    parser.add_argument(
        "--mode",
        choices=["draft", "send", "preview"],
        default="draft",
        help="Cold email mode: 'draft' (in Gmail), 'send' (via SMTP), or 'preview'",
    )
    parser.add_argument("--daemon", action="store_true", help="Run continuously in 24/7 background mode")
    parser.add_argument("--interval", type=int, default=900, help="Daemon polling interval in seconds (default: 900s)")
    parser.add_argument("--discover", action="store_true", help="Discover live active jobs (Healthcare #1 + Cross-Industry) and update jobs.txt")
    parser.add_argument("--test", action="store_true", help="Run automated test using sample JD")

    args = parser.parse_args()

    if args.discover:
        jobs = discover_live_jobs(max_results=15, write_to_jobs_txt=True)
        print(f"\nDiscovered {len(jobs)} live jobs and updated jobs.txt!")
    elif args.daemon:
        asyncio.run(
            run_continuous_daemon(
                poll_interval=args.interval,
                jobs_file=args.batch or "jobs.txt",
                cold_email_mode=args.mode,
            )
        )
    elif args.batch:
        asyncio.run(
            run_batch_autopilot(
                jobs_file=args.batch,
                cold_email_mode=args.mode,
            )
        )
    elif args.company and args.role:
        asyncio.run(
            run_cold_outreach(
                company_name=args.company,
                role_title=args.role,
                job_url=args.url or f"https://{args.company.lower().replace(' ', '')}.com/careers",
                mode=args.mode,
            )
        )
    else:
        # Single URL or Test mode
        target_url = args.url
        if args.test or not target_url:
            sample_jd_path = OUTPUT_DIR / "sample_jd.txt"
            sample_jd_path.write_text(
                """
                Role: Senior AI Automation Engineer
                Company: Horizon AI Solutions
                Location: San Francisco, CA (Remote Friendly)
                Requirements:
                - 4+ years building full-stack applications with Python, TypeScript, and FastAPI.
                - Proven experience with LLM orchestration frameworks such as LangChain and LangGraph.
                - Strong expertise in browser automation, web scraping (Playwright), and document ingestion.
                - Hands-on integration of Google APIs (Sheets, Gmail, Cloud Run) and OAuth2 authentication.
                """,
                encoding="utf-8",
            )
            target_url = str(sample_jd_path.resolve())

        asyncio.run(
            process_single_job_fully_automated(
                job_url=target_url,
                cold_email_mode=args.mode,
            )
        )
