"""
NiceGUI web interface (replaces Streamlit).

Run:  python nicegui_app.py
Docs: https://nicegui.io/documentation
"""
import os

from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from nicegui import app, ui

from src.auth_password import get_expected_password
from ui.nicegui_account import build_account_page
from ui.nicegui_agent import build_agent_page
from ui.nicegui_chart import build_chart_page
from ui.nicegui_option_chains import build_option_trade_page

load_dotenv()
load_dotenv("src/.env", override=False)  # also pick up GEMINI_API_KEY etc. from src/.env


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools_wellknown():
    """Chrome DevTools requests this URL; returning empty JSON avoids 404 warnings in logs."""
    return JSONResponse({})


_PUBLIC_PATHS = frozenset(
    {
        "/login",
        "/favicon.ico",
    }
)


@app.add_middleware
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/_nicegui") or path.startswith("/static"):
            return await call_next(request)
        if path.startswith("/.well-known/"):
            return await call_next(request)
        if path in _PUBLIC_PATHS:
            return await call_next(request)
        if not app.storage.user.get("authenticated", False):
            dest = f"/login?redirect_to={path}"
            return RedirectResponse(dest, status_code=302)
        return await call_next(request)


def _app_layout(inner):
    with ui.header():
        ui.label("Schwab API").classes("text-h6")
    with ui.left_drawer(value=True):
        ui.link("Account", "/account").classes("block p-2")
        ui.link("Option trade", "/options").classes("block p-2")
        ui.link("Chart", "/chart").classes("block p-2")
        ui.link("AI Agent", "/agent").classes("block p-2")

        def logout():
            app.storage.user.clear()
            ui.navigate.to("/login")

        ui.button("Log out", on_click=logout, icon="logout").classes("mt-4")
    with ui.column().classes("p-4 w-full"):
        inner()


@ui.page("/login")
def login_page(redirect_to: str = "/account"):
    expected = get_expected_password()

    async def try_login():
        if not expected:
            ui.notify(
                "Set APP_PASSWORD in .env (project root or src/.env)",
                color="negative",
            )
            return
        from hmac import compare_digest

        if not compare_digest(pw.value or "", expected):
            ui.notify("Wrong password", color="negative")
            return
        app.storage.user["authenticated"] = True
        ui.navigate.to(redirect_to or "/account")

    if app.storage.user.get("authenticated"):
        ui.navigate.to(redirect_to or "/account")
        return


    with ui.card().classes("absolute-center p-8"):
        ui.label("Log in").classes("text-h5")
        if not expected:
            ui.label(
                "No password configured. Set APP_PASSWORD in .env (project root or src/.env)."
            ).classes("text-warning")
        pw = ui.input("Password", password=True, password_toggle_button=True)
        pw.on("keydown.enter", try_login)
        ui.button("Log in", on_click=try_login)


@ui.page("/")
def root_page():
    ui.navigate.to("/account")


@ui.page("/account")
def account_page():
    _app_layout(build_account_page)


@ui.page("/options")
def options_page():
    option_state = {}
    _app_layout(lambda: build_option_trade_page(option_state))


@ui.page("/chart")
def chart_page():
    _app_layout(build_chart_page)


@ui.page("/agent")
def agent_page():
    _app_layout(build_agent_page)


if __name__ in {"__main__", "__mp_main__"}:
    storage_secret = os.getenv("NICEGUI_STORAGE_SECRET", "change-me-in-production")
    ui.run(
        title="Schwab AI Trader",
        storage_secret=storage_secret,
        port=int(os.getenv("NICEGUI_PORT", "8080")),
    )
