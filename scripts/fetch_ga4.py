"""
Fetch Google Analytics 4 data for rhytm.store
Reuses the same OAuth token from GSC (webmasters scope + analytics scope).
Usage: python src/scripts/fetch_ga4.py
"""

import os
from datetime import date, timedelta
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    OrderBy,
)

ROOT = Path(__file__).parent.parent.parent
CREDENTIALS_FILE = ROOT / ".credentials" / "oauth_client.json"
TOKEN_FILE = ROOT / ".credentials" / "token_ga4.json"
OUTPUT_DIR = ROOT / "src" / "analytics"

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
]
PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "530661371")


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


def fetch_overview(client, days=28):
    end = date.today()
    start = end - timedelta(days=days)
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        dimensions=[Dimension(name="date")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
            Metric(name="newUsers"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="conversions"),
        ],
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
    )
    return client.run_report(request)


def fetch_by_source(client, days=28):
    end = date.today()
    start = end - timedelta(days=days)
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="conversions"),
            Metric(name="totalRevenue"),
        ],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
    )
    return client.run_report(request)


def fetch_top_pages(client, days=28):
    end = date.today()
    start = end - timedelta(days=days)
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        dimensions=[Dimension(name="pagePath")],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
        ],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
        limit=10,
    )
    return client.run_report(request)


def fetch_by_device(client, days=28):
    end = date.today()
    start = end - timedelta(days=days)
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        dimensions=[Dimension(name="deviceCategory")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="conversions"),
        ],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
    )
    return client.run_report(request)


def format_report(overview, by_source, top_pages, by_device):
    today = date.today().isoformat()

    # Aggregate overview totals
    total_sessions = sum(int(r.metric_values[0].value) for r in overview.rows)
    total_users = sum(int(r.metric_values[1].value) for r in overview.rows)
    total_new_users = sum(int(r.metric_values[2].value) for r in overview.rows)
    total_conversions = sum(int(r.metric_values[5].value) for r in overview.rows)
    avg_bounce = sum(float(r.metric_values[3].value) for r in overview.rows) / len(overview.rows) if overview.rows else 0
    avg_duration = sum(float(r.metric_values[4].value) for r in overview.rows) / len(overview.rows) if overview.rows else 0

    lines = [
        f"# Google Analytics 4 — rhytm.store",
        f"> Generato: {today} | Periodo: ultimi 28 giorni\n",
        "## Riepilogo",
        "| Metrica | Valore |",
        "|---|---|",
        f"| Sessioni totali | {total_sessions} |",
        f"| Utenti totali | {total_users} |",
        f"| Nuovi utenti | {total_new_users} |",
        f"| Conversioni | {total_conversions} |",
        f"| Bounce rate medio | {avg_bounce*100:.1f}% |",
        f"| Durata media sessione | {avg_duration:.0f}s |",
        "",
        "## Sessioni per canale",
        "| Canale | Sessioni | Conversioni | Revenue |",
        "|---|---|---|---|",
    ]
    for row in by_source.rows:
        channel = row.dimension_values[0].value
        sessions = row.metric_values[0].value
        convs = row.metric_values[1].value
        revenue = f"${float(row.metric_values[2].value):.2f}"
        lines.append(f"| {channel} | {sessions} | {convs} | {revenue} |")

    lines += [
        "",
        "## Top pagine",
        "| Pagina | Views | Durata media | Bounce rate |",
        "|---|---|---|---|",
    ]
    for row in top_pages.rows:
        page = row.dimension_values[0].value
        views = row.metric_values[0].value
        duration = f"{float(row.metric_values[1].value):.0f}s"
        bounce = f"{float(row.metric_values[2].value)*100:.1f}%"
        lines.append(f"| {page} | {views} | {duration} | {bounce} |")

    lines += [
        "",
        "## Per dispositivo",
        "| Dispositivo | Sessioni | Conversioni |",
        "|---|---|---|",
    ]
    for row in by_device.rows:
        device = row.dimension_values[0].value
        sessions = row.metric_values[0].value
        convs = row.metric_values[1].value
        lines.append(f"| {device} | {sessions} | {convs} |")

    return "\n".join(lines)


def main():
    print("Autenticazione Google Analytics...")
    creds = get_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)
    print(f"Connesso. Fetching dati per property {PROPERTY_ID}...")

    overview = fetch_overview(client)
    by_source = fetch_by_source(client)
    top_pages = fetch_top_pages(client)
    by_device = fetch_by_device(client)

    report = format_report(overview, by_source, top_pages, by_device)
    output_file = OUTPUT_DIR / f"ga4-{date.today().isoformat()}.md"
    output_file.write_text(report)
    print(f"Report salvato: {output_file}")
    print(report)


if __name__ == "__main__":
    main()
