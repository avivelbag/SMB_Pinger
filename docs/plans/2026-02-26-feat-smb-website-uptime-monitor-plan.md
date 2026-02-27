---
title: "feat: Santa Barbara Small Business Website Uptime Monitor"
type: feat
status: completed
date: 2026-02-26
deepened: 2026-02-26
origin: docs/brainstorms/2026-02-26-smb-pinger-brainstorm.md
---

# feat: Santa Barbara Small Business Website Uptime Monitor

## Enhancement Summary

**Deepened on:** 2026-02-26
**Research agents used:** Python Reviewer (Kieran), Architecture Strategist, Security Sentinel, Performance Oracle, Simplicity Reviewer, Data Integrity Guardian, Deployment Verifier, Frontend Design, FastAPI+HTMX Research, Google Places API Research

### Key Improvements
1. **Simplified scope:** Defer Yelp + Google Places API to v2 — CSV-only for v1 (YAGNI)
2. **Added `aiosqlite`:** Critical for non-blocking DB access in async FastAPI (all reviewers agreed)
3. **Added `uptime_cache` table:** Dashboard reads from pre-computed cache, not live aggregation (1000x faster)
4. **SSRF protection:** URL validation with private IP blocking — critical since app fetches user-submitted URLs
5. **Right-sized PRAGMAs:** Reduced from 320MB to ~72MB memory footprint for 1GB VPS
6. **Added `jinja2-fragments`:** Render full page or HTMX fragment from same template
7. **HTML/CSS uptime bar:** Lighter than Chart.js for status visualization; Chart.js only for response time
8. **Security hardened:** CSRF tokens, security headers, parameterized SQL mandate, SRI hashes
9. **Concrete deployment specs:** systemd, nginx, backup, firewall, service user all fully specified
10. **Proper Python tooling:** `pydantic-settings`, `StrEnum`, ruff, mypy, comprehensive test strategy

### Scope Change: v1 = CSV-Only Discovery

The simplicity review identified that Yelp + Google Places discovery is premature for 100-500 businesses. You can build a CSV of Santa Barbara businesses by hand in an afternoon. The API clients are moved to "Future Considerations."

---

## Overview

Build a Python-based website uptime monitoring tool that discovers small businesses in Santa Barbara via CSV import, checks their websites every 15 minutes, and displays results on a web dashboard. The tool runs on a VPS and is for personal use initially, with future potential as a monitoring service.

(see brainstorm: docs/brainstorms/2026-02-26-smb-pinger-brainstorm.md)

## Problem Statement / Motivation

There is no easy way to know which small businesses in Santa Barbara have unreliable websites. A monitoring tool creates a dataset of website reliability that can eventually be offered as a service to those businesses.

## Proposed Solution

A single Python application with three components:

1. **Business Import** — Add businesses via CSV upload or admin form
2. **Pinger** — Async HTTP health checker using httpx, scheduled every 15 minutes via APScheduler
3. **Dashboard** — FastAPI + Jinja2 + HTMX + Pico CSS web UI showing current status and uptime history

## Technical Approach

### Architecture

```
┌──────────────────────────────────────────────────────┐
│                VPS (DigitalOcean, 1GB RAM)            │
│                                                       │
│  ┌─────────────┐   ┌──────────────────────────────┐  │
│  │ APScheduler  │──>│  Pinger (httpx async)         │  │
│  │ (every 15m)  │   │  - Semaphore(30) concurrency  │  │
│  │ AsyncIOExec  │   │  - SSRF validation            │  │
│  └─────────────┘   └───────────┬──────────────────┘  │
│                                 │ writes (aiosqlite)   │
│                                 ▼                      │
│                     ┌──────────────────────────────┐  │
│                     │  SQLite (WAL mode)            │  │
│                     │  - businesses                  │  │
│                     │  - ping_results                │  │
│                     │  - uptime_cache (materialized) │  │
│                     └───────────▲──────────────────┘  │
│                                 │ reads (aiosqlite)    │
│  ┌──────────────────────────────┴──────────────────┐  │
│  │  FastAPI + Jinja2 + jinja2-fragments + HTMX     │  │
│  │  - Dashboard (overview, detail, admin)           │  │
│  │  - HTMX polling (60s summary, 120s table)       │  │
│  │  - Chart.js for response time only              │  │
│  │  - HTML/CSS uptime bar                          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  Uvicorn (--host 127.0.0.1 --port 8000, 1 worker)     │
│  Nginx reverse proxy (SSL via Let's Encrypt)            │
└─────────────────────────────────────────────────────────┘
         │
         │  /health (unauthenticated, minimal response)
         ▼
  UptimeRobot free tier
```

