import logging

import httpx
from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from smb_pinger.check_cycle import refresh_uptime_cache
from smb_pinger.checker import check_site
from smb_pinger.csv_importer import import_csv
from smb_pinger.database import get_db
from smb_pinger.queries import get_all_businesses
from smb_pinger.schemas import BusinessCreate
from smb_pinger.security import generate_csrf_token, verify_admin
from smb_pinger.url_utils import validate_url_safe

logger = logging.getLogger(__name__)


def create_admin_router(password_hash: str) -> APIRouter:
    """Create admin router with auth dependency bound to the password hash."""
    router = APIRouter(prefix="/admin", dependencies=[Depends(verify_admin(password_hash))])

    @router.get("", response_class=HTMLResponse)
    async def admin_page(request: Request) -> HTMLResponse:
        settings = request.app.state.settings
        templates = request.app.state.templates

        async with get_db(settings.db_path) as db:
            businesses = await get_all_businesses(db)

        return templates.TemplateResponse(request, "admin.html", {
            "businesses": businesses,
            "csrf_token": generate_csrf_token(),
            "message": request.query_params.get("message", ""),
            "message_type": request.query_params.get("type", "success"),
        })

    @router.post("/import")
    async def import_businesses(request: Request, file: UploadFile) -> RedirectResponse:
        settings = request.app.state.settings

        if not file.filename or not file.filename.endswith(".csv"):
            return RedirectResponse(
                "/admin?message=Please+upload+a+CSV+file&type=error",
                status_code=303,
            )

        content = await file.read()
        async with get_db(settings.db_path) as db:
            result = await import_csv(content, db)

        errors_msg = ""
        if result.errors:
            errors_msg = f".+Errors:+{',+'.join(result.errors[:5])}"

        msg = f"Imported+{result.imported},+skipped+{result.skipped}{errors_msg}"
        return RedirectResponse(f"/admin?message={msg}", status_code=303)

    @router.post("/business")
    async def add_business(request: Request) -> RedirectResponse:
        settings = request.app.state.settings
        form = await request.form()

        name = str(form.get("name", "")).strip()
        url = str(form.get("url", "")).strip()
        category = str(form.get("category", "")).strip() or None
        address = str(form.get("address", "")).strip() or None

        try:
            biz = BusinessCreate(name=name, url=url, category=category, address=address)
        except Exception as exc:
            return RedirectResponse(
                f"/admin?message=Invalid+input:+{exc}&type=error",
                status_code=303,
            )

        if not validate_url_safe(biz.url):
            return RedirectResponse(
                "/admin?message=URL+failed+safety+check&type=error",
                status_code=303,
            )

        async with get_db(settings.db_path) as db:
            await db.execute(
                """INSERT OR IGNORE INTO businesses (name, url, normalized_url, category, address)
                   VALUES (?, ?, ?, ?, ?)""",
                (biz.name, biz.url, biz.normalized_url, biz.category, biz.address),
            )
            await db.commit()

        return RedirectResponse(
            f"/admin?message=Added+{name}", status_code=303
        )

    @router.post("/business/{business_id}/deactivate")
    async def deactivate_business(
        request: Request, business_id: int
    ) -> RedirectResponse:
        settings = request.app.state.settings
        async with get_db(settings.db_path) as db:
            await db.execute(
                "UPDATE businesses SET is_active = 0 WHERE id = ?",
                (business_id,),
            )
            await db.commit()
        return RedirectResponse("/admin?message=Business+deactivated", status_code=303)

    @router.post("/business/{business_id}/activate")
    async def activate_business(
        request: Request, business_id: int
    ) -> RedirectResponse:
        settings = request.app.state.settings
        async with get_db(settings.db_path) as db:
            await db.execute(
                "UPDATE businesses SET is_active = 1 WHERE id = ?",
                (business_id,),
            )
            await db.commit()
        return RedirectResponse("/admin?message=Business+activated", status_code=303)

    @router.post("/check/{business_id}")
    async def manual_check(
        request: Request, business_id: int
    ) -> RedirectResponse:
        """Trigger a manual re-check for a single business."""
        settings = request.app.state.settings
        client: httpx.AsyncClient = request.app.state.http_client

        async with get_db(settings.db_path) as db:
            cursor = await db.execute(
                "SELECT url FROM businesses WHERE id = ? AND is_active = 1",
                (business_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return RedirectResponse(
                    "/admin?message=Business+not+found&type=error",
                    status_code=303,
                )

            outcome = await check_site(row["url"], client)

            await db.execute(
                """INSERT INTO ping_results
                   (business_id, cycle_id, status_code, response_time_ms, is_up, result, error)
                   VALUES (?, 'manual', ?, ?, ?, ?, ?)""",
                (
                    business_id,
                    outcome.status_code,
                    outcome.response_time_ms,
                    1 if outcome.result.is_up else 0,
                    outcome.result.value,
                    outcome.error,
                ),
            )
            await db.commit()
            await refresh_uptime_cache(db)

        return RedirectResponse(
            f"/admin?message=Check+complete:+{outcome.result.value}",
            status_code=303,
        )

    return router
