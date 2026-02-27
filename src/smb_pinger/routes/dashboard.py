from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from smb_pinger.database import get_db
from smb_pinger.queries import (
    get_business_detail,
    get_businesses_with_status,
    get_dashboard_summary,
    get_down_businesses,
    get_recent_checks,
    get_response_time_data,
    get_uptime_bar_data,
)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    sort: str = "name",
    order: str = "asc",
    search: str = "",
    status: str = "",
    partial: str = "",
) -> HTMLResponse:
    """Main dashboard page with optional HTMX partial rendering."""
    settings = request.app.state.settings
    templates = request.app.state.templates

    async with get_db(settings.db_path) as db:
        summary = await get_dashboard_summary(db)
        businesses = await get_businesses_with_status(
            db, sort_by=sort, sort_order=order, search=search, status_filter=status,
        )
        down_businesses = await get_down_businesses(db)

    context = {
        "summary": summary,
        "businesses": businesses,
        "down_businesses": down_businesses,
        "sort_by": sort,
        "sort_order": order,
        "search": search,
        "status_filter": status,
    }

    if partial == "summary":
        return templates.TemplateResponse(
            request, "dashboard.html", context, block_name="summary"
        )
    if partial == "table":
        return templates.TemplateResponse(
            request, "dashboard.html", context, block_name="business_table"
        )

    return templates.TemplateResponse(request, "dashboard.html", context)


@router.get("/business/{business_id}", response_class=HTMLResponse)
async def business_detail(
    request: Request,
    business_id: int,
    hours: int = 24,
) -> HTMLResponse:
    """Business detail page with uptime bar, chart, and check log."""
    settings = request.app.state.settings
    templates = request.app.state.templates

    # Cap hours to valid range
    if hours not in (24, 168, 720):
        hours = 24

    async with get_db(settings.db_path) as db:
        business = await get_business_detail(db, business_id)
        if not business:
            return HTMLResponse("Business not found", status_code=404)
        recent_checks = await get_recent_checks(db, business_id)
        uptime_data = await get_uptime_bar_data(db, business_id, hours=hours)
        response_time_data = await get_response_time_data(
            db, business_id, hours=hours
        )

    return templates.TemplateResponse(request, "business_detail.html", {
        "business": business,
        "recent_checks": recent_checks,
        "uptime_data": uptime_data,
        "response_time_data": response_time_data,
        "hours": hours,
    })
