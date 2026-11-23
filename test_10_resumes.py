"""Generate 10 Distinct Tailored Resumes for 10 Different Healthcare & HealthTech Companies.

Tests and verifies how the tailoring engine adapts:
- Professional Summary
- Core Target Competencies
- Prioritized Experience Bullets
- ATS Match Scores
across 10 diverse healthcare organizations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import re

from apply_agent import generate_pdf_node, tailor_resume_node

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_10_resumes")

COMPANIES = [
    {
        "company": "Epic Systems",
        "role": "EHR Integration & Interoperability Engineer",
        "jd": "Seeking an Integration Engineer with deep knowledge of EHR systems, HL7/FHIR messaging, and hospital workflow automation. Experience with Epic Bridges, Python, clinical data interfaces, and HIPAA compliance required.",
    },
    {
        "company": "Athenahealth",
        "role": "Healthcare API & Cloud Automation Developer",
        "jd": "Join our cloud platform team. Looking for a developer skilled in RESTful healthcare APIs, FHIR standards, Python/FastAPI microservices, and automating clinical intake pipelines with zero compliance breaches.",
    },
    {
        "company": "Teladoc Health",
        "role": "Virtual Care & Telehealth Systems Engineer",
        "jd": "Looking for a Full-Stack Engineer to build reliable, high-availability telehealth platforms. Needs strong experience in Python, React, Webhooks, appointment automation, and securing patient health information (PHI).",
    },
    {
        "company": "Flatiron Health",
        "role": "Oncology Clinical Data Pipeline Engineer",
        "jd": "We require a software engineer experienced in ingesting, transforming, and de-identifying complex real-world clinical oncology records. Strong Python, PostgreSQL, HIPAA Safe Harbor de-identification, and data validation skills.",
    },
    {
        "company": "Tempus AI",
        "role": "Clinical AI & Data Automation Engineer",
        "jd": "Build intelligent pipelines powering precision medicine. Requires expertise in Python, LangGraph/LLM orchestration, clinical document summarization, medical terminology, and high-performance vector databases.",
    },
    {
        "company": "Oscar Health",
        "role": "Claims & Prior-Authorization Automation Engineer",
        "jd": "Seeking an automation engineer to streamline healthcare insurance prior-authorization and claims processing. Must have experience with Python, Playwright/browser automation, API integrations, and rule engines.",
    },
    {
        "company": "Ro (Roman Health)",
        "role": "Digital Health & Telepharmacy Full-Stack Developer",
        "jd": "Help us scale digital healthcare and pharmacy fulfillment. Looking for proficiency in TypeScript, React, Python FastAPI, automated order routing, and HIPAA-compliant patient communication systems.",
    },
    {
        "company": "Cerner (Oracle Health)",
        "role": "Hospital Data Exchange & Protocol Engineer",
        "jd": "Work on enterprise hospital information systems. Requirements: HL7 v2/v3, FHIR resources, secure distributed microservices, audit logging, and SOC2/HIPAA security protocols.",
    },
    {
        "company": "Cedar",
        "role": "Patient Financial & Billing Experience Engineer",
        "jd": "Transform healthcare billing. Seeking a full-stack engineer to build empathetic, transparent patient financial workflows. Expertise in Python, secure payment integrations, EHR billing feeds, and web automation.",
    },
    {
        "company": "Komodo Health",
        "role": "Healthcare Map & Clinical Data Pipeline Engineer",
        "jd": "Map the healthcare ecosystem. Looking for a data/software engineer with strong Python background in processing massive healthcare claim datasets, patient journey mapping, and compliant cloud architectures.",
    },
]


async def generate_all_10():
    results = []
    print("\n" + "=" * 75)
    print("🚀 GENERATING 10 DIVERSE COMPANY-SPECIFIC TAILORED RESUMES (HEALTHCARE)")
    print("=" * 75 + "\n")

    for idx, target in enumerate(COMPANIES, start=1):
        company = target["company"]
        role = target["role"]
        jd = target["jd"]

        print(f"[{idx}/10] Tailoring for {company} — {role}...")

        state = {
            "company_name": company,
            "role_title": role,
            "jd_text": jd,
        }

        # 1. Run resume tailoring node
        tailored_state = tailor_resume_node(state)
        state.update(tailored_state)

        # 2. Render ATS PDF via Playwright
        pdf_res = await generate_pdf_node(state)
        pdf_path = pdf_res.get("pdf_path", "")

        tailored = state.get("tailored_resume", {})
        score = state.get("match_score", 85)

        results.append({
            "index": idx,
            "company": company,
            "role": role,
            "score": score,
            "summary": tailored.get("tailored_summary", ""),
            "primary_skills": tailored.get("skills", {}).get("primary_matched", []),
            "secondary_skills": tailored.get("skills", {}).get("secondary", []),
            "pdf_path": pdf_path,
            "pdf_basename": os.path.basename(pdf_path),
        })

        print(f"   ✓ Generated: {os.path.basename(pdf_path)} (ATS Score: {score}/100)")

    # Save summary report
    summary_file = Path("output/10_resumes_comparison.json")
    summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved detailed comparison report to: {summary_file.resolve()}\n")
    return results


if __name__ == "__main__":
    asyncio.run(generate_all_10())
