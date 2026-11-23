"""Google Sheets Application Tracking Integration.

Manages OAuth2 token lifecycle, initializes header schema, records new
job applications, updates statuses from email updates, and queries
tracked target companies. Includes offline CSV fallback mode for local testing.
"""

from __future__ import annotations

import csv
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import uuid

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sheets_manager")

# OAuth Scopes for both Google Sheets (R/W) and Gmail (Read-only)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.readonly",
]

SHEET_HEADERS = [
    "Application ID",
    "Date Applied",
    "Company",
    "Role",
    "Job URL",
    "Match Score",
    "Missing Skills",
    "Tailored PDF Path",
    "Status",
    "Last Email Update",
    "Last Updated Timestamp",
    "Gmail Thread Link",
]

LOCAL_FALLBACK_FILE = "applications_tracker.csv"


def get_google_credentials(
    credentials_file: str = "credentials.json",
    token_file: str = "token.json",
) -> Credentials | None:
    """Load or authenticate Google OAuth2 user credentials."""
    creds: Credentials | None = None

    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception as e:
            logger.warning(f"Error loading {token_file}: {e}. Refreshing authorization flow.")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired Google OAuth2 credentials...")
                creds.refresh(Request())
                with open(token_file, "w") as token:
                    token.write(creds.to_json())
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}. Initiating interactive sign-in.")
                creds = None

        if not creds:
            if not os.path.exists(credentials_file):
                logger.warning(
                    f"'{credentials_file}' not found. Google Sheets / Gmail API will be offline. "
                    "Falling back to local CSV storage."
                )
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_file, "w") as token:
                    token.write(creds.to_json())
                logger.info(f"OAuth credentials successfully saved to {token_file}.")
            except Exception as e:
                logger.error(f"Failed to complete OAuth flow: {e}")
                return None

    return creds


