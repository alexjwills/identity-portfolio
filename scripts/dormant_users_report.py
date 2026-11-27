"""List Okta users inactive for 60 days or more, and users who have never signed in.

Set OKTA_DOMAIN (for example https://your-org.okta.com) and OKTA_API_TOKEN
as environment variables before running. The report contains user emails,
so it is written locally and never committed.
"""

import csv
import os
import sys
from datetime import datetime, timezone

import requests

DAYS_THRESHOLD = 60
REPORT_FILE = "Dormant_Users_60_Days_Report.csv"

okta_domain = os.environ.get("OKTA_DOMAIN")
api_token = os.environ.get("OKTA_API_TOKEN")

if not okta_domain or not api_token:
    sys.exit("Set OKTA_DOMAIN and OKTA_API_TOKEN as environment variables first.")

headers = {
    "Accept": "application/json",
    "Authorization": f"SSWS {api_token}",
}

print(f"[*] Auditing Okta tenant for accounts inactive >= {DAYS_THRESHOLD} days...")

# Okta returns users in pages. Each response links to the next page in its
# Link header, which requests exposes as response.links.
users = []
url = f"{okta_domain}/api/v1/users?limit=200"
while url:
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        sys.exit(f"[!] Error: {response.status_code} - {response.text}")
    users.extend(response.json())
    url = response.links.get("next", {}).get("url")

now = datetime.now(timezone.utc)
dormant_users = []

for u in users:
    p = u.get("profile", {})
    last_login = u.get("lastLogin")

    if last_login:
        login_dt = datetime.fromisoformat(last_login.replace("Z", "+00:00"))
        days_inactive = (now - login_dt).days
        if days_inactive >= DAYS_THRESHOLD:
            dormant_users.append({
                "User ID": u.get("id"),
                "Email": p.get("email"),
                "Department": p.get("department", "N/A"),
                "Status": u.get("status"),
                "Last Login": login_dt.strftime("%Y-%m-%d"),
                "Days Inactive": days_inactive,
            })
    else:
        # Accounts that were created but have never signed in
        dormant_users.append({
            "User ID": u.get("id"),
            "Email": p.get("email"),
            "Department": p.get("department", "N/A"),
            "Status": u.get("status"),
            "Last Login": "Never Logged In",
            "Days Inactive": "N/A",
        })

fieldnames = ["User ID", "Email", "Department", "Status", "Last Login", "Days Inactive"]
with open(REPORT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(dormant_users)

print(
    f"[+] Checked {len(users)} users. Found {len(dormant_users)} dormant or "
    f"never-used accounts. Report saved to '{REPORT_FILE}'."
)
