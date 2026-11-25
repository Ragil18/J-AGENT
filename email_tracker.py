"""Gmail Application Status Watcher & Notification Agent.

Continuously scans Gmail inbox for updates from applied companies and standard ATS
platforms (Greenhouse, Lever, Workday, Ashby, SmartRecruiters, LinkedIn).
Classifies updates using Gemini structured outputs, updates Google Sheets, and
dispatches desktop notifications and Telegram alerts.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta
import email as email_lib
from email.header import decode_header
import imaplib
import json
import logging
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from googleapiclient.discovery import build
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
import requests

from sheets_manager import get_google_credentials, get_sheets_manager

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("email_tracker")

FAST_MODEL = os.getenv("FAST_MODEL", "gemini-2.5-flash")

ATS_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "workday.com",
    "ashbyhq.com",
    "smartrecruiters.com",
    "linkedin.com",
    "hire.lever.co",
    "myworkday.com",
]


# ====================================================================
# Pydantic Schema for Structured Email Classification
# ====================================================================

class EmailClassification(BaseModel):
    is_job_update: bool = Field(
        description="True if email is related to a job application, recruitment process, interview, or rejection."
    )
    matched_company: str = Field(
        description="Name of the company sending or referenced in this email update."
    )
    status: Literal[
        "Application Viewed",
        "Assessment / Task",
        "Interview Scheduled",
        "Offer",
        "Rejected",
        "General Update",
        "Unrelated",
    ] = Field(
        description="Standardized recruitment stage status."
    )
    action_required: bool = Field(
        description="True if the candidate must reply, pick an interview slot, or submit a take-home task."
    )
    summary: str = Field(
        description="1-sentence executive summary of the update, including any explicit deadlines or next steps."
    )


# ====================================================================
# Notifications (Desktop + Telegram)
# ====================================================================

def send_desktop_notification(title: str, message: str):
    """Deliver a native desktop notification with robust multi-platform fallbacks."""
    logger.info(f"Desktop Notification: {title} | {message}")
    
    # Windows native notification via PowerShell (toast/balloon)
    if os.name == "nt":
        try:
            escaped_title = title.replace('"', '`"').replace("'", "''")
            escaped_msg = message[:200].replace('"', '`"').replace("'", "''")
            ps_script = (
                f"[void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
                f"$objNotify = New-Object System.Windows.Forms.NotifyIcon; "
                f"$objNotify.Icon = [System.Drawing.SystemIcons]::Information; "
                f"$objNotify.BalloonTipTitle = '{escaped_title}'; "
                f"$objNotify.BalloonTipText = '{escaped_msg}'; "
                f"$objNotify.Visible = $True; "
                f"$objNotify.ShowBalloonTip(5000); "
                f"Start-Sleep -Seconds 1; "
                f"$objNotify.Dispose()"
            )
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception as e:
            logger.debug(f"PowerShell notification notice: {e}")

    # Fallback to plyer notification
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message[:250],
            app_name="Job Agent",
            timeout=5,
        )
    except Exception as e:
        logger.debug(f"Plyer notification notice: {e}")


def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram bot if credentials are configured in .env."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=8)
        if resp.status_code == 200:
            logger.info("Telegram notification delivered successfully.")
            return True
        else:
            logger.warning(f"Telegram API responded with {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.warning(f"Failed to send Telegram alert: {e}")
    return False


# ====================================================================
# Gmail API Fetcher
# ====================================================================

class GmailClient:
    """Handles interaction with Gmail via OAuth API OR Zero-OAuth Gmail IMAP (App Password)."""

    def __init__(self):
        self.creds = get_google_credentials()
        self.service = None
        self.imap_user = os.getenv("SMTP_USER") or os.getenv("GMAIL_ADDRESS")
        self.imap_pass = os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_APP_PASSWORD")
        self.imap_host = os.getenv("IMAP_HOST", "imap.gmail.com")
        self.mode = "offline"

        if self.creds:
            try:
                self.service = build("gmail", "v1", credentials=self.creds)
                self.mode = "oauth"
                logger.info("Connected to Gmail API (OAuth).")
            except Exception as e:
                logger.warning(f"Failed to build Gmail OAuth service: {e}")

        if self.mode == "offline" and self.imap_user and self.imap_pass:
            self.mode = "imap"
            logger.info(f"Using Zero-OAuth Gmail IMAP mode for {self.imap_user}.")

    def is_available(self) -> bool:
        return self.mode in ("oauth", "imap")

    @staticmethod
    def _decode_mime_header(value: str) -> str:
        if not value:
            return ""
        parts = decode_header(value)
        decoded = []
        for part, enc in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                decoded.append(str(part))
        return "".join(decoded)

    def _search_via_imap(self, tracked_companies: List[str], days_back: int = 7) -> List[Dict[str, Any]]:
        """Upgrade #6: Zero-OAuth Gmail inbox scan using standard IMAP + App Password."""
        email_details: List[Dict[str, Any]] = []
        try:
            mail = imaplib.IMAP4_SSL(self.imap_host, 993)
            mail.login(self.imap_user, self.imap_pass)
            mail.select("INBOX")

            since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            status, data = mail.search(None, f'(SINCE "{since_date}")')
            if status != "OK" or not data or not data[0]:
                mail.logout()
                return []

            msg_nums = data[0].split()[-40:]  # Inspect latest 40 messages from past 7 days
            keywords = [c.lower() for c in tracked_companies if c] + [d.lower() for d in ATS_DOMAINS]

            for num in reversed(msg_nums):
                res_status, msg_data = mail.fetch(num, "(RFC822.HEADER BODY.PEEK[TEXT]<0.1200>)")
                if res_status != "OK" or not msg_data:
                    continue

                raw_header = b""
                raw_snippet = b""
                for part in msg_data:
                    if isinstance(part, tuple):
                        meta = part[0].decode(errors="ignore").upper()
                        if "HEADER" in meta:
                            raw_header = part[1]
                        else:
                            raw_snippet = part[1]

                parsed = email_lib.message_from_bytes(raw_header)
                subject = self._decode_mime_header(parsed.get("Subject", "(No Subject)"))
                sender = self._decode_mime_header(parsed.get("From", "Unknown"))
                date_hdr = parsed.get("Date", "")
                snippet = raw_snippet.decode("utf-8", errors="ignore").replace("\r", " ").replace("\n", " ").strip()[:500]

                combined = f"{subject} {sender} {snippet}".lower()
                if keywords and not any(k in combined for k in keywords):
                    continue

                msg_id = num.decode()
                email_details.append({
                    "id": msg_id,
                    "thread_id": msg_id,
                    "thread_link": "https://mail.google.com/mail/u/0/#inbox",
                    "subject": subject,
                    "from": sender,
                    "date": date_hdr,
                    "snippet": snippet,
                })

            mail.logout()
            logger.info(f"IMAP scan retrieved {len(email_details)} matching recruitment email(s).")
        except Exception as e:
            logger.error(f"Gmail IMAP scan failed: {e}")
        return email_details

    def search_recent_recruiter_emails(self, tracked_companies: List[str]) -> List[Dict[str, Any]]:
        """Query Gmail for recent emails matching tracked companies or ATS domains."""
        if self.mode == "imap":
            return self._search_via_imap(tracked_companies)

        if not self.service:
            logger.warning("Gmail service is unavailable. Set SMTP_USER & SMTP_PASSWORD in .env for IMAP, or add credentials.json.")
            return []

        # Build search query: newer than 7 days, matching company names or standard ATS senders
        company_queries = [f'"{comp}"' for comp in tracked_companies if comp]
        ats_queries = [f"from:{domain}" for domain in ATS_DOMAINS]

        all_clauses = ats_queries + company_queries
        if not all_clauses:
            return []

        query = f"newer_than:7d ({' OR '.join(all_clauses)})"
        logger.info(f"Executing Gmail query: {query[:120]}...")

        try:
            results = self.service.users().messages().list(userId="me", q=query, maxResults=25).execute()
            messages = results.get("messages", [])
            logger.info(f"Retrieved {len(messages)} matching candidate emails.")

            email_details = []
            for msg in messages:
                msg_id = msg["id"]
                thread_id = msg["threadId"]
                full_msg = self.service.users().messages().get(
                    userId="me", id=msg_id, format="metadata",
                    metadataHeaders=["Subject", "From", "Date"]
                ).execute()

                headers = {h["name"]: h["value"] for h in full_msg.get("payload", {}).get("headers", [])}
                snippet = full_msg.get("snippet", "")

                email_details.append({
                    "id": msg_id,
                    "thread_id": thread_id,
                    "thread_link": f"https://mail.google.com/mail/u/0/#inbox/{thread_id}",
                    "subject": headers.get("Subject", "(No Subject)"),
                    "from": headers.get("From", "Unknown"),
                    "date": headers.get("Date", ""),
                    "snippet": snippet,
                })

            return email_details
        except Exception as e:
            logger.error(f"Error querying Gmail: {e}")
            return []