class SheetsManager:
    """Manages reading and writing application records to Google Sheets or local CSV."""

    def __init__(self, sheet_id: str | None = None):
        self.sheet_id = sheet_id or os.getenv("GOOGLE_SHEET_ID")
        self.creds = get_google_credentials()
        self.client: gspread.Client | None = None
        self.sheet = None
        self.is_connected = False

        if self.creds and self.sheet_id and self.sheet_id != "your_google_sheet_id_here":
            try:
                self.client = gspread.authorize(self.creds)
                self.sheet = self._init_sheet()
                self.is_connected = True
                logger.info("Successfully connected to Google Sheet.")
            except Exception as e:
                logger.warning(f"Failed to connect to Google Sheet ({e}). Falling back to local CSV.")
                self.is_connected = False
        else:
            logger.info("Google Sheet credentials/ID not fully configured. Using local CSV fallback.")
            self._init_local_csv()

    def _init_sheet(self):
        """Open or initialize Google Sheet with standard header columns."""
        spreadsheet = self.client.open_by_key(self.sheet_id)
        worksheet = spreadsheet.sheet1
        existing_values = worksheet.get_all_values()
        if not existing_values or len(existing_values) == 0 or existing_values[0] != SHEET_HEADERS:
            logger.info("Initializing sheet headers...")
            worksheet.clear()
            worksheet.append_row(SHEET_HEADERS)
        return worksheet

    def _init_local_csv(self):
        """Initialize local CSV fallback tracker if not present."""
        if not os.path.exists(LOCAL_FALLBACK_FILE):
            with open(LOCAL_FALLBACK_FILE, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(SHEET_HEADERS)
            logger.info(f"Initialized local tracker: {LOCAL_FALLBACK_FILE}")

    def log_new_application(
        self,
        company: str,
        role: str,
        job_url: str,
        match_score: int | float,
        missing_skills: list[str] | str,
        pdf_path: str,
        status: str = "Applied - Awaiting Response",
    ) -> str:
        """Append a new job application record to the sheet or fallback CSV."""
        app_id = f"APP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        date_applied = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        missing_skills_str = (
            ", ".join(missing_skills) if isinstance(missing_skills, list) else str(missing_skills)
        )

        row_data = [
            app_id,
            date_applied,
            company,
            role,
            job_url,
            str(match_score),
            missing_skills_str,
            str(pdf_path),
            status,
            "",  # Last Email Update
            date_applied,  # Last Updated Timestamp
            "",  # Gmail Thread Link
        ]

        if self.is_connected and self.sheet:
            try:
                self.sheet.append_row(row_data)
                logger.info(f"Logged application to Google Sheet: {app_id} | {company} - {role}")
                return app_id
            except Exception as e:
                logger.error(f"Error appending row to Google Sheet: {e}. Writing to local CSV fallback.")

        # Local CSV Fallback
        self._init_local_csv()
        with open(LOCAL_FALLBACK_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row_data)
        logger.info(f"Logged application to local CSV: {app_id} | {company} - {role}")
        return app_id

    def update_application_status(
        self,
        company_or_role: str,
        new_status: str,
        email_summary: str,
        thread_link: str | None = None,
    ) -> bool:
        """Find matching application row and update status and notes."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target = company_or_role.strip().lower()

        if self.is_connected and self.sheet:
            try:
                records = self.sheet.get_all_records()
                for idx, record in enumerate(records, start=2):  # row 1 is header
                    company = str(record.get("Company", "")).lower()
                    role = str(record.get("Role", "")).lower()

                    if target in company or company in target or target in role:
                        # Column indices in 1-based indexing:
                        # Status: col 9
                        # Last Email Update: col 10
                        # Last Updated Timestamp: col 11
                        # Gmail Thread Link: col 12
                        self.sheet.update_cell(idx, 9, new_status)
                        self.sheet.update_cell(idx, 10, email_summary)
                        self.sheet.update_cell(idx, 11, timestamp)
                        if thread_link:
                            self.sheet.update_cell(idx, 12, thread_link)

                        logger.info(f"Google Sheet updated row {idx} for '{company}': {new_status}")
                        return True
            except Exception as e:
                logger.error(f"Failed to update Google Sheet: {e}. Attempting local CSV update.")

        # Fallback to local CSV update
        if os.path.exists(LOCAL_FALLBACK_FILE):
            rows = []
            updated = False
            with open(LOCAL_FALLBACK_FILE, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if rows:
                header = rows[0]
                company_idx = header.index("Company") if "Company" in header else 2
                role_idx = header.index("Role") if "Role" in header else 3
                status_idx = header.index("Status") if "Status" in header else 8
                summary_idx = header.index("Last Email Update") if "Last Email Update" in header else 9
                timestamp_idx = header.index("Last Updated Timestamp") if "Last Updated Timestamp" in header else 10
                thread_idx = header.index("Gmail Thread Link") if "Gmail Thread Link" in header else 11

                for row in rows[1:]:
                    if len(row) > company_idx:
                        company = row[company_idx].lower()
                        role = row[role_idx].lower() if len(row) > role_idx else ""
                        if target in company or company in target or target in role:
                            while len(row) < len(SHEET_HEADERS):
                                row.append("")
                            row[status_idx] = new_status
                            row[summary_idx] = email_summary
                            row[timestamp_idx] = timestamp
                            if thread_link:
                                row[thread_idx] = thread_link
                            updated = True
                            logger.info(f"Local CSV updated record for '{row[company_idx]}': {new_status}")
                            break

                if updated:
                    with open(LOCAL_FALLBACK_FILE, mode="w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerows(rows)
                    return True

        logger.warning(f"No matching active application found for '{company_or_role}'.")
        return False

    def get_tracked_companies(self) -> list[dict[str, str]]:
        """Return list of active companies and roles currently being tracked."""
        tracked: list[dict[str, str]] = []

        if self.is_connected and self.sheet:
            try:
                records = self.sheet.get_all_records()
                for r in records:
                    company = str(r.get("Company", "")).strip()
                    if company:
                        tracked.append({
                            "application_id": str(r.get("Application ID", "")),
                            "company": company,
                            "role": str(r.get("Role", "")).strip(),
                            "status": str(r.get("Status", "")).strip(),
                            "job_url": str(r.get("Job URL", "")).strip(),
                        })
                return tracked
            except Exception as e:
                logger.error(f"Error reading companies from Google Sheet: {e}. Falling back to CSV.")

        # Local CSV Fallback
        if os.path.exists(LOCAL_FALLBACK_FILE):
            with open(LOCAL_FALLBACK_FILE, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    company = r.get("Company", "").strip()
                    if company:
                        tracked.append({
                            "application_id": r.get("Application ID", ""),
                            "company": company,
                            "role": r.get("Role", "").strip(),
                            "status": r.get("Status", "").strip(),
                            "job_url": r.get("Job URL", "").strip(),
                        })

        return tracked


# Convenience singleton accessor
_default_manager: SheetsManager | None = None


def get_sheets_manager() -> SheetsManager:
    """Return singleton instance of SheetsManager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = SheetsManager()
    return _default_manager