### Tech Stack

| Component | Choice | Version | Notes |
|-----------|--------|---------|-------|
| Language | Python | 3.12 (Ubuntu 24.04 system) | Target 3.11 for tooling compat |
| HTTP client | httpx (AsyncClient) | 0.28.x | Shared instance via lifespan |
| Async DB | **aiosqlite** | latest | Non-blocking SQLite access |
| Scheduler | APScheduler (AsyncIOScheduler) | 3.11.x (NOT 4.0) | AsyncIOExecutor configured |
| Web framework | FastAPI + Jinja2 | 0.115.x | |
| Template fragments | **jinja2-fragments** | latest | Block-level rendering for HTMX |
| Config | **pydantic-settings** | 2.x | Typed env var loading |
| ASGI server | Uvicorn | 0.34.x | Single worker, localhost only |
| CSS | Pico CSS v2 (CDN + SRI) | 2.x | Classless, dark mode built-in |
| Interactivity | HTMX (CDN + SRI) | 2.0.x | |
| Charts | Chart.js (CDN, detail page only) | 4.x | Response time chart only |
| Linting | ruff | 0.9.x | `select = ["E","F","I","UP","B","SIM","ASYNC"]` |
| Type checking | mypy --strict | 1.14.x | Mandatory from Phase 1 |
| Dependency mgmt | uv + pyproject.toml | latest | |

### Data Model

```sql
CREATE TABLE businesses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL UNIQUE,
    category TEXT,
    address TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')) CHECK (created_at IS datetime(created_at))
);

CREATE TABLE ping_results (
    id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    checked_at TEXT NOT NULL DEFAULT (datetime('now')) CHECK (checked_at IS datetime(checked_at)),
    cycle_id TEXT NOT NULL,                -- UUID per check cycle, for partial cycle detection
    status_code INTEGER CHECK (status_code BETWEEN 100 AND 599),
    response_time_ms REAL CHECK (response_time_ms >= 0),
    is_up INTEGER NOT NULL CHECK (is_up IN (0, 1)),
    result TEXT NOT NULL CHECK (result IN ('up', 'down', 'timeout', 'dns_error',
                                           'ssl_error', 'redirect_loop', 'challenge_page')),
    error TEXT
);

-- Materialized cache: refreshed at end of each check cycle
CREATE TABLE uptime_cache (
    business_id INTEGER PRIMARY KEY REFERENCES businesses(id),
    current_status TEXT NOT NULL,           -- 'up', 'down'
    uptime_24h REAL,
    uptime_7d REAL,
    uptime_30d REAL,
    last_checked_at TEXT,
    last_response_time_ms REAL,
    computed_at TEXT NOT NULL
);

-- Indexes: covering indexes for dashboard performance
CREATE INDEX idx_ping_business_covering ON ping_results(
    business_id, checked_at DESC, is_up, response_time_ms, status_code, result
);
CREATE INDEX idx_ping_time_business_up ON ping_results(checked_at, business_id, is_up);
CREATE INDEX idx_business_active ON businesses(is_active);

-- Prevent hard deletes — soft-delete only
CREATE TRIGGER prevent_business_delete
BEFORE DELETE ON businesses
BEGIN
    SELECT RAISE(ABORT, 'Hard delete not allowed. Set is_active = 0 instead.');
END;
```

#### Research Insights: Data Model

