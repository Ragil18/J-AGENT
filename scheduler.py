"""Cloud Runner, Background Scheduler & Webhook API for Headless Deployment.

Designed for zero-cost cloud platforms (Render, Railway, Fly.io, GCP Cloud Run, Docker).
Exposes HTTP health-checks and webhook triggers, while running an asynchronous
background polling loop for Gmail recruitment status updates and automated cold outreach.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
import uvicorn

from apply_agent import run_application_agent
from autopilot import process_single_job_fully_automated
from cold_email_agent import run_cold_outreach
from email_tracker import run_email_tracker
from sheets_manager import get_sheets_manager

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cloud_scheduler")

POLL_INTERVAL_SECONDS = int(os.getenv("EMAIL_POLL_INTERVAL", "900"))  # Default 15 mins
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")

# Background worker task handle
_background_task: Optional[asyncio.Task] = None


async def background_inbox_poller():
    """Continuous background loop that scans Gmail for recruitment updates."""
    logger.info(f"Background email poller started. Polling every {POLL_INTERVAL_SECONDS} seconds.")
    while True:
        try:
            logger.info("Executing scheduled Gmail recruitment scan...")
            run_email_tracker(dry_run=False)
        except Exception as e:
            logger.error(f"Error in background email scan: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background workers on server startup and clean up on shutdown."""
    global _background_task
    logger.info("Initializing cloud agent background services...")
    _background_task = asyncio.create_task(background_inbox_poller())
    yield
    if _background_task:
        _background_task.cancel()
        logger.info("Background services stopped.")


app = FastAPI(
    title="Autonomous Job Application & Recruitment Agent",
    description="Cloud Worker and Webhook API for automated job applications, cold email outreach, and status tracking.",
    version="2.0.0",
    lifespan=lifespan,
)


# ====================================================================
# Request Schemas
# ====================================================================

class ApplyRequest(BaseModel):
    job_url: str
    send_cold_email: bool = True
    cold_email_mode: str = "draft"  # "draft", "send", or "preview"
    target_recruiter_email: Optional[str] = None


class ColdEmailRequest(BaseModel):
    company_name: str
    role_title: str
    job_url: Optional[str] = None
    target_email: Optional[str] = None
    pdf_path: Optional[str] = None
    mode: str = "draft"  # "draft", "send", "preview"


# ====================================================================
# Endpoints
# ====================================================================

@app.get("/health")
def health_check():
    """Cloud platform health probe."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "poller_active": _background_task is not None and not _background_task.done(),
    }


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Live web dashboard of active job applications and system status."""
    sheets_mgr = get_sheets_manager()
    tracked = sheets_mgr.get_tracked_companies()

    rows_html = "".join([
        f"""<tr>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;"><b>{t.get('company')}</b></td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{t.get('role')}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;"><span style="background-color: #dbeafe; color: #1e40af; padding: 4px 8px; border-radius: 4px; font-weight: 600;">{t.get('status')}</span></td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;"><a href="{t.get('job_url')}" target="_blank" style="color: #2563eb;">View Posting</a></td>
        </tr>"""
        for t in tracked
    ]) if tracked else "<tr><td colspan='4' style='padding: 20px; text-align: center; color: #64748b;'>No applications recorded yet.</td></tr>"

    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <title>Job Application Agent Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 24px; }}
            .card {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); padding: 24px; }}
            h1 {{ font-size: 24px; margin-bottom: 8px; color: #1e3a8a; }}
            .status-badge {{ display: inline-block; background: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; margin-top: 12px; }}
            th {{ background: #f1f5f9; padding: 10px; color: #475569; font-weight: 600; }}
            .actions {{ margin-top: 24px; display: flex; gap: 12px; }}
            button {{ background: #2563eb; color: white; border: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; cursor: pointer; }}
            button:hover {{ background: #1d4ed8; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Autonomous Job Application & Recruitment Agent</h1>
            <div class="status-badge">Cloud Service Active &bull; Polling Every {POLL_INTERVAL_SECONDS // 60}m</div>
            
            <h3>Tracked Applications ({len(tracked)})</h3>
            <table>
                <thead>
                    <tr>
                        <th>Company</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Job Link</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>

            <div class="actions">
                <form action="/trigger-scan" method="post" style="display:inline;">
                    <button type="submit">Scan Inbox Now</button>
                </form>
            </div>
        </div>
    </body>
    </html>"""
    return html


@app.post("/trigger-scan")
def trigger_scan(background_tasks: BackgroundTasks):
    """Manual webhook trigger to scan Gmail immediately."""
    background_tasks.add_task(run_email_tracker, False)
    return {"status": "Gmail scan triggered in background"}


@app.post("/apply")
async def trigger_apply(payload: ApplyRequest, background_tasks: BackgroundTasks):
    """Trigger fully automated end-to-end application and cold email outreach."""
    logger.info(f"Received API request to apply for: {payload.job_url}")

    async def execute_apply_and_cold_email():
        try:
            await process_single_job_fully_automated(
                job_url=payload.job_url,
                cold_email_mode=payload.cold_email_mode if payload.send_cold_email else "preview",
                target_recruiter_email=payload.target_recruiter_email,
            )
        except Exception as e:
            logger.error(f"Error executing cloud autopilot workflow: {e}")

    background_tasks.add_task(execute_apply_and_cold_email)
    return {
        "status": "Autopilot workflow initiated in background",
        "job_url": payload.job_url,
        "cold_email_enabled": payload.send_cold_email,
    }


@app.post("/cold-email")
async def trigger_cold_email(payload: ColdEmailRequest, background_tasks: BackgroundTasks):
    """Dispatch or draft personalized cold email with dynamically generated company-tailored resume."""
    async def execute_outreach():
        try:
            await run_cold_outreach(
                company_name=payload.company_name,
                role_title=payload.role_title,
                job_url=payload.job_url or f"https://{payload.company_name.lower().replace(' ', '')}.com/careers",
                pdf_path=payload.pdf_path,
                mode=payload.mode,
                target_email=payload.target_email,
            )
        except Exception as e:
            logger.error(f"Error executing cold email outreach: {e}")

    background_tasks.add_task(execute_outreach)
    return {
        "status": "Cold email outreach with dynamic resume generation triggered in background",
        "company": payload.company_name,
        "role": payload.role_title,
        "mode": payload.mode,
    }
    return {
        "status": "Cold email outreach triggered in background",
        "company": payload.company_name,
        "role": payload.role_title,
        "mode": payload.mode,
    }


if __name__ == "__main__":
    logger.info(f"Starting Cloud Runner on {HOST}:{PORT}")
    uvicorn.run("scheduler:app", host=HOST, port=PORT, reload=False)
