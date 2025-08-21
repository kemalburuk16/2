# /var/www/instavido/adminpanel/analytics_data.py

try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import RunReportRequest
    from google.oauth2 import service_account
    GOOGLE_ANALYTICS_AVAILABLE = True
except ImportError:
    GOOGLE_ANALYTICS_AVAILABLE = False
    BetaAnalyticsDataClient = None
    RunReportRequest = None
    service_account = None

import os

SERVICE_ACCOUNT_FILE = "/var/www/instavido/anly/webb1-466620-5d22f4311e8f.json"
PROPERTY_ID = "499908879"  # <-- BURAYA GA4 mülk ID'ni yaz (sadece rakam!)

# Initialize Google Analytics client only if available and credentials exist
credentials = None
client = None

if GOOGLE_ANALYTICS_AVAILABLE and os.path.exists(SERVICE_ACCOUNT_FILE):
    try:
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        client = BetaAnalyticsDataClient(credentials=credentials)
    except Exception as e:
        print(f"Warning: Google Analytics client initialization failed: {e}")
        GOOGLE_ANALYTICS_AVAILABLE = False

def get_summary_7days():
    """Son 7 günün temel analytics verileri"""
    if not GOOGLE_ANALYTICS_AVAILABLE or not client:
        # Return mock data when Analytics is not available
        return {
            "active_users": 0,
            "new_users": 0,
            "page_views": 0,
            "sessions": 0,
            "bounce_rate": 0.0,
            "avg_session_duration": 0.0,
            "daily_data": [],
            "error": "Google Analytics not available"
        }
    
    try:
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[{"name": "date"}],
            metrics=[
                {"name": "activeUsers"},
                {"name": "newUsers"},
                {"name": "screenPageViews"}
            ],
            date_ranges=[{"start_date": "7daysAgo", "end_date": "today"}]
        )
        response = client.run_report(request)
        rows = []
        for row in response.rows:
            rows.append({
                "date": row.dimension_values[0].value,
                "active_users": int(row.metric_values[0].value),
                "new_users": int(row.metric_values[1].value),
                "pageviews": int(row.metric_values[2].value)
            })
        return {
            "active_users": sum(r["active_users"] for r in rows),
            "new_users": sum(r["new_users"] for r in rows),
            "page_views": sum(r["pageviews"] for r in rows),
            "daily_data": rows
        }
    except Exception as e:
        print(f"Analytics API error: {e}")
        return {
            "active_users": 0,
            "new_users": 0,
            "page_views": 0,
            "sessions": 0,
            "bounce_rate": 0.0,
            "avg_session_duration": 0.0,
            "daily_data": [],
            "error": f"Analytics API error: {str(e)}"
        }

def get_realtime_users():
    """Anlık aktif kullanıcı sayısı"""
    if not GOOGLE_ANALYTICS_AVAILABLE or not client:
        return 0
    
    try:
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            metrics=[{"name": "activeUsers"}],
            date_ranges=[{"start_date": "today", "end_date": "today"}]
        )
        response = client.run_report(request)
        if response.rows:
            return int(response.rows[0].metric_values[0].value)
        return 0
    except Exception as e:
        print(f"Realtime analytics error: {e}")
        return 0
