"""Browser walk-through of the acceptance workflow (optional; needs: pip install playwright; playwright install chromium).

Start from fresh sample data (python -m app.seed --reset), start backend and frontend, then run:
    python tools/e2e_acceptance.py docs/screenshots
"""
import sys
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:5173"
SHOTS = sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots"
errors = []


def shot(page, name):
    page.wait_for_timeout(400)  # let dialogs finish animating
    page.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)


def login(page, user, pw="Connect@2026"):
    page.goto(BASE + "/login")
    page.get_by_label("Username").fill(user)
    page.get_by_role("textbox", name="Password").fill(pw)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("button", name="Log out")).to_be_visible()


def logout(page):
    page.get_by_role("button", name="Log out").click()
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(BASE + "/login")
    shot(page, "01-login")

    # 1-2 lab registers patient
    login(page, "lab1")
    shot(page, "02-lab-dashboard")
    page.get_by_role("link", name="Patients", exact=True).click()
    page.get_by_role("button", name="Register patient").click()
    page.get_by_label("Full name").fill("Priya Nair")
    page.get_by_label("Birth date").fill("1992-08-10")
    page.get_by_label("Mobile (10 digits, optional)").fill("9000000055")
    page.get_by_label("Patient portal username").fill("priya")
    page.get_by_label("Temporary password").fill("Priya@123")
    page.get_by_role("button", name="Register", exact=True).click()
    expect(page.get_by_text("Patient registered with patient ID")).to_be_visible()

    # 3-4 CBC report with LOINC codes
    page.get_by_role("link", name="Create report", exact=True).click()
    expect(page.get_by_label("Patient")).to_have_value("Priya Nair (PAT-000003)")
    page.get_by_role("button", name="Fill CBC template").click()
    expect(page.get_by_label("Report title")).to_have_value("Complete Blood Count")
    values = ["13.2", "11.9", "4.6", "40.1", "88", "29", "33", "260"]
    for i, v in enumerate(values):
        page.get_by_label("Result").nth(i).fill(v)
    # Manually add one more row using the LOINC search (abbreviation search)
    page.get_by_role("button", name="Add test").click()
    picker = page.get_by_label("Test 9: LOINC concept")
    picker.fill("ESR")
    page.get_by_role("option", name="4537-7").click()
    page.get_by_label("Result").nth(8).fill("12")
    page.get_by_label("Ref low").nth(8).fill("0")
    page.get_by_label("Ref high").nth(8).fill("20")
    shot(page, "03-report-form")
    page.get_by_role("button", name="Save report").click()
    expect(page.get_by_text("Report saved.")).to_be_visible()
    expect(page.get_by_text("4537-7")).to_be_visible()
    shot(page, "04-report-view")
    report_url = page.url
    page.get_by_role("tab", name="FHIR R4 JSON").click()
    expect(page.get_by_text("Valid. Checked against")).to_be_visible()
    shot(page, "05-fhir-viewer")
    logout(page)

    # 6-7 hospital requests access
    login(page, "hospital1")
    page.get_by_role("link", name="Find patient", exact=True).click()
    page.get_by_placeholder("e.g. Asha or PAT-000001").fill("Priya")
    page.get_by_role("button", name="Search").click()
    page.get_by_role("link", name="Open", exact=True).first.click()
    page.get_by_role("button", name="Request access").click()
    page.get_by_role("button", name="Send request").click()
    expect(page.get_by_text("Access request sent")).to_be_visible()
    page.get_by_role("link", name="Access requests", exact=True).click()
    page.get_by_role("button", name="Retrieve").first.click()
    expect(page.get_by_text("Access denied: consent is PENDING")).to_be_visible()
    shot(page, "06-hospital-pending-denied")
    logout(page)

    # 8 patient approves
    login(page, "priya", "Priya@123")
    shot(page, "07-patient-dashboard")
    page.get_by_role("link", name="Consent center", exact=True).click()
    page.get_by_role("button", name="Approve").click()
    page.get_by_role("dialog").get_by_role("button", name="Approve").click()
    expect(page.get_by_text("Consent approved.")).to_be_visible()
    shot(page, "08-consent-approved")
    logout(page)

    # 9 hospital retrieves
    login(page, "hospital1")
    page.get_by_role("link", name="Access requests", exact=True).click()
    page.get_by_role("button", name="Retrieve").first.click()
    expect(page.get_by_text("Access granted by the patient's consent")).to_be_visible()
    shot(page, "09-hospital-retrieved")
    page.get_by_role("dialog").get_by_role("tab", name="FHIR R4 JSON").click()
    expect(page.get_by_role("dialog").get_by_text("Valid. Checked against")).to_be_visible()
    page.get_by_role("button", name="Close").click()
    # Hospital cannot open the report page directly
    page.goto(report_url)
    expect(page.get_by_text("not available for your role")).to_be_visible()
    logout(page)

    # 11 patient revokes
    login(page, "priya", "Priya@123")
    page.get_by_role("link", name="Consent center", exact=True).click()
    page.get_by_role("button", name="Revoke").click()
    page.get_by_role("dialog").get_by_role("button", name="Revoke").click()
    expect(page.get_by_text("Consent revoked.")).to_be_visible()
    page.get_by_role("link", name="Access history", exact=True).click()
    expect(page.get_by_text("CONSENT_REVOKED").first).to_be_visible()
    shot(page, "10-patient-history")
    logout(page)

    login(page, "hospital1")
    page.get_by_role("link", name="Access requests", exact=True).click()
    page.get_by_role("button", name="Retrieve").first.click()
    expect(page.get_by_text("Access denied: consent is REVOKED")).to_be_visible()
    shot(page, "11-hospital-revoked-denied")
    logout(page)

    # 10 admin audit log + admin pages
    login(page, "admin")
    shot(page, "12-admin-dashboard")
    page.get_by_role("link", name="Audit log", exact=True).click()
    expect(page.get_by_text("REPORT_RETRIEVE").first).to_be_visible()
    shot(page, "13-audit-log")
    page.get_by_role("link", name="Users & facilities", exact=True).click()
    page.get_by_label("Facility name").fill("Riverside Clinic")
    page.get_by_role("button", name="Add facility").click()
    expect(page.get_by_text("FAC-LAB-005")).to_be_visible()
    shot(page, "14-admin-users")

    # Session expiry: break the token and reload
    page.evaluate("sessionStorage.setItem('token', 'expired.token.value')")
    page.goto(BASE + "/audit")
    expect(page.get_by_text("Your session ended")).to_be_visible()
    browser.close()

real = [e for e in errors if "401" not in e and "403" not in e and "409" not in e]
print("console errors:", real or "none")
print("E2E OK")