- **Simplified schema:** Removed `source`, `source_id`, `yelp_url`, `phone`, `city`, `deactivated_at`, `notes` — none are used in v1 (Simplicity Review)
- **CHECK constraints on all enum/boolean columns:** Prevents silent data corruption from typos in application code (Data Integrity Guardian)
- **`cycle_id` column:** Enables detecting and repairing partial check cycles after crashes (Data Integrity Guardian)
- **`uptime_cache` table:** Dashboard reads from this instead of computing aggregates on-the-fly. Reduces dashboard query from scanning 672K rows to reading 500 rows — **1000x faster** (Performance Oracle)
- **Covering indexes:** `idx_ping_business_covering` includes all columns needed for detail page queries, eliminating table lookups (Performance Oracle)
- **Soft-delete trigger:** Prevents accidental data loss from FK constraint violations (Data Integrity Guardian)
- **Removed `final_url` column:** Not displayed anywhere in the dashboard (Simplicity Review)

### Up/Down Classification

Use `StrEnum` in Python for type safety:

```python
from enum import StrEnum

class CheckResult(StrEnum):
    UP = "up"
    DOWN = "down"
    TIMEOUT = "timeout"
    DNS_ERROR = "dns_error"
    SSL_ERROR = "ssl_error"
    REDIRECT_LOOP = "redirect_loop"
    CHALLENGE_PAGE = "challenge_page"
```

| Condition | Result | Counts as UP? |
|-----------|--------|---------------|
| HTTP 2xx (after following redirects, max 5 hops) | `up` | Yes |
| HTTP 403 with CloudFlare/CDN challenge signature | `challenge_page` | Yes |
| Connection timeout (>15s) | `timeout` | No |
| DNS resolution failure | `dns_error` | No |
| SSL certificate error | `ssl_error` | No |
| Connection refused | `down` | No |
| HTTP 4xx (other) | `down` | No |
| HTTP 5xx | `down` | No |
| Too many redirects (>5 hops) | `redirect_loop` | No |

**Uptime formula:** `uptime_pct = (UP checks / total checks) * 100` over a given window (24h, 7d, 30d). Pre-computed in `uptime_cache` every 15 minutes.

### SSRF Protection (Critical)

Since the app fetches user-submitted URLs, it must validate them to prevent Server-Side Request Forgery:

```python
import ipaddress, socket, urllib.parse

BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Cloud metadata endpoint
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fd00::/8"),
]

def validate_url_safe(url: str) -> bool:
    """Reject URLs targeting internal/private IPs."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    try:
        for _, _, _, _, sockaddr in socket.getaddrinfo(parsed.hostname, None):
            if any(ipaddress.ip_address(sockaddr[0]) in net for net in BLOCKED_NETWORKS):
                return False
    except socket.gaierror:
        return False
    return True
```

- Validate at **ingestion time** (CSV import, admin form) AND at **check time** (DNS can change)
- Block `169.254.169.254` (cloud metadata endpoint) explicitly
- Only allow `http://` and `https://` schemes

### URL Normalization

Applied at ingestion time to prevent duplicates:
1. Lowercase scheme and hostname (preserve path case per RFC 3986)
2. Normalize scheme to `https://` (most small business sites redirect to HTTPS)
3. Strip trailing slash from path
4. Strip `www.` prefix
5. Remove default ports (`:80`, `:443`)
6. Remove fragment (`#...`)
7. Strip all query parameters (small business homepages don't use meaningful query params)
8. Store normalized form in `normalized_url` with UNIQUE constraint

**On UNIQUE violation during import:** Use `INSERT OR IGNORE` for idempotent imports. Log skipped rows for admin review rather than silently discarding.

### Business Discovery Strategy (v1: CSV-Only)

**v1:** Manual CSV import only. Build a list of 100-500 Santa Barbara businesses by hand using Yelp's website, Google search, Chamber of Commerce directories, etc. This takes an afternoon and requires zero API dependencies.

**CSV format:** `name,url` (required), `category,address` (optional). UTF-8 encoded. Max 10,000 rows per upload, max 5MB file size.

**v2 (deferred):** Yelp Fusion API for discovery + Google Places API (New) for website URL resolution. Research findings documented in `docs/google_places_api_research.md`.

### Configuration

Use `pydantic-settings` (not plain dataclass):

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Database
    db_path: Path = Path("data/smb_pinger.db")

    # Pinger
    check_interval_minutes: int = 15
    concurrency_limit: int = 30
    timeout_seconds: int = 15
    max_redirects: int = 5
    user_agent: str = "SMBPinger/1.0 (+https://your-domain.com; uptime-monitor)"

    # Auth
    admin_password_hash: str  # bcrypt hash, no default — forces explicit config

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    model_config = {"env_prefix": "SMB_PINGER_", "env_file": ".env"}
```

### SQLite Performance Strategy

**PRAGMAs (auto-scaled to VPS RAM):**

```python
import os

total_mem_mb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024)

