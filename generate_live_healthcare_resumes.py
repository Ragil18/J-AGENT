"""Generate specifically tailored ATS resumes for active Healthcare Openings in India/Chennai.

Target Openings:
1. Optum (UnitedHealth Group) - Healthcare Data Analyst & BI Developer
2. athenahealth (Chennai) - Data Operations Analyst (Platform & EHR)
3. CitiusTech - Healthcare Data Systems Analyst
4. Philips Healthcare - Healthcare Quality & Clinical Data Analyst
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from apply_agent import generate_pdf_node, tailor_resume_node

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("live_healthcare_resumes")

ACTIVE_HEALTHCARE_JOBS = [
    {
        "company": "Optum (UnitedHealth Group)",
        "role": "Healthcare Data Analyst & BI Developer",
        "location": "Chennai / Bangalore, India",
        "jd": (
            "Seeking a Healthcare Data Analyst & BI Developer. Key responsibilities: Extract, clean, and validate "
            "complex clinical, patient-flow, and claims datasets from MS SQL databases. Design and build enterprise "
            "dashboards and KPI reports using Power BI (DAX, Power Query). Automate recurring reporting pipelines, "
            "support diagnostic laboratory and clinical operational metrics, and maintain strict data integrity and "
            "HIPAA compliance. Experience with SQL query optimization, Azure/Databricks, and Python is highly valued."
        ),
    },
    {
        "company": "athenahealth",
        "role": "Data Operations Analyst (Platform & EHR)",
        "location": "Chennai, Tamil Nadu, India",
        "jd": (
            "Join our Chennai Data Operations team within Product Optimization. You will support platform operations "
            "products and EHR integrations involving HL7 connections, RESTful APIs, and Data View. Troubleshoot "
            "integration and clinical data flow issues, validate EHR backend feeds, maintain standard operating procedures (SOPs), "
            "and track customer resolution workflows. Proficiency in SQL scripting, healthcare workflows, data validation, "
            "and SLA monitoring required."
        ),
    },
    {
        "company": "CitiusTech",
        "role": "Healthcare Data Systems Analyst",
        "location": "Chennai / Bengaluru, India",
        "jd": (
            "Looking for a Healthcare Data Systems Analyst to design and support clinical data pipelines and healthcare data warehouses. "
            "Responsibilities: Collect, interpret, and validate multi-million row clinical and patient datasets. Ensure data quality, "
            "troubleshoot ETL pipeline discrepancies, and adhere to healthcare interoperability (HL7/FHIR) and HIPAA privacy standards. "
            "Hands-on expertise in advanced SQL, ETL, database management, and Python automation required."
        ),
    },
    {
        "company": "Philips Healthcare",
        "role": "Healthcare Quality & Clinical Data Analyst",
        "location": "Bengaluru / Chennai, India",
        "jd": (
            "Philips is hiring a Clinical & Healthcare Quality Data Analyst. Analyze complex healthcare and product quality datasets "
            "using SQL and advanced Power BI. Build automated telemetry for Turnaround Time (TAT) and operational efficiency. "
            "Implement automated anomaly detection, manage CAPA tracking and root cause analysis (RCA), and ensure strict HIPAA/PHI "
            "compliance across healthcare delivery systems."
        ),
    },
]


async def run_generation():
    results = []
    print("\n" + "=" * 75)
    print("🚀 GENERATING ATS RESUMES FOR REAL HEALTHCARE JOB OPENINGS")
    print("=" * 75 + "\n")

    for idx, target in enumerate(ACTIVE_HEALTHCARE_JOBS, start=1):
        company = target["company"]
        role = target["role"]
        jd = target["jd"]

        print(f"[{idx}/4] Generating Tailored ATS Resume for {company} — {role}...")

        state = {
            "company_name": company,
            "role_title": role,
            "jd_text": jd,
        }

        # 1. Tailor Resume Node
        tailored_state = tailor_resume_node(state)
        state.update(tailored_state)

        # 2. Render ATS PDF via Playwright
        pdf_res = await generate_pdf_node(state)
        pdf_path = pdf_res.get("pdf_path", "")

        tailored = state.get("tailored_resume", {})
        score = state.get("match_score", 90)

        results.append({
            "index": idx,
            "company": company,
            "role": role,
            "location": target["location"],
            "score": score,
            "summary": tailored.get("tailored_summary", ""),
            "primary_skills": tailored.get("skills", {}).get("primary_matched", []),
            "secondary_skills": tailored.get("skills", {}).get("secondary", []),
            "pdf_path": pdf_path,
            "pdf_basename": os.path.basename(pdf_path),
        })

        print(f"   ✓ PDF Created: {os.path.basename(pdf_path)} (Match Score: {score}/100)\n")

    out_file = Path("output/active_healthcare_openings_resumes.json")
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved summary to {out_file.resolve()}")
    return results


if __name__ == "__main__":
    asyncio.run(run_generation())
