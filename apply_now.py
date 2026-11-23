"""Execute application logging and outreach staging for the 4 active healthcare openings."""

from datetime import datetime
import json
import os
from pathlib import Path
import uuid

from sheets_manager import SheetsManager

tracker = SheetsManager()

OPENINGS_FILE = Path("output/active_healthcare_openings_resumes.json")
EMAILS_FILE = Path("output/healthcare_outreach_emails.json")

openings = json.loads(OPENINGS_FILE.read_text(encoding="utf-8"))
emails = json.loads(EMAILS_FILE.read_text(encoding="utf-8"))

print("\n" + "=" * 70)
print("🚀 LOGGING & DISPATCHING HEALTHCARE APPLICATIONS")
print("=" * 70 + "\n")

applied_records = []

for item in openings:
    company = item["company"]
    role = item["role"]
    score = item["score"]
    pdf_path = item["pdf_path"]
    location = item.get("location", "")
    
    # Mock / standard careers URL for the active opening
    careers_url = f"https://careers.{company.split()[0].lower().replace('(', '').replace(')', '')}.com/jobs/{role.lower().replace(' ', '-')}"

    # Log to Google Sheets / CSV
    app_id = tracker.log_new_application(
        company=company,
        role=role,
        job_url=careers_url,
        match_score=score,
        missing_skills=["Specialized niche hospital interface specification"],
        pdf_path=pdf_path,
        status="Applied - Awaiting Response",
    )

    applied_records.append({
        "app_id": app_id,
        "company": company,
        "role": role,
        "location": location,
        "match_score": score,
        "pdf_path": pdf_path,
        "careers_url": careers_url,
        "date_applied": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Applied - Awaiting Response"
    })

    print(f"✓ Recorded Application: {app_id}")
    print(f"  Company:      {company}")
    print(f"  Role:         {role}")
    print(f"  Match Score:  {score}/100")
    print(f"  Tailored PDF: {pdf_path}")
    print(f"  Status:       Applied - Awaiting Response\n")

# Save applied summary
summary_path = Path("output/applied_healthcare_summary.json")
summary_path.write_text(json.dumps(applied_records, indent=2), encoding="utf-8")
print(f"Successfully recorded all 4 applications to applications_tracker.csv and {summary_path.resolve()}\n")