if total_mem_mb <= 1024:   # 1 GB VPS
    CACHE_SIZE = -8000     # 8MB
    MMAP_SIZE = 67108864   # 64MB
else:
    CACHE_SIZE = -16000    # 16MB
    MMAP_SIZE = 134217728  # 128MB

# Set on every connection
PRAGMA journal_mode = WAL
PRAGMA synchronous = NORMAL
PRAGMA busy_timeout = 5000
PRAGMA cache_size = {CACHE_SIZE}
PRAGMA mmap_size = {MMAP_SIZE}
PRAGMA foreign_keys = ON
PRAGMA temp_store = MEMORY
```

#### Research Insights: Performance

- **Original PRAGMAs (64MB cache + 256MB mmap = 320MB) would OOM on a 512MB VPS.** Reduced to 8MB cache + 64MB mmap = ~72MB. Query performance impact <5%, fully offset by covering indexes. (Performance Oracle)
- **`uptime_cache` eliminates the expensive dashboard aggregation query.** Without cache: 200ms-2s per dashboard load after 30 days. With cache: <5ms always. (Performance Oracle)
- **HTMX polling intervals increased:** 60s for summary, 120s for table (data only changes every 15 min). Add ETag-style `since` parameter to skip re-rendering when data unchanged. (Performance Oracle)
- **`PRAGMA temp_store = MEMORY`:** Avoids writing temp sort/group results to disk. (Performance Oracle)
- **`ANALYZE` weekly** via scheduled job to keep query planner statistics fresh. (Data Integrity Guardian)
- **Data aggregation trigger:** When `ping_results` exceeds 10M rows, implement hourly/daily rollup. (Performance Oracle + Data Integrity Guardian)

### Dashboard Views

**A. Overview page (`/`)**
- Summary cards in `.grid` (4 Pico CSS `<article>` elements): total, UP, DOWN, degraded
- "Currently Down" alert section (red-bordered card, top of page)
- Full business table in `<figure>` (horizontal scroll on mobile)
- Sortable columns via HTMX `hx-get` with sort/order params
- Active search with `hx-trigger="input changed delay:300ms"`
- Status dropdown filter
- Auto-refresh: 60s summary, 120s table, paused on hidden tabs via Visibility API

**B. Business detail page (`/business/{id}`)**
- Business metadata card
- Current status with last check timestamp
- **HTML/CSS uptime bar** (colored flex segments per hour — green/red/yellow, no Chart.js)
- Response time chart (Chart.js line chart, loaded conditionally only on this page)
- Time range selector: 24h/7d/30d (cap "all" at 365 days)
- Server-side downsampling: raw data for 24h/7d, hourly averages for 30d
- Recent check log table (last 50 checks)

**C. Admin page (`/admin`)**
- Add/edit/deactivate businesses (soft-delete only)
- CSV import form (file upload, max 5MB)
- Trigger manual re-check for a single business

**D. Health endpoint (`/health`)**
- Minimal response: `{"status": "ok"}` (200) or `{"status": "degraded"}` (503)
- Returns 503 if last check cycle is older than 30 minutes
- Unauthenticated (external monitors need access)
- No database state, site count, or timestamps exposed (reduces information disclosure)

#### Research Insights: Dashboard UI

- **Use `jinja2-fragments`** with `Jinja2Blocks` for block-level rendering — serve full page or HTMX fragment from same template, eliminating separate partial files for blocks. (FastAPI+HTMX Research)
- **HTML/CSS uptime bar instead of Chart.js:** A flex-based row of colored segments is lighter, crisper, dark-mode-aware, and requires no canvas. Chart.js only for response time line chart. (Frontend Design)
- **Status indicators must be accessible (WCAG 2.1 AA):** Color + icon (checkmark/cross/warning) + text label ("Up"/"Down") + `aria-label` + `role="status"`. Never color-only. (Frontend Design)
- **Pico CSS `<figure>` wrapping `<table>`** gives automatic horizontal scroll on mobile — zero CSS work. (Frontend Design)
- **Dark mode:** Pico CSS v2 `data-theme` attribute + `localStorage` toggle + early `<script>` to prevent flash. (Frontend Design)
- **HTMX + Chart.js lifecycle:** Set `htmx.config.allowScriptTags = true` via `<meta name="htmx-config">` to allow chart initialization in swapped content. Destroy chart instance before re-init. (Frontend Design)
- **`hx-swap="outerHTML"`** on polling containers to prevent stale `hx-` attributes. (FastAPI+HTMX Research)
- **OOB swaps:** Use `hx-swap-oob="true"` to update summary counts alongside table content from a single response. (FastAPI+HTMX Research)

### Security

| Concern | Mitigation |
|---------|-----------|
| **SSRF** | Validate URLs at ingestion + check time; block private IPs, metadata endpoint |
| **SQL injection** | All queries use `?` parameterized placeholders. Never f-strings in SQL. |
| **CSRF** | CSRF tokens on all POST endpoints via `starlette-csrf` or custom middleware. HTMX sends token via `hx-headers` from `<meta>` tag. |
| **XSS** | Jinja2 autoescape (default for .html). Validate URL schemes before rendering in `href`. Use `{{ data \| tojson }}` for JS contexts. |
| **Auth** | HTTPBasic via `Depends()` (not middleware). Password stored as bcrypt hash. HTTPS enforced via Nginx redirect + HSTS header. |
| **Security headers** | CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy, HSTS |
| **CDN integrity** | SRI hashes on all `<script>` and `<link>` CDN tags. Pin exact versions. |
| **CSV upload** | Max 5MB, max 10K rows, UTF-8 only. Never use client filename. Strip formula-injection chars (`=`, `+`, `-`, `@`). |
| **API keys** | `.env` with `chmod 600`, owned by service user. Google key restricted to Places API + VPS IP. Pre-commit hook via `gitleaks`. |
| **Rate limiting** | Nginx `limit_req_zone` for login (5r/m) and general (30r/s). App-level auth throttling after 5 failed attempts. |

### Implementation Phases

#### Phase 1: Pinger + CSV Import (Core functionality)

Build the complete backend: project scaffolding, database, config, CSV import, pinger, scheduler, and health endpoint. At the end of this phase, you can load a CSV and it starts pinging.

**Deliverables:**
- Project scaffolding: `pyproject.toml` (with ruff, mypy, pytest config), `.gitignore`, `.env.example`
- SQLite database setup with `aiosqlite`, PRAGMA configuration, schema initialization
- `pydantic-settings` configuration with all tunable parameters
- URL normalization with SSRF validation
- CSV importer: parse, validate, normalize, UPSERT with dedup
- Async HTTP checker: httpx with `Semaphore(30)`, `asyncio.gather`, classification
- CloudFlare challenge detection (`cf-ray` header)
- APScheduler integration (15-min interval, `AsyncIOExecutor`, `max_instances=1`)
- Batch insert via `executemany` in single transaction, then refresh `uptime_cache`
- Health endpoint (minimal JSON response)
- Structured logging via `logging.config.dictConfig`
- `StrEnum` for check results, frozen dataclasses for DB rows, Pydantic models for input validation

**Files to create:**
```
pyproject.toml
.gitignore
.env.example
src/smb_pinger/
    __init__.py
    config.py              # pydantic-settings BaseSettings
    database.py            # aiosqlite connection manager, PRAGMAs, schema init
    models.py              # CheckResult StrEnum, Business/PingResult dataclasses
    schemas.py             # Pydantic input validation (BusinessCreate, CSVRow)
    url_utils.py           # URL normalization + SSRF validation
    csv_importer.py        # parse CSV, validate, normalize, UPSERT
    checker.py             # check_site() — HTTP transport + classification
    check_cycle.py         # check_all_sites(), store_results(), refresh_cache()
    scheduler.py           # APScheduler setup, generic callable interface
    main.py                # FastAPI app, lifespan (httpx client + scheduler), /health
