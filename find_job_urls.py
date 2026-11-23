from playwright.sync_api import sync_playwright
import json

def get_links():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        page.goto("https://www.athenahealth.com/careers", timeout=30000)
        links = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a')).map(a => ({
                text: a.innerText.trim(),
                href: a.href
            })).filter(x => x.href && (x.href.includes('job') || x.href.includes('phenom') || x.href.includes('search') || x.href.includes('lever') || x.href.includes('greenhouse')));
        }""")
        print(json.dumps(links[:15], indent=2))
        b.close()

if __name__ == "__main__":
    get_links()
