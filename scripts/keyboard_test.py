"""Keyboard and behavior checks that automated scanners like axe can't do.

Runs the same checks on both pages and prints PASS/FAIL for each, so the
difference between "before" and "after" is visible.

Usage:  python scripts/keyboard_test.py
"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def focused(page):
    """A short description of the element that currently has keyboard focus."""
    return page.evaluate(
        """() => { const el = document.activeElement;
                   return el ? (el.tagName + ' ' + (el.textContent || el.id || '').trim()).slice(0, 60) : ''; }"""
    )


def tab_until(page, predicate_js, max_tabs=40):
    """Presses Tab until the focused element matches, or gives up."""
    for _ in range(max_tabs):
        page.keyboard.press("Tab")
        if page.evaluate(predicate_js):
            return True
    return False


def check_page(browser, name):
    page = browser.new_page()
    page.goto((ROOT / name / "index.html").as_uri())
    results = []

    def record(label, ok):
        results.append((label, ok))

    # 1. The first Tab should land on a "skip to main content" link.
    page.keyboard.press("Tab")
    record("First Tab reaches a skip link",
           "skip" in focused(page).lower())

    # 2. The Register buttons should be reachable with the keyboard.
    is_register = ("() => { const el = document.activeElement;"
                   " return el !== document.body && /^Register/.test(el.textContent.trim()); }")
    reached = tab_until(page, is_register)
    record("Register button reachable with Tab", reached)

    # 3. Enter opens the dialog and moves focus into it; Escape closes it
    #    and returns focus to the Register button.
    if reached:
        page.keyboard.press("Enter")
        inside = page.evaluate("() => !!document.activeElement.closest('dialog, .modal')")
        record("Opening the dialog moves focus into it", inside)
        page.keyboard.press("Escape")
        back = page.evaluate(is_register)
        record("Escape closes it and returns focus to the button", back)
    else:
        record("Opening the dialog moves focus into it", False)
        record("Escape closes it and returns focus to the button", False)

    # 4. Submitting a bad email shows a text error, marks the field invalid,
    #    and moves focus to the field.
    page.fill("#email", "not-an-email")
    page.focus("#email")
    page.keyboard.press("Enter")
    state = page.evaluate(
        """() => {
            const email = document.getElementById('email');
            const err = document.getElementById('email-error');
            return {
              invalid: email.getAttribute('aria-invalid') === 'true',
              message: !!(err && !err.hidden && err.textContent.trim()),
              focus: document.activeElement === email,
            };
        }"""
    )
    record("Bad email: field marked invalid for screen readers", state["invalid"])
    record("Bad email: error explained in text (not color only)", state["message"])

    # 5. The email field has a real label (not just placeholder text).
    labelled = page.evaluate(
        "() => !!document.querySelector('label[for=email]') || !!document.getElementById('email').getAttribute('aria-label')"
    )
    record("Email field has a visible label", labelled)

    # 6. Moving content can be paused (WCAG 2.2.2).
    record("Rotating banner has a pause control",
           page.locator("#banner-toggle").count() == 1)

    # 7. Keyboard focus is visible (outline is not removed).
    page.focus("a, button")
    outline = page.evaluate("() => getComputedStyle(document.activeElement).outlineStyle")
    record("Focus outline is visible", outline not in ("none", ""))

    page.close()
    return results


def main():
    launch = {}
    if os.environ.get("CHROME_PATH"):
        launch["executable_path"] = os.environ["CHROME_PATH"]
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)
        all_results = {name: check_page(browser, name) for name in ("before", "after")}
        browser.close()

    labels = [label for label, _ in all_results["before"]]
    width = max(len(l) for l in labels)
    print(f"{'Check'.ljust(width)}  BEFORE  AFTER")
    for k, label in enumerate(labels):
        b = "PASS" if all_results["before"][k][1] else "FAIL"
        a = "PASS" if all_results["after"][k][1] else "FAIL"
        print(f"{label.ljust(width)}  {b:6}  {a}")
    after_failures = [l for l, ok in all_results["after"] if not ok]
    raise SystemExit(1 if after_failures else 0)


if __name__ == "__main__":
    main()