tests/
    conftest.py            # Shared fixtures: in-memory DB, test settings, httpx mock
    test_url_utils.py
    test_csv_importer.py
    test_checker.py        # Parametrized tests for all classification cases
    test_check_cycle.py
    test_config.py
    test_database.py
```

**Key patterns:**
- httpx `AsyncClient` created once in FastAPI lifespan, stored in `app.state`
- APScheduler accepts any `async def run() -> None` callable (generic, testable)
- `checker.py` separated from `check_cycle.py` (transport/classification vs orchestration/persistence)
- All DB access through `aiosqlite` with `fetchall()` (never row-by-row iteration)
- Database connection management: context manager yielding connection, with PRAGMAs applied

**Success criteria:**
- `uv run uvicorn smb_pinger.main:app` starts and serves `/health`
- CSV import loads businesses, scheduler pings them every 15 minutes
- `uptime_cache` is refreshed after each cycle
- All tests pass, mypy --strict passes, ruff passes

#### Phase 2: Dashboard (Web UI)

Web UI to view results. Admin page for CSV upload and business management. At the end of this phase, the tool is feature-complete for personal use.

**Deliverables:**
- Overview page: summary cards, "currently down" alert, business table with sort/search/filter
- Business detail page: metadata, HTML/CSS uptime bar, Chart.js response time chart, check log
- Admin page: add/edit/deactivate, CSV upload, manual re-check
- HTMX auto-refresh (60s/120s) with Visibility API pause
- HTTPBasic auth via `Depends()` (password hash from env)
- CSRF tokens on all POST endpoints
- Security headers middleware
- Dark mode toggle with localStorage persistence

**Files to create:**
```
src/smb_pinger/
    routes/
        __init__.py
        dashboard.py       # GET /, GET /business/{id}, HTMX partials co-located
        admin.py           # GET/POST /admin, POST /admin/import, POST /admin/check/{id}
    queries.py             # SQL queries for dashboard (reads from uptime_cache)
    security.py            # HTTPBasic dependency, CSRF, security headers middleware
