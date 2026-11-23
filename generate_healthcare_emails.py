"""Draft company-specific cold emails for the 4 real healthcare openings."""

import json
from pathlib import Path

OPENINGS = [
    {
        "company": "Optum (UnitedHealth Group)",
        "role": "Healthcare Data Analyst & BI Developer",
        "hiring_manager": "Healthcare Analytics Talent Acquisition Team",
        "email": "optum_careers@unitedhealthgroup.com",
        "hook": "I noticed Optum's continuous expansion in scaling clinical and claims analytics intelligence across India.",
        "pitch": (
            "With nearly 2 years of dedicated healthcare analytics experience at Neuberg Diagnostics, I architected regional diagnostic "
            "performance telemetry, automated multi-million row SQL ETL pipelines, and built Power BI executive dashboards that slashed "
            "diagnostic turnaround times (TAT) by 20% and automated weekly MIS reporting (saving 10+ hours weekly). "
            "In my current role at DAC Developers, I deploy production AI automation workflows and FastAPI microservices."
        ),
        "pdf_path": "Resume_Optum_UnitedHealth_Group_Healthcare_Data_Analyst__BI_Developer.pdf"
    },
    {
        "company": "athenahealth",
        "role": "Data Operations Analyst (Platform & EHR)",
        "hiring_manager": "Chennai Data Operations Hiring Team",
        "email": "chennaicareers@athenahealth.com",
        "hook": "I am following athenahealth Chennai's work expanding cloud-based EHR and platform interoperability services.",
        "pitch": (
            "At Neuberg Diagnostics, I conducted backend validation for healthcare applications (Neu5R), tracked laboratory SLA/CAPA metrics, "
            "and engineered an end-to-end patient Net Promoter Score (NPS) portal in Python and SQL. My background in healthcare data validation, "
            "HIPAA/PHI security awareness, and standard operating procedure (SOP) documentation directly aligns with your Platform Operations standards."
        ),
        "pdf_path": "Resume_athenahealth_Data_Operations_Analyst_Platform__EHR.pdf"
    },
    {
        "company": "CitiusTech",
        "role": "Healthcare Data Systems Analyst",
        "hiring_manager": "Healthcare Technology Practice Lead",
        "email": "careers@citiustech.com",
        "hook": "Given CitiusTech's leadership in US healthcare interoperability, payer/provider data systems, and FHIR standards.",
        "pitch": (
            "Having managed diagnostic data ETL pipelines between production and disaster-recovery backup servers at Neuberg Diagnostics, "
            "optimized complex SQL queries across multi-million row clinical datasets, and maintained laboratory data integrity, "
            "I bring hands-on experience bridging raw healthcare feeds into actionable, compliant data models."
        ),
        "pdf_path": "Resume_CitiusTech_Healthcare_Data_Systems_Analyst.pdf"
    },
    {
        "company": "Philips Healthcare",
        "role": "Healthcare Quality & Clinical Data Analyst",
        "hiring_manager": "Clinical Quality & Analytics Talent Team",
        "email": "careers.india@philips.com",
        "hook": "Philips Healthcare's commitment to patient-centric medical technology and clinical operational excellence stands out.",
        "pitch": (
            "During my 2 years in healthcare analytics at Neuberg Diagnostics, I engineered real-time Turnaround Time (TAT) monitoring "
            "dashboards that improved laboratory operational efficiency by 25% and deployed Python/OpenCV operational analytics solutions. "
            "I combine strong clinical data governance and root cause analysis (RCA) with scalable Power BI and Python automation."
        ),
        "pdf_path": "Resume_Philips_Healthcare_Healthcare_Quality__Clinical_Data_Analyst.pdf"
    }
]

emails = []
for item in OPENINGS:
    subject = f"Application: {item['role']} — Ragil Immanuvel PD (Healthcare Analytics & Automation Background)"
    body = (
        f"Dear {item['hiring_manager']},\n\n"
        f"{item['hook']} I am writing to express my strong interest in the {item['role']} position at {item['company']}.\n\n"
        f"{item['pitch']}\n\n"
        f"I have attached my tailored ATS resume ({item['pdf_path']}) for your review. My complete portfolio, code repositories, and project demonstrations are accessible at https://ragil-portfolio-site.vercel.app/.\n\n"
        f"I would welcome the opportunity to discuss how my healthcare diagnostic analytics background can contribute to {item['company']}'s goals.\n\n"
        f"Best regards,\n"
        f"Ragil Immanuvel PD\n"
        f"+91 9345741472 | ragilimmanuvel@gmail.com\n"
        f"Chennai, India | https://ragil-portfolio-site.vercel.app/"
    )
    emails.append({
        "company": item["company"],
        "role": item["role"],
        "subject": subject,
        "recipient": item["email"],
        "body": body,
        "resume_pdf": item["pdf_path"]
    })

out = Path("output/healthcare_outreach_emails.json")
out.write_text(json.dumps(emails, indent=2), encoding="utf-8")
print(f"Drafted 4 outreach emails in {out.resolve()}")
