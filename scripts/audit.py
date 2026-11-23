"""Runs the axe-core accessibility engine against the before and after pages
and saves the results to docs/axe-results.json.

Usage (from the project folder, after `npm install`):
    pip install playwright && playwright install chromium
    python scripts/audit.py
"""

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
AXE = ROOT / "node_modules" / "axe-core" / "axe.min.js"


def run_axe(page, url):
    page.goto(url)
    page.add_script_tag(path=str(AXE))
    return page.evaluate(
        """async () => {
            const r = await axe.run(document, {
              runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'] }
            });
            return r.violations.map(v => ({
              id: v.id, impact: v.impact, help: v.help, wcag: v.tags.filter(t => t.startsWith('wcag') && /\\d/.test(t)),
              nodes: v.nodes.length
            }));
        }"""
    )


def main():
    if not AXE.exists():
        sys.exit("axe-core not found. Run `npm install` first.")
    launch = {}
    if os.environ.get("CHROME_PATH"):
        launch["executable_path"] = os.environ["CHROME_PATH"]
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)
        page = browser.new_page()
        for name in ("before", "after"):
            url = (ROOT / name / "index.html").as_uri()
            violations = run_axe(page, url)
            results[name] = {
                "rules_failed": len(violations),
                "elements_affected": sum(v["nodes"] for v in violations),
                "violations": violations,
            }
            print(f"{name}: {len(violations)} rules failed, "
                  f"{results[name]['elements_affected']} elements affected")
            for v in violations:
                print(f"   - [{v['impact']}] {v['id']}: {v['help']} ({v['nodes']})")
        browser.close()
    out = ROOT / "docs" / "axe-results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"Saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