templates/
    base.html              # Pico CSS + HTMX CDN (with SRI), nav, dark mode toggle
    dashboard.html         # jinja2-fragments blocks for overview + partials
    business_detail.html   # Metadata, uptime bar, chart, check log
    admin.html             # Forms, CSV upload
    components/
        status_badge.html  # Jinja2 macro: color + icon + text + aria
        uptime_bar.html    # HTML/CSS flex bar
static/
    app.css                # Status indicator styles, uptime bar, dark mode adjustments
    app.js                 # Chart.js init, theme toggle, HTMX afterSettle handler, polling pause
tests/
    test_routes/
        test_dashboard.py  # TestClient tests, HTMX partial responses
        test_admin.py      # Auth-protected routes, CSV upload
        test_health.py     # 200 vs 503 responses
    test_queries.py
```

**Success criteria:**
- Dashboard loads in <1s with 500 businesses (reads from `uptime_cache`)
- Currently-down sites prominently displayed
- Table sortable/filterable via HTMX without full page reload
- Charts render correctly, destroyed/recreated on HTMX swap
- Dashboard password-protected, CSRF tokens on all forms
- Dark mode works, respects system preference

#### Phase 3: Deployment (VPS)

**VPS spec:** DigitalOcean Basic Regular, 1 vCPU / 1 GB RAM / 25 GB SSD, Ubuntu 24.04 LTS, SFO3 region (~$6/mo).

**Deliverables:**
- `setup.sh`: apt packages (nginx, certbot, sqlite3, ufw, fail2ban), uv install, `smbpinger` service user, directory structure, firewall
- `smb-pinger.service`: systemd unit with security hardening (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`), `Restart=on-failure`, `RestartSec=5`
- `nginx.conf`: HTTP→HTTPS redirect, reverse proxy to `127.0.0.1:8000`, static file serving, security headers, SSL via certbot
- `backup.sh`: WAL checkpoint → `sqlite3 .backup` → gzip → integrity check → 7-day rotation. Daily cron at 3 AM.
- UptimeRobot: HTTPS monitor on `/health` + keyword monitor on `/` for "Up" string

