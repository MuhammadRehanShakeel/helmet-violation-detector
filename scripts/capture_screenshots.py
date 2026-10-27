"""
capture_screenshots.py - Takes the README / LinkedIn screenshots of the RUNNING app.

Needs: the app running (start_project.bat) and DEMO_ACCOUNT.txt in the project folder with
    admin_email=...
    admin_password=...
(DEMO_ACCOUNT.txt is git-ignored, so the password never goes to GitHub.)

Run: scripts\windows\capture_screenshots.bat   -> pictures are saved in docs/screenshots/
Uses the Edge or Chrome already installed on the PC (nothing big to download).
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "screenshots")
APP = "http://localhost:5174"


def read_account():
    values = {}
    with open(os.path.join(ROOT, "DEMO_ACCOUNT.txt"), encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                key, _, value = line.strip().partition("=")
                values[key.strip()] = value.strip()
    return values["admin_email"], values["admin_password"]


def launch(p):
    for channel in ("msedge", "chrome"):
        try:
            return p.chromium.launch(channel=channel)
        except Exception:
            continue
    return p.chromium.launch()


def login(page, email, password):
    page.goto(f"{APP}/login")
    page.fill("input[type=email]", email)
    page.fill("input[type=password]", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{APP}/", timeout=20000)
    page.wait_for_timeout(2500)


def shot(page, name, full_page=False, wait=2000):
    try:
        page.wait_for_timeout(wait)
        page.screenshot(path=os.path.join(OUT, name), full_page=full_page)
        print("saved", name)
    except Exception as e:
        print("skipped", name, "-", e)


def main():
    os.makedirs(OUT, exist_ok=True)
    email, password = read_account()
    with sync_playwright() as p:
        browser = launch(p)

        # ---------- desktop ----------
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.goto(f"{APP}/login")
        shot(page, "01_login.png", wait=1500)
        login(page, email, password)
        shot(page, "02_dashboard.png", full_page=True)

        page.goto(f"{APP}/analyze")
        shot(page, "03_analyse_media.png")

        page.goto(f"{APP}/violations")
        page.wait_for_timeout(1500)
        page.get_by_role("tab", name="All").click()
        shot(page, "04_review_queue.png", wait=3500)

        ids = page.evaluate("""async () => {
            const h = {Authorization: 'Bearer ' + sessionStorage.getItem('rg_token')};
            const r = await (await fetch('/api/violations?page_size=100', {headers: h})).json();
            const pick = (f) => (r.items.find(f) || {}).violation_id;
            return {
              triple: pick(v => v.violation_type === 'TRIPLE_RIDING' && v.challan_id),
              approved: pick(v => v.violation_type === 'NO_HELMET' && v.challan_id),
              pending: pick(v => v.status === 'pending' && !v.low_confidence),
              rejected: pick(v => v.status === 'rejected'),
            };
        }""")
        print("violations used:", ids)

        def open_violation(vid, name):
            if not vid:
                return
            try:
                _open(vid)
                shot(page, name, wait=3500)
            except Exception as e:
                print("skipped", name, "-", e)

        def _open(vid):
            page.goto(f"{APP}/violations")
            page.wait_for_timeout(1500)
            page.get_by_role("tab", name="All").click()
            page.wait_for_timeout(2000)
            page.locator(".MuiCardActionArea-root").filter(has_text=f"#{vid} ").first.click(timeout=10000)

        open_violation(ids.get("triple"), "05_violation_triple_riding_challan.png")
        open_violation(ids.get("pending"), "06_violation_review.png")
        open_violation(ids.get("rejected"), "07_violation_rejected_false_alarm.png")

        page.goto(f"{APP}/plates")
        page.wait_for_timeout(1200)
        page.fill("input", "DEMO-7")
        page.click("button[type=submit]")
        shot(page, "08_plate_search_repeat_offender.png", wait=2500)

        page.goto(f"{APP}/live")
        shot(page, "09_live_camera.png")
        page.goto(f"{APP}/users")
        shot(page, "10_users_roles.png")
        page.goto(f"{APP}/audit")
        shot(page, "11_audit_log.png")
        page.goto(f"{APP}/cameras")
        shot(page, "12_cameras.png")
        page.close()

        # ---------- phone (same as the Android app) ----------
        phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                 is_mobile=True, has_touch=True)
        login(phone, email, password)
        shot(phone, "13_phone_dashboard.png")
        phone.goto(f"{APP}/violations")
        phone.wait_for_timeout(1500)
        phone.get_by_role("tab", name="All").click()
        shot(phone, "14_phone_review_queue.png", wait=3500)
        if ids.get("triple"):
            phone.locator(".MuiCardActionArea-root").filter(has_text=f"#{ids['triple']} ").first.click()
            shot(phone, "15_phone_violation.png", wait=3500)
        browser.close()
    print("\nDone. Screenshots are in docs\\screenshots")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)
