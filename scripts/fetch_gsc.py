"""
Fetch Google Search Console data for rhytm.store
Run once to authenticate (browser opens), then token is saved locally.
Usage: python src/scripts/fetch_gsc.py
"""

import os
import json
from datetime import date, timedelta
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

ROOT = Path(__file__).parent.parent.parent
CREDENTIALS_FILE = ROOT / ".credentials" / "oauth_client.json"
TOKEN_FILE = ROOT / ".credentials" / "token_gsc.json"
OUTPUT_DIR = ROOT / "src" / "analytics"

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SITE_URL = os.getenv("GSC_SITE_URL", "sc-domain:rhytm.store")


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def fetch_top_keywords(service, days=28):
    end = date.today()
    start = end - timedelta(days=days)
    response = service.searchanalytics().query(
        siteUrl=SITE_URL,
        body={
            "startDate": str(start),
            "endDate": str(end),
            "dimensions": ["query"],
            "rowLimit": 25,
            "orderBy": [{"fieldName": "impressions", "sortOrder": "DESCENDING"}],
        },
    ).execute()
    return response.get("rows", [])


def fetch_top_pages(service, days=28):
    end = date.today()
    start = end - timedelta(days=days)
    response = service.searchanalytics().query(
        siteUrl=SITE_URL,
        body={
            "startDate": str(start),
            "endDate": str(end),
            "dimensions": ["page"],
            "rowLimit": 10,
            "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
        },
    ).execute()
    return response.get("rows", [])


def fetch_daily_trend(service, days=28):
    end = date.today()
    start = end - timedelta(days=days)
    response = service.searchanalytics().query(
        siteUrl=SITE_URL,
        body={
            "startDate": str(start),
            "endDate": str(end),
            "dimensions": ["date"],
            "rowLimit": 90,
        },
    ).execute()
    return response.get("rows", [])


def format_report(keywords, pages, trend):
    today = date.today().isoformat()
    lines = [
        f"# Google Search Console — rhytm.store",
        f"> Generato: {today} | Periodo: ultimi 28 giorni\n",
        "## Top Keywords (per impressioni)",
        "| Keyword | Impressioni | Click | CTR | Posizione |",
        "|---|---|---|---|---|",
    ]
    for row in keywords:
        k = row["keys"][0]
        imp = row.get("impressions", 0)
        clk = row.get("clicks", 0)
        ctr = f"{row.get('ctr', 0)*100:.1f}%"
        pos = f"{row.get('position', 0):.1f}"
        lines.append(f"| {k} | {imp} | {clk} | {ctr} | {pos} |")

    lines += [
        "",
        "## Top Pagine (per click)",
        "| URL | Click | Impressioni | CTR | Posizione |",
        "|---|---|---|---|---|",
    ]
    for row in pages:
        url = row["keys"][0].replace("https://rhytm.store", "")
        clk = row.get("clicks", 0)
        imp = row.get("impressions", 0)
        ctr = f"{row.get('ctr', 0)*100:.1f}%"
        pos = f"{row.get('position', 0):.1f}"
        lines.append(f"| {url} | {clk} | {imp} | {ctr} | {pos} |")

    total_clicks = sum(r.get("clicks", 0) for r in trend)
    total_impressions = sum(r.get("impressions", 0) for r in trend)
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0
    avg_pos = sum(r.get("position", 0) for r in trend) / len(trend) if trend else 0

    lines += [
        "",
        "## Riepilogo periodo",
        f"| Metrica | Valore |",
        f"|---|---|",
        f"| Click totali | {total_clicks} |",
        f"| Impressioni totali | {total_impressions} |",
        f"| CTR medio | {avg_ctr:.2f}% |",
        f"| Posizione media | {avg_pos:.1f} |",
    ]
    return "\n".join(lines)


def main():
    print("Autenticazione Google...")
    creds = get_credentials()
    service = build("searchconsole", "v1", credentials=creds)
    print(f"Connesso. Fetching dati per {SITE_URL}...")

    keywords = fetch_top_keywords(service)
    pages = fetch_top_pages(service)
    trend = fetch_daily_trend(service)

    report = format_report(keywords, pages, trend)
    output_file = OUTPUT_DIR / f"gsc-{date.today().isoformat()}.md"
    output_file.write_text(report)
    print(f"Report salvato: {output_file}")
    print(report)


if __name__ == "__main__":
    main()