**Production paths:**
- Code: `/opt/smb-pinger`
- Database: `/var/lib/smb-pinger/smb_pinger.db`
- Backups: `/var/lib/smb-pinger/backups/`
- Env: `/opt/smb-pinger/.env` (chmod 600, owned by `smbpinger`)
- Logs: journald (`journalctl -u smb-pinger`)

**Firewall (ufw):** Allow 22/tcp (SSH), 80/tcp (HTTP redirect), 443/tcp (HTTPS). Deny all other incoming.

**Deployment procedure:**
1. Wait for check cycle to complete (check logs)
2. `cd /opt/smb-pinger && git pull origin main && uv sync`
3. `systemctl restart smb-pinger`
4. Verify: `systemctl status smb-pinger` + `curl -s http://localhost:8000/health`

**Domain name required** for Let's Encrypt SSL. Cannot use bare IP with certbot.

**Files to create:**
```
deploy/
    setup.sh               # VPS initial provisioning
    smb-pinger.service     # systemd unit with security hardening
    nginx.conf             # Reverse proxy + SSL + static files
    backup.sh              # SQLite backup with WAL checkpoint + rotation
```

**Success criteria:**
- App runs as `smbpinger` user, restarts on crash
- Dashboard accessible via HTTPS, HTTP redirects to HTTPS
- Port 8000 not exposed externally
- UptimeRobot alerts if `/health` returns 503
- Daily backups verified with integrity check

## `pyproject.toml`

```toml
[project]
name = "smb-pinger"
version = "0.1.0"
description = "Website uptime monitor for Santa Barbara small businesses"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115,<1.0",
    "uvicorn[standard]>=0.34,<1.0",
    "httpx>=0.28,<1.0",
    "aiosqlite>=0.20,<1.0",
    "apscheduler>=3.10,<4.0",
    "jinja2>=3.1,<4.0",
    "jinja2-fragments>=1.0",
    "python-multipart>=0.0.9",
    "pydantic-settings>=2.0,<3.0",
    "passlib[bcrypt]>=1.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.22",
    "ruff>=0.9",
    "mypy>=1.14",
    "coverage>=7.0",
    "gitleaks",
]

[tool.ruff]
target-version = "py311"
line-length = 99

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "ASYNC"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

## Project Structure

```
SMB_Pinger/
├── pyproject.toml
├── .gitignore
├── .env.example
├── docs/
│   ├── brainstorms/
│   │   └── 2026-02-26-smb-pinger-brainstorm.md
│   └── plans/
│       └── 2026-02-26-feat-smb-website-uptime-monitor-plan.md
├── src/
│   └── smb_pinger/
│       ├── __init__.py
│       ├── main.py                # FastAPI app, lifespan, /health
│       ├── config.py              # pydantic-settings
│       ├── database.py            # aiosqlite manager, PRAGMAs, schema
│       ├── models.py              # CheckResult StrEnum, dataclasses
│       ├── schemas.py             # Pydantic input validation
│       ├── url_utils.py           # URL normalization + SSRF validation
│       ├── csv_importer.py        # CSV parse, validate, UPSERT
│       ├── checker.py             # HTTP transport + classification
│       ├── check_cycle.py         # Orchestration + persistence + cache refresh
│       ├── scheduler.py           # APScheduler generic setup
│       ├── queries.py             # SQL reads (dashboard, detail, admin)
│       ├── security.py            # HTTPBasic, CSRF, security headers
│       └── routes/
│           ├── __init__.py
│           ├── dashboard.py       # GET /, GET /business/{id}, HTMX partials
│           └── admin.py           # Admin CRUD, CSV upload, manual check
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── business_detail.html
│   ├── admin.html
│   └── components/
│       ├── status_badge.html
│       └── uptime_bar.html
├── static/
│   ├── app.css
│   └── app.js
├── deploy/
│   ├── setup.sh
│   ├── smb-pinger.service
│   ├── nginx.conf
│   └── backup.sh
└── tests/
    ├── conftest.py
    ├── test_url_utils.py
    ├── test_csv_importer.py
    ├── test_checker.py
    ├── test_check_cycle.py
    ├── test_config.py
    ├── test_database.py
    ├── test_queries.py
    └── test_routes/
        ├── test_dashboard.py
        ├── test_admin.py
        └── test_health.py
