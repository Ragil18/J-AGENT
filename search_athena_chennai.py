from playwright.sync_api import sync_playwright
import json

def search_chennai():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        page.goto("https://careers.athenahealth.com/us/en/search-results?location=Chennai%2C%20Tamil%20Nadu%2C%20India", timeout=30000)
        page.wait_for_timeout(4000)
        jobs = page.evaluate("""() => {
            const list = [];
            document.querySelectorAll('a[data-ph-at-id="job-link"]').forEach(a => {
                list.push({
                    title: a.innerText.trim(),
                    url: a.href
                });
            });
            if (list.length === 0) {
                document.querySelectorAll('a[href*="/job/"]').forEach(a => {
                    list.push({
                        title: a.innerText.trim(),
                        url: a.href
                    });
                });
            }
            return list;
        }""")
        print(f"Found {len(jobs)} jobs in Chennai:")
        print(json.dumps(jobs[:10], indent=2))
        b.close()

if __name__ == "__main__":
    search_chennai()
