"""
NiceGUI web interface (replaces Streamlit).

Run:  python nicegui_app.py
Docs: https://nicegui.io/documentation
"""
import os
from datetime import datetime

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

ui.add_head_html(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700&family=Manrope:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
      :root {
        --bg-1: #0b1320;
        --bg-2: #111f35;
        --ink: #d7e0ef;
        --ink-soft: #95a3bc;
        --panel: rgba(16, 29, 50, 0.72);
        --accent: #f4c869;
        --accent-soft: #f4c86922;
      }
      body, .q-layout, .q-page-container, .q-page {
        background:
          radial-gradient(1300px 600px at -20% -20%, #1d3359 0%, transparent 55%),
          radial-gradient(1200px 700px at 120% 0%, #2a1f3e 0%, transparent 50%),
          linear-gradient(165deg, var(--bg-1), var(--bg-2));
        color: var(--ink);
        font-family: "Manrope", sans-serif;
      }
      .app-shell-header {
        backdrop-filter: blur(8px);
        background: linear-gradient(90deg, rgba(8, 20, 37, 0.92), rgba(24, 41, 71, 0.88));
        border-bottom: 1px solid rgba(244, 200, 105, 0.18);
      }
      .brand-title {
        font-family: "Cinzel", serif;
        letter-spacing: 0.06em;
        color: #f8e3b1;
        text-transform: uppercase;
      }
      .brand-subtitle {
        color: var(--ink-soft);
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .app-shell-drawer {
        backdrop-filter: blur(8px);
        background: rgba(6, 14, 29, 0.82);
        border-right: 1px solid rgba(244, 200, 105, 0.15);
        width: 220px !important;
        min-width: 220px !important;
        max-width: 220px !important;
      }
      .app-shell-drawer .q-drawer__content {
        padding-top: 0.25rem;
      }
      .drawer-panel-title {
        font-family: "Cinzel", serif;
        font-size: 0.72rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #f8e3b1;
        margin: 0 0 0.35rem 0;
        opacity: 0.95;
      }
      .drawer-section-label {
        font-size: 0.62rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--ink-soft);
        margin: 0.45rem 0 0.2rem 0;
        font-weight: 700;
      }
      .drawer-section-label:first-of-type {
        margin-top: 0;
      }
      .nav-drawer-btn {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        color: var(--ink) !important;
        min-height: 34px !important;
        padding: 0 6px !important;
        border-radius: 8px !important;
        justify-content: flex-start !important;
      }
      .nav-drawer-btn .q-btn__content {
        justify-content: flex-start !important;
        width: 100%;
      }
      .nav-drawer-btn .q-icon {
        font-size: 1.05rem !important;
        color: rgba(244, 200, 105, 0.85);
      }
      .nav-drawer-btn--active {
        background: linear-gradient(135deg, var(--accent-soft), transparent) !important;
        border: 1px solid rgba(244, 200, 105, 0.38) !important;
        color: #fff !important;
      }
      .nav-drawer-btn--active .q-icon {
        color: #f8e3b1 !important;
      }
      .drawer-external {
        font-size: 0.72rem !important;
        color: #9fd4ff !important;
        text-decoration: none !important;
        display: block;
        padding: 0.15rem 0;
        line-height: 1.35;
      }
      .drawer-external:hover {
        text-decoration: underline !important;
        color: #c5e4ff !important;
      }
      .drawer-meta {
        font-size: 0.68rem !important;
        color: var(--ink-soft) !important;
        line-height: 1.4;
        margin: 0.1rem 0;
      }
      .drawer-logout.q-btn {
        margin-top: 0.35rem;
        font-size: 0.75rem !important;
      }
      .content-stage {
        width: 100%;
        max-width: none;
      }
      .content-panel {
        background: var(--panel);
        border: 1px solid rgba(138, 160, 196, 0.24);
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
      }
      .login-panel {
        min-width: 380px;
        background: rgba(8, 19, 35, 0.9);
        border: 1px solid rgba(244, 200, 105, 0.3);
        border-radius: 16px;
        box-shadow: 0 16px 40px rgba(2, 8, 16, 0.55);
      }

      /* ── Full-width content cards ── */
      .content-panel.q-card {
        width: 100% !important;
        max-width: none !important;
      }

      /* ── Quasar input dark-theme overrides ── */
      .q-field__control,
      .q-field__native,
      .q-field__input {
        color: #d7e0ef !important;
        caret-color: #f4c869 !important;
      }
      .q-field__label {
        color: #95a3bc !important;
      }
      .q-field--outlined .q-field__control {
        border-color: rgba(138, 160, 196, 0.45) !important;
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 8px !important;
      }
      .q-field--outlined.q-field--focused .q-field__control {
        border-color: #f4c869 !important;
        background: rgba(244, 200, 105, 0.06) !important;
      }
      .q-field--outlined.q-field--focused .q-field__label,
      .q-field--outlined.q-field--float .q-field__label {
        color: #f4c869 !important;
      }
      /* Textarea + input placeholder */
      .q-field__native::placeholder,
      .q-field__input::placeholder {
        color: rgba(149, 163, 188, 0.6) !important;
      }
      /* Select dropdown */
      .q-menu, .q-select__dropdown-icon {
        background: #0e1e33;
        color: #d7e0ef;
      }
      .q-item:hover { background: rgba(244, 200, 105, 0.08); }
      .q-item__label { color: #d7e0ef; }
      /* Checkbox / switch labels */
      .q-checkbox__label, .q-toggle__label, .q-switch__label {
        color: #d7e0ef !important;
      }
      /* Table dark overrides (QTable + native table) */
      .q-table {
        background: rgba(6, 14, 29, 0.72) !important;
        color: #d7e0ef !important;
      }
      .q-table__card {
        background: transparent !important;
        color: #d7e0ef !important;
      }
      .q-table__container {
        background: rgba(4, 10, 22, 0.5) !important;
      }
      .q-table__middle.scroll {
        background: transparent !important;
      }
      .q-table thead tr, .q-table thead th {
        background: rgba(6, 14, 29, 0.95) !important;
        color: #f4c869 !important;
        font-family: "Manrope", sans-serif;
        font-weight: 700;
        letter-spacing: 0.04em;
        border-bottom: 1px solid rgba(244, 200, 105, 0.25) !important;
      }
      .q-table tbody tr {
        background: transparent !important;
        color: #d7e0ef !important;
      }
      .q-table tbody tr:hover td {
        background: rgba(244, 200, 105, 0.08) !important;
      }
      .q-table tbody td {
        color: #d7e0ef !important;
        border-bottom: 1px solid rgba(138, 160, 196, 0.12) !important;
      }
      .q-table tbody tr.selected td,
      tbody tr.selected .q-td {
        background: rgba(244, 200, 105, 0.14) !important;
      }
      .q-table__top, .q-table__bottom {
        background: rgba(6, 14, 29, 0.88) !important;
        color: #d7e0ef !important;
        border-color: rgba(138, 160, 196, 0.2) !important;
      }
      .q-table__bottom .q-table__control,
      .q-table__bottom .q-table__separator,
      .q-table__bottom-item {
        color: var(--ink-soft) !important;
      }
      .q-table__bottom .q-btn {
        color: #f4c869 !important;
      }
      .q-table .q-checkbox__svg,
      .q-table .q-checkbox__inner--truthy .q-checkbox__bg {
        color: #f4c869 !important;
      }
      .options-table {
        border: 1px solid rgba(138, 160, 196, 0.22);
        border-radius: 10px;
        overflow: hidden;
      }
      /* Scrollarea */
      .q-scrollarea__thumb { background: rgba(244, 200, 105, 0.35); }
      /* Separator */
      .q-separator { background: rgba(138, 160, 196, 0.2); }
      /* Buttons */
      .q-btn { font-family: "Manrope", sans-serif; font-weight: 600; letter-spacing: 0.04em; }

      /* ── Nested cards (e.g. AI agent sidebar, message bubbles) ── */
      .content-panel .q-card {
        background: rgba(8, 18, 34, 0.88) !important;
        color: #d7e0ef !important;
        border: 1px solid rgba(138, 160, 196, 0.22) !important;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.2);
      }

      /* AI Agent page */
      .agent-page-title {
        font-family: "Cinzel", serif;
        letter-spacing: 0.06em;
        color: #f8e3b1;
        text-transform: uppercase;
      }
      .agent-muted {
        color: #95a3bc !important;
      }
      .agent-sidebar {
        flex: 0 0 min(280px, 28vw);
        min-width: 240px;
        max-width: 320px;
      }
      .agent-cat-market { color: #9fd4ff !important; }
      .agent-cat-account { color: #8fdd9f !important; }
      .agent-cat-trading { color: #ff9a9a !important; }
      .agent-cat-skills { color: #d8b8ff !important; }
      .agent-cat-default { color: #c5d0e5 !important; }
      .agent-switch-off .q-switch__label {
        color: #ffb4b4 !important;
      }
      .agent-chat-scroll {
        border: 1px solid rgba(138, 160, 196, 0.28) !important;
        border-radius: 12px !important;
        background: rgba(4, 12, 26, 0.5) !important;
      }
      .agent-header-btn.q-btn {
        color: #f4c869 !important;
        border: 1px solid rgba(244, 200, 105, 0.45) !important;
        background: rgba(244, 200, 105, 0.08) !important;
      }
      .agent-header-btn.q-btn:hover {
        background: rgba(244, 200, 105, 0.16) !important;
      }
      .agent-skill-btn.q-btn {
        color: #e8ddff !important;
        border-color: rgba(200, 175, 255, 0.5) !important;
      }
      .agent-skill-btn.q-btn:hover {
        background: rgba(200, 175, 255, 0.12) !important;
      }
      .agent-user-bubble {
        background: rgba(55, 110, 190, 0.4) !important;
        color: #eef4ff !important;
        border: 1px solid rgba(130, 175, 255, 0.35);
      }
      .agent-assistant-card {
        background: rgba(12, 26, 48, 0.95) !important;
        border: 1px solid rgba(138, 160, 196, 0.25) !important;
      }
      .agent-assistant-card .nicegui-markdown,
      .agent-assistant-card .markdown-body,
      .agent-assistant-card .markdown-body p,
      .agent-assistant-card .markdown-body li {
        color: #d7e0ef !important;
      }
      .agent-assistant-card .markdown-body a {
        color: #f4c869 !important;
      }
      .agent-assistant-card .markdown-body code {
        background: rgba(244, 200, 105, 0.12) !important;
        color: #f8e3b1 !important;
      }
      .agent-tool-caption {
        color: #aab6cc !important;
        font-style: italic;
      }
      .agent-tool-link {
        color: #8ec5ff !important;
        font-style: italic;
        cursor: pointer;
      }
      .agent-chart-cap {
        color: #d8b8ff !important;
      }
    </style>
    """,
    shared=True,
)


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


def _drawer_nav_button(path: str, label: str, icon: str, active: str) -> None:
    cls = "nav-drawer-btn full-width"
    if path == active:
        cls += " nav-drawer-btn--active"
    ui.button(
        label,
        icon=icon,
        on_click=lambda p=path: ui.navigate.to(p),
    ).props("flat dense no-caps").classes(cls)


def _app_layout(inner, *, active: str):
    with ui.header().classes("app-shell-header q-px-lg q-py-sm"):
        with ui.row().classes("items-center justify-between w-full"):
            with ui.column().classes("gap-0"):
                ui.label("Schwab Control Deck").classes("brand-title text-h6")
                ui.label("Market data, options, and AI execution").classes("brand-subtitle")
    with ui.left_drawer(value=True).classes("app-shell-drawer q-pa-xs").props(
        "width=220"
    ):
        ui.label("Navigate").classes("drawer-panel-title")

        ui.label("Trading & data").classes("drawer-section-label")
        _drawer_nav_button("/account", "Account", "account_balance", active)
        _drawer_nav_button("/options", "Option trade", "candlestick_chart", active)
        _drawer_nav_button("/chart", "Chart", "show_chart", active)

        ui.separator().classes("q-my-xs")

        ui.label("Intelligence").classes("drawer-section-label")
        _drawer_nav_button("/agent", "AI Agent", "smart_toy", active)

        ui.separator().classes("q-my-sm")

        ui.label("Quick links").classes("drawer-section-label")
        ui.link(
            "Schwab.com",
            "https://www.schwab.com",
            new_tab=True,
        ).classes("drawer-external")
        ui.link(
            "Developer portal",
            "https://developer.schwab.com",
            new_tab=True,
        ).classes("drawer-external")
        ui.link(
            "Daily Financial News",
            "https://www.youtube.com/@dailyFinanceTv",
            new_tab=True,
        ).classes("drawer-external")

        port = int(os.getenv("NICEGUI_PORT", "8080"))
        ui.label(f"App port · {port}").classes("drawer-meta")

        time_lbl = ui.label("").classes("drawer-meta")

        def _drawer_clock() -> None:
            time_lbl.set_text(datetime.now().strftime("%H:%M · local time"))

        ui.timer(0, _drawer_clock, once=True)
        ui.timer(30.0, _drawer_clock)

        ui.separator().classes("q-my-xs")

        def logout():
            app.storage.user.clear()
            ui.navigate.to("/login")

        ui.button("Log out", on_click=logout, icon="logout").classes(
            "drawer-logout full-width"
        ).props("dense unelevated outline")
    with ui.column().classes("w-full q-pa-sm"):
        with ui.column().classes("content-stage"):
            with ui.card().classes("content-panel q-pa-md w-full").style("display: flex; flex-direction: column"):
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


    with ui.card().classes("absolute-center p-8 login-panel"):
        ui.label("Welcome back").classes("text-h5 brand-title")
        ui.label("Enter your access password to continue").classes("brand-subtitle")
        if not expected:
            ui.label(
                "No password configured. Set APP_PASSWORD in .env (project root or src/.env)."
            ).classes("text-warning")
        pw = (
            ui.input("Password", password=True, password_toggle_button=True)
            .props("outlined dense")
            .classes("w-full")
        )
        pw.on("keydown.enter", try_login)
        ui.button("Log in", on_click=try_login, icon="login").classes("w-full")


@ui.page("/")
def root_page():
    ui.navigate.to("/account")


@ui.page("/account")
def account_page():
    _app_layout(build_account_page, active="/account")


@ui.page("/options")
def options_page():
    option_state = {}
    _app_layout(lambda: build_option_trade_page(option_state), active="/options")


@ui.page("/chart")
def chart_page():
    _app_layout(build_chart_page, active="/chart")


@ui.page("/agent")
def agent_page():
    _app_layout(build_agent_page, active="/agent")


if __name__ in {"__main__", "__mp_main__"}:
    storage_secret = os.getenv("NICEGUI_STORAGE_SECRET", "change-me-in-production")
    ui.run(
        title="Schwab AI Trader",
        storage_secret=storage_secret,
        port=int(os.getenv("NICEGUI_PORT", "8080")),
    )