# ====================================================================
# Classification Logic
# ====================================================================

def classify_email(email_item: Dict[str, Any], tracked_companies: List[str]) -> Optional[EmailClassification]:
    """Classify email content into structured status using Gemini."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set. Using rule-based fallback classification.")
        return rule_based_fallback_classification(email_item, tracked_companies)

    system_prompt = (
        "You are an AI Recruitment Operations Specialist.\n"
        "Analyze the provided email subject, sender, and snippet to identify if it is a job application update.\n"
        "Classify into one of: 'Application Viewed', 'Assessment / Task', 'Interview Scheduled', 'Offer', 'Rejected', 'General Update', or 'Unrelated'.\n"
        "Set action_required = True if the candidate needs to schedule an interview, reply to a question, or submit a code test.\n"
        "Provide a crisp 1-sentence summary."
    )

    user_prompt = (
        f"Tracked Companies: {json.dumps(tracked_companies)}\n\n"
        f"EMAIL DETAILS:\n"
        f"- From: {email_item.get('from')}\n"
        f"- Subject: {email_item.get('subject')}\n"
        f"- Snippet: {email_item.get('snippet')}\n"
    )

    models_to_try = [FAST_MODEL, "gemini-2.5-flash", "gemini-1.5-flash"]
    for model_name in models_to_try:
        try:
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=0.0,
            )
            structured_llm = llm.with_structured_output(EmailClassification, method="json_schema")
            result = structured_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
            if isinstance(result, EmailClassification):
                return result
        except Exception as e:
            logger.warning(f"Classification with {model_name} failed: {e}")

    return rule_based_fallback_classification(email_item, tracked_companies)


def rule_based_fallback_classification(
    email_item: Dict[str, Any], tracked_companies: List[str]
) -> EmailClassification:
    """Heuristic fallback classification when offline or LLM unavailable."""
    subject = email_item.get("subject", "").lower()
    snippet = email_item.get("snippet", "").lower()
    sender = email_item.get("from", "").lower()
    combined = f"{subject} {snippet} {sender}"

    # Match company
    matched = "Unknown"
    for comp in tracked_companies:
        if comp.lower() in combined:
            matched = comp
            break

    is_update = False
    status = "General Update"
    action_required = False

    if any(k in combined for k in ["interview", "invitation", "chat with", "schedule time", "meet the team"]):
        is_update = True
        status = "Interview Scheduled"
        action_required = True
        summary = f"Interview invitation from {matched}. Candidate action required to schedule slot."
    elif any(k in combined for k in ["assessment", "coding challenge", "take-home", "hackerrank", "codesignal"]):
        is_update = True
        status = "Assessment / Task"
        action_required = True
        summary = f"Technical assessment assigned for {matched}. Completion required."
    elif any(k in combined for k in ["offer", "pleased to offer", "welcome to the team"]):
        is_update = True
        status = "Offer"
        action_required = True
        summary = f"Formal employment offer received from {matched}!"
    elif any(k in combined for k in ["unfortunately", "not moving forward", "other candidates", "regret to inform"]):
        is_update = True
        status = "Rejected"
        action_required = False
        summary = f"Application rejected by {matched}."
    elif any(k in combined for k in ["application received", "thank you for applying", "reviewing your application"]):
        is_update = True
        status = "Application Viewed"
        action_required = False
        summary = f"Application officially received and under review by {matched}."
    else:
        summary = f"General communication received from {matched}."

    return EmailClassification(
        is_job_update=is_update,
        matched_company=matched,
        status=status,
        action_required=action_required,
        summary=summary,
    )


# ====================================================================
# Execution Loop
# ====================================================================

def run_email_tracker(dry_run: bool = False):
    """Execute a single sweep of the Gmail inbox and sync status updates."""
    logger.info("=== Starting Gmail Status Tracking Scan ===")
    sheets_mgr = get_sheets_manager()
    tracked = sheets_mgr.get_tracked_companies()
    tracked_companies = list({t["company"] for t in tracked if t.get("company")})

    logger.info(f"Active companies being tracked ({len(tracked_companies)}): {tracked_companies}")

    gmail = GmailClient()
    if not gmail.is_available():
        logger.warning(
            "Gmail client is offline (no valid credentials.json found). "
            "To test notifications and updates, use --mock-test flag."
        )
        return

    emails = gmail.search_recent_recruiter_emails(tracked_companies)
    if not emails:
        logger.info("No new recruitment emails found in this cycle.")
        return

    for email_item in emails:
        classification = classify_email(email_item, tracked_companies)
        if not classification or not classification.is_job_update or classification.status == "Unrelated":
            continue

        company = classification.matched_company
        status = classification.status
        summary = classification.summary
        thread_link = email_item.get("thread_link", "")

        logger.info(f"Detected Update: Company='{company}' | Status='{status}' | ActionRequired={classification.action_required}")

        if not dry_run:
            # Update Google Sheet
            updated = sheets_mgr.update_application_status(
                company_or_role=company,
                new_status=status,
                email_summary=summary,
                thread_link=thread_link,
            )

        # Build notification messages
        action_tag = " [ACTION REQUIRED]" if classification.action_required else ""
        notif_title = f"{status}{action_tag}: {company}"
        notif_body = f"{summary}\n\nDate: {email_item.get('date', '')}\nGmail: {thread_link}"

        # Dispatch Desktop Notification
        send_desktop_notification(notif_title, notif_body)

        # Dispatch Telegram Alert
        telegram_msg = (
            f"<b>{notif_title}</b>\n\n"
            f"{summary}\n\n"
            f"<a href='{thread_link}'>Open in Gmail</a>"
        )
        send_telegram_alert(telegram_msg)


def run_mock_test():
    """Simulate receiving recruiter emails to test classification, sheet update, and notifications."""
    logger.info("Running simulated recruiter email updates test...")
    sheets_mgr = get_sheets_manager()

    mock_emails = [
        {
            "from": "recruiting@horizon-ai.example.com",
            "subject": "Invitation to Technical Interview with Horizon AI Solutions",
            "snippet": "Hi Alex, our team was impressed with your background in AI automation and LangGraph. We would like to schedule a 45-minute technical discussion this week.",
            "date": datetime.now().strftime("%a, %d %b %Y %H:%M:%S"),
            "thread_link": "https://mail.google.com/mail/u/0/#inbox/mock_thread_12345",
        },
        {
            "from": "talent@nexaflow.example.com",
            "subject": "Update on your Senior AI Engineer Application",
            "snippet": "Thank you for taking the time to speak with our hiring team. Unfortunately, we have decided to move forward with another candidate whose experience more closely matches our immediate needs.",
            "date": datetime.now().strftime("%a, %d %b %Y %H:%M:%S"),
            "thread_link": "https://mail.google.com/mail/u/0/#inbox/mock_thread_67890",
        },
    ]

    for item in mock_emails:
        logger.info(f"\nProcessing mock email from: {item['from']}")
        classification = classify_email(item, ["Horizon AI Solutions", "Horizon AI", "NexaFlow Systems"])
        logger.info(f"Classified: {classification.model_dump_json(indent=2)}")

        sheets_mgr.update_application_status(
            company_or_role=classification.matched_company,
            new_status=classification.status,
            email_summary=classification.summary,
            thread_link=item["thread_link"],
        )

        send_desktop_notification(
            f"Job Alert: {classification.matched_company} - {classification.status}",
            classification.summary,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gmail Recruitment Status Watcher & Notifier")
    parser.add_argument("--once", action="store_true", help="Run a single email scan and exit")
    parser.add_argument("--watch", action="store_true", help="Run continuously in a background monitoring loop")
    parser.add_argument("--interval", type=int, default=900, help="Polling interval in seconds for --watch (default: 900s / 15m)")
    parser.add_argument("--dry-run", action="store_true", help="Classify emails without updating Google Sheets")
    parser.add_argument("--mock-test", action="store_true", help="Simulate email receipt to verify notifications and updates")

    args = parser.parse_args()

    if args.mock_test:
        run_mock_test()
    elif args.watch:
        logger.info(f"Starting continuous email watch loop (polling every {args.interval} seconds)...")
        try:
            while True:
                run_email_tracker(dry_run=args.dry_run)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Watch loop terminated by user.")
    else:
        # Default to single run
        run_email_tracker(dry_run=args.dry_run)
