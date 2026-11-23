from playwright.sync_api import sync_playwright
import json

def search_india():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        page.goto("https://careers.athenahealth.com/us/en/search-results?location=India", timeout=30000)
        page.wait_for_timeout(4000)
        jobs = page.evaluate("""() => {
            const list = [];
            const seen = new Set();
            document.querySelectorAll('a[data-ph-at-id="job-link"]').forEach(a => {
                const title = a.innerText.trim();
                const url = a.href;
                if (!seen.has(url)) {
                    seen.add(url);
                    list.push({ title, url });
                }
            });
            return list;
        }""")
        print(f"Found {len(jobs)} active jobs in India at athenahealth:")
        print(json.dumps(jobs, indent=2))
        b.close()

if __name__ == "__main__":
    search_india()
