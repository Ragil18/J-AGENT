from playwright.sync_api import sync_playwright
import json

def inspect_form():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        page.goto("https://careers.athenahealth.com/us/en/apply?jobSeqNo=ATHAHHUSR15332EXTERNALENUS", timeout=30000)
        page.wait_for_timeout(4000)
        
        inputs = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('input, select, textarea')).map(el => ({
                tag: el.tagName,
                type: el.type,
                name: el.name,
                id: el.id,
                placeholder: el.placeholder,
                ariaLabel: el.getAttribute('aria-label') || ''
            }));
        }""")
        print(f"Title: {page.title()}")
        print(f"URL: {page.url}")
        print("Inputs found:")
        print(json.dumps(inputs[:20], indent=2))
        b.close()

if __name__ == "__main__":
    inspect_form()
