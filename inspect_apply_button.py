from playwright.sync_api import sync_playwright

def inspect_apply():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        page.goto("https://careers.athenahealth.com/us/en/job/R15332/Lead-Software-Engineer-Medication-Management", timeout=30000)
        page.wait_for_timeout(3000)
        apply_links = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a, button')).map(el => ({
                tag: el.tagName,
                text: el.innerText.trim(),
                href: el.href || el.getAttribute('href') || '',
                id: el.id,
                className: el.className
            })).filter(x => x.text.toLowerCase().includes('apply'));
        }""")
        print("Apply elements found:")
        import json
        print(json.dumps(apply_links, indent=2))
        b.close()

if __name__ == "__main__":
    inspect_apply()
