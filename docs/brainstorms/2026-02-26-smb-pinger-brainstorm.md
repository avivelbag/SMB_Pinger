# SMB Pinger — Santa Barbara Small Business Website Monitor

**Date:** 2026-02-26
**Status:** Brainstorm

## What We're Building

A website uptime monitoring tool focused on small businesses in Santa Barbara. The system will:

1. **Discover businesses** — Find local small businesses and their websites via manual CSV import and the Yelp Fusion API
2. **Ping their websites** — Perform basic HTTP checks (up/down status via HTTP response codes) every 15-30 minutes
3. **Dashboard** — A web-based dashboard showing which sites are currently down, uptime history, and business details

The long-term vision is to offer this as a monitoring service to local businesses, but the immediate goal is to build the tool for personal use first and figure out monetization later.

## Why This Approach

- **Manual + Yelp for discovery:** Manual CSV import gets us running immediately with zero dependencies. Yelp Fusion API adds free, scalable discovery (5,000 API calls/day). Google Places API can be added later if better coverage is needed.
- **Basic HTTP checks:** Simple up/down checks are sufficient to start. No need for SSL monitoring, performance scoring, or content verification yet — keep it simple.
- **15-30 minute intervals:** Good balance between freshness and resource usage. For hundreds of sites, this is lightweight enough to run on a single machine.
- **Python + web dashboard:** Python is well-suited for the scheduler/pinger backend. A Flask or FastAPI web dashboard is accessible from anywhere and can eventually be shared with customers.
- **VPS hosting:** Always-on server ensures continuous monitoring and an internet-accessible dashboard.
- **Keep all data:** Full historical record supports trend analysis and future business insights.

## Key Decisions

1. **Tech stack:** Python backend, SQLite for storage, Flask or FastAPI for the web dashboard
2. **Business discovery:** Manual CSV import + Yelp Fusion API
3. **Check type:** Basic HTTP status checks (GET request, check for 200 OK)
4. **Check frequency:** Every 15-30 minutes
5. **Dashboard:** Web-based (browser UI), personal use initially
6. **Monetization:** Deferred — build the tool first
7. **Hosting:** VPS (DigitalOcean or similar, ~$5-10/mo), scheduler runs as a background service
8. **Alerting:** Dashboard only — no email/SMS/Slack notifications in v1
9. **Scale:** 100-500 businesses
10. **Data retention:** Indefinite — keep all ping history