```

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SSRF via user-submitted URLs | Medium | Critical | Private IP blocking, scheme validation, DNS re-check |
| CloudFlare blocking causes false "down" | Medium | High | Detect `cf-ray` header, classify as `challenge_page` |
| SQLite performance after 1+ year (17.5M rows) | Low | Medium | Covering indexes, `uptime_cache`, aggregation at 10M rows |
| VPS goes down silently | Medium | High | UptimeRobot on `/health` + keyword monitor on `/` |
| Event loop blocked by sync DB | High | High | `aiosqlite` for all DB access (non-negotiable) |
| OOM on 1GB VPS | Low | High | Right-sized PRAGMAs (72MB not 320MB), monitor with `journalctl -k` |
| Brute-force on Basic Auth | Medium | Medium | Nginx rate limiting (5r/m on login), fail2ban |
| Target sites block our IP | Low | Low | Polite User-Agent, 1 req/site/15min |
| CSV injection / malicious upload | Low | Medium | Size limits, row limits, formula char stripping, UTF-8 only |

## Future Considerations

- **Yelp + Google Places discovery (v2):** Yelp Fusion API for business metadata, Google Places API (New) Text Search for website URLs. Research in `docs/google_places_api_research.md`. Note: Google ToS prohibits caching `websiteUri` — only `place_id` can be stored long-term.
- **Alerting (v2):** Email/SMS notifications when a site goes down
- **Data aggregation:** Roll up raw checks to hourly/daily summaries when >10M rows
- **Session-based auth:** Replace HTTPBasic with signed cookies for better security
- **Public status pages:** Per-business public status pages for customers
- **Multi-city expansion:** Monitor businesses in other cities
- **Customer portal:** Businesses log in to see their own uptime data
- **SSL monitoring:** Check certificate expiry dates

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-02-26-smb-pinger-brainstorm.md](docs/brainstorms/2026-02-26-smb-pinger-brainstorm.md) — Key decisions carried forward: Python + SQLite + FastAPI stack, manual CSV import, basic HTTP checks every 15 min, VPS hosting, dashboard-only (no alerts v1), indefinite data retention.

### External References

- [httpx AsyncClient docs](https://www.python-httpx.org/async/)
- [aiosqlite docs](https://github.com/omnilib/aiosqlite)
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- [FastAPI Templates](https://fastapi.tiangolo.com/advanced/templates/)
- [FastAPI Dependencies with Yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
- [jinja2-fragments](https://github.com/sponsfreixes/jinja2-fragments)
- [SQLite WAL mode](https://sqlite.org/wal.html)
- [SQLite Performance Tuning](https://phiresky.github.io/blog/2020/sqlite-performance-tuning/)
- [HTMX docs](https://htmx.org/docs/)
- [HTMX hx-trigger](https://htmx.org/attributes/hx-trigger/)
- [Pico CSS docs](https://picocss.com/docs)
- [Chart.js Time Series](https://www.chartjs.org/docs/latest/axes/cartesian/timeseries.html)
- [Google Places API (New) Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search)
- [pydantic-settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

### Review Agent Reports (full transcripts available)

- Python Review: `pydantic-settings`, `StrEnum`, `schemas.py`, testing strategy, `python-multipart`
- Architecture Review: `aiosqlite` (critical), repository pattern, domain-oriented structure
- Security Review: SSRF (critical), CSRF, parameterized SQL, security headers, SRI hashes
- Performance Review: `uptime_cache` (critical), right-sized PRAGMAs, covering indexes, chart downsampling
- Simplicity Review: CSV-only v1, defer API clients, 3 phases not 5, HTML uptime bar
- Data Integrity Review: CHECK constraints, `cycle_id`, soft-delete trigger, `sqlite3 .backup` mandate
- Deployment Review: droplet spec, service user, firewall, systemd hardening, concrete configs
- Frontend Design: Pico CSS patterns, status badges with a11y, dark mode, HTMX+Chart.js lifecycle
- FastAPI+HTMX Research: `jinja2-fragments`, `aiosqlite` with `fetchall()`, dependency injection
- Google Places API Research: Use New API, Text Search endpoint, 1K free/month, `websiteUri` field
