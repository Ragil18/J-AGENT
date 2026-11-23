"""Automated Form Filler Agent for athenahealth Job Application."""

from pathlib import Path
import time
from playwright.sync_api import sync_playwright

RESUME_PATH = Path("d:/NOV-2026/TEST-AGENT/output/Resume_athenahealth_Data_Operations_Analyst_Platform__EHR.pdf").resolve()
SCREENSHOT_PATH = Path("d:/NOV-2026/TEST-AGENT/output/athenahealth_application_filled.png").resolve()

def autofill_athena():
    print("\n" + "=" * 70)
    print("🤖 LAUNCHING AGENT: AUTONOMOUS FORM FILLER (athenahealth)")
    print("=" * 70 + "\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()
        
        apply_url = "https://careers.athenahealth.com/us/en/apply?jobSeqNo=ATHAHHUSR15332EXTERNALENUS&step=1&stepname=personalInformation"
        print(f"Step 1: Navigating to application form: {apply_url}")
        page.goto(apply_url, timeout=45000)
        page.wait_for_timeout(3000)

        # 1. Attach Resume
        if RESUME_PATH.exists():
            print(f"Step 2: Uploading tailored resume: {RESUME_PATH.name}")
            try:
                file_input = page.locator('input[type="file"]')
                if file_input.count() > 0:
                    file_input.set_input_files(str(RESUME_PATH))
                    print("   ✓ Resume uploaded successfully.")
                    page.wait_for_timeout(3000)
            except Exception as e:
                print(f"   ! Resume upload notification: {e}")

        # 2. Previous Worker Radio
        print("Step 3: Populating applicant details...")
        try:
            no_radio = page.locator('#previousWorker\\.false')
            if no_radio.count() > 0:
                no_radio.check(force=True)
                print("   ✓ Previous Worker: No")
        except Exception:
            pass

        # 3. Country / Region if selectable
        try:
            country_select = page.locator('#country')
            if country_select.count() > 0:
                country_select.select_option(label="India")
                print("   ✓ Country: India")
                page.wait_for_timeout(1000)
        except Exception:
            pass

        # 4. First Name
        try:
            fn = page.locator('input[id*="firstName"], input[name*="firstName"]')
            if fn.count() > 0:
                fn.fill("Ragil Immanuvel")
                print("   ✓ First Name: Ragil Immanuvel")
        except Exception as e:
            print(f"   ! First Name fill: {e}")

        # 5. Last Name
        try:
            ln = page.locator('input[id*="lastName"], input[name*="lastName"]')
            if ln.count() > 0:
                ln.fill("PD")
                print("   ✓ Last Name: PD")
        except Exception as e:
            print(f"   ! Last Name fill: {e}")

        # 6. Address
        try:
            addr = page.locator('input[id*="addressLine1"]')
            if addr.count() > 0:
                addr.fill("Chennai, Tamil Nadu")
                print("   ✓ Address: Chennai, Tamil Nadu")
        except Exception:
            pass

        # 7. City
        try:
            city = page.locator('input[id*="city"]')
            if city.count() > 0:
                city.fill("Chennai")
                print("   ✓ City: Chennai")
        except Exception:
            pass

        # 8. Email & Email Communication Consent
        try:
            email_input = page.locator('#email')
            if email_input.count() > 0:
                email_input.fill("ragilimmanuvel@gmail.com")
                print("   ✓ Email: ragilimmanuvel@gmail.com")
            
            consent_checkbox = page.locator('#emailCommunication')
            if consent_checkbox.count() > 0:
                consent_checkbox.check(force=True)
                print("   ✓ Email Communication Consent: Checked")
        except Exception as e:
            print(f"   ! Email fill: {e}")

        # 9. Phone Number
        try:
            phone_input = page.locator('input[id*="phoneNumber"]')
            if phone_input.count() > 0:
                phone_input.fill("9345741472")
                print("   ✓ Phone: +91 9345741472")
        except Exception as e:
            print(f"   ! Phone fill: {e}")

        page.wait_for_timeout(2000)

        # Take verification screenshot
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        print(f"\nStep 4: Saved full application state screenshot to: {SCREENSHOT_PATH.name}")
        print("CRITICAL SAFETY ENFORCED: Stopped before final submission button.\n")

        browser.close()

if __name__ == "__main__":
    autofill_athena()
