import json
from pathlib import Path

import pandas as pd
from nicegui import run, ui

import src.app_logging_config as log_conf
from src.client import get_client
from src.get_optionchains import Get_option_chain

logging = log_conf.loger(__name__)
logger = logging

columns_to_print = [
    "symbol",
    "putCall",
    "strikePrice",
    "experationDate",
    "bid",
    "ask",
    "bidSize",
    "askSize",
    "daysToExpiration",
    "bought",
]

_WATCHLIST_FILE = Path(__file__).resolve().parent.parent / "watchlist.json"

DEFAULT_WATCHLIST = [
    "SOFI",
    "NVDA",
]


def _normalize_watchlist_symbols(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.replace(",", "\n").splitlines():
        for part in line.split():
            s = part.strip().upper()
            if s and s not in out:
                out.append(s)
    return out


def load_watchlist() -> list[str]:
    if not _WATCHLIST_FILE.is_file():
        return list(DEFAULT_WATCHLIST)
    try:
        with open(_WATCHLIST_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            out: list[str] = []
            for x in data:
                if isinstance(x, str):
                    s = x.strip().upper()
                    if s and s not in out:
                        out.append(s)
            return out if out else list(DEFAULT_WATCHLIST)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Watchlist file unreadable (%s), using defaults", e)
    return list(DEFAULT_WATCHLIST)


def save_watchlist(symbols: list[str]) -> None:
    with open(_WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(symbols, f, indent=2)


def get_data(symbol: str, filter_chains: bool):
    client = get_client()
    get_option_chain = Get_option_chain(client)
    get_option_chain.filter_optionchains = filter_chains
    data = get_option_chain.get_options(symbol=symbol)
    current_price = get_option_chain.symbol_price
    previous_bought = get_option_chain.load_contracts_from_csv()
    data["bought"] = data["symbol"].isin(previous_bought)
    return data, current_price, get_option_chain.netPercentChange


def get_symbol_chain_list():
    client = get_client()
    get_option_chain = Get_option_chain(client)
    data = get_option_chain.get_list_symbols(load_watchlist())
    previous_bought = get_option_chain.load_contracts_from_csv()
    data["bought"] = data["symbol"].isin(previous_bought)
    return data


def _df_to_table_rows(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    present = [c for c in columns_to_print if c in df.columns]
    sub = df[present].copy()
    sub["_rid"] = range(len(sub))
    rows = sub.to_dict("records")
    columns = [{"name": c, "label": c, "field": c} for c in ["_rid"] + present]
    return columns, rows


def build_option_trade_page(selection_state: dict):
    ui.label("Option trade").classes("text-h5")
    stage_label = ui.label("Stage: enter symbol").classes("text-caption")
    result_area = ui.column()
    chain_table_holder = ui.column().classes("w-full")
    order_area = ui.column().classes("w-full")

    def _render_order_panel():
        order_area.clear()
        created = selection_state.get("created")
        if created is None or len(created) == 0:
            return
        with order_area:
            ui.label("Selected row(s):").classes("text-weight-medium")
            present = [c for c in columns_to_print if c in created.columns]
            ui.table.from_pandas(created[present].copy())

    def _render_chain_table():
        chain_table_holder.clear()
        df = selection_state.get("df")
        if df is None or len(df) == 0:
            with chain_table_holder:
                ui.label("No option chains found")
            return

        price = selection_state.get("current_price", "")
        net_pct = selection_state.get("net_pct", "")
        columns, rows = _df_to_table_rows(df)

        def on_select(e):
            rows_sel = e.selection or []
            if not rows_sel:
                selection_state["created"] = None
                selection_state["stage"] = 1
                order_area.clear()
                return
            selected_rids = {r["_rid"] for r in rows_sel}
            sub = df.iloc[sorted(selected_rids)].copy()
            selection_state["created"] = sub
            selection_state["stage"] = 2
            _render_order_panel()

        with chain_table_holder:
            if (
                selection_state.get("current_price") == ""
                and selection_state.get("net_pct") == ""
            ):
                wl = load_watchlist()
                ui.label(
                    f"Watchlist ({len(wl)}): {', '.join(wl)}"
                ).classes("text-caption text-wrap")
            else:
                ui.label("Select contract row(s) below.").classes("text-caption")
            ui.label(f"Current price: {price}").classes("text-weight-bold")
            ui.label(f"Percent change today: {net_pct}").classes("text-weight-bold")
            ui.table(
                columns=columns,
                rows=rows,
                row_key="_rid",
                selection="multiple",
                on_select=on_select,
            ).classes("w-full")

    async def run_fetch(symbol: str, filter_chains: bool):
        selection_state["stage"] = 0
        selection_state["created"] = None
        order_area.clear()
        result_area.clear()

        try:
            data, current_price, net_pct = await run.io_bound(
                get_data, symbol, filter_chains
            )
        except Exception as e:
            chain_table_holder.clear()
            with chain_table_holder:
                ui.label(f"Request failed: {e}").classes("text-negative")
            return

        if current_price == 0:
            chain_table_holder.clear()
            with chain_table_holder:
                ui.label(f"Symbol '{symbol}' not found").classes("text-warning")
            selection_state["df"] = None
            return

        selection_state["df"] = data
        selection_state["current_price"] = current_price
        selection_state["net_pct"] = net_pct
        selection_state["stage"] = 1
        stage_label.set_text("Stage: select row(s)")
        _render_chain_table()

    async def run_fetch_watchlist():
        selection_state["stage"] = 0
        selection_state["created"] = None
        order_area.clear()
        result_area.clear()

        try:
            data = await run.io_bound(get_symbol_chain_list)
        except Exception as e:
            chain_table_holder.clear()
            with chain_table_holder:
                ui.label(f"RunAll failed: {e}").classes("text-negative")
            return

        selection_state["df"] = data
        selection_state["current_price"] = ""
        selection_state["net_pct"] = ""
        stage_label.set_text("Stage: select row(s) (watchlist)")
        _render_chain_table()

    watchlist_refresh_busy = {"value": False}

    async def run_fetch_watchlist_if_idle():
        if watchlist_refresh_busy["value"]:
            return
        watchlist_refresh_busy["value"] = True
        try:
            await run_fetch_watchlist()
        finally:
            watchlist_refresh_busy["value"] = False

    with ui.row().classes("w-full no-wrap gap-4"):
        with ui.column().classes("w-1/2"):
            symbol_in = ui.input("Enter symbol").props("dense outlined")
            filter_cb = ui.checkbox("Filter (bid size, spread)", value=True)

            async def on_submit():
                sym = (symbol_in.value or "").strip().upper()
                if not sym:
                    ui.notify("Enter a symbol", color="warning")
                    return
                await run_fetch(sym, filter_cb.value)

            ui.button("Submit", on_click=on_submit, icon="search")

        with ui.column().classes("w-1/2 gap-2"):
            watchlist_ta = (
                ui.textarea(
                    "Watchlist (one ticker per line)",
                    value="\n".join(load_watchlist()),
                )
                .props("outlined dense rows=8")
                .classes("w-full")
            )

            def save_watchlist_click():
                syms = _normalize_watchlist_symbols(watchlist_ta.value or "")
                if not syms:
                    ui.notify("Add at least one symbol", color="warning")
                    return
                try:
                    save_watchlist(syms)
                except OSError as e:
                    ui.notify(f"Could not save: {e}", color="negative")
                    return
                ui.notify(f"Saved {len(syms)} symbol(s)", color="positive")

            ui.button("Save watchlist", on_click=save_watchlist_click, icon="save")
            ui.button(
                "RunAll (watchlist)",
                on_click=run_fetch_watchlist,
                icon="playlist_play",
            )
            with ui.row().classes("items-center gap-3 flex-wrap"):
                runall_auto = ui.checkbox(
                    "Auto-refresh watchlist", value=False
                ).props("dense")
                runall_secs = ui.number(
                    label="Every (sec)",
                    value=60,
                    min=10,
                    max=3600,
                    step=5,
                    format="%.0f",
                ).classes("w-36").props("dense outlined")
            runall_auto.tooltip(
                "When enabled, reloads the watchlist on the interval below. "
                "Uncheck to stop."
            )
            watchlist_timer = ui.timer(
                60.0,
                run_fetch_watchlist_if_idle,
                active=False,
                immediate=False,
            )

            def _sync_watchlist_timer_interval(_=None) -> None:
                try:
                    s = float(runall_secs.value)
                except (TypeError, ValueError):
                    return
                watchlist_timer.interval = max(10.0, min(3600.0, s))

            runall_auto.bind_value_to(watchlist_timer, "active")
            runall_secs.on("update:model-value", _sync_watchlist_timer_interval)
            _sync_watchlist_timer_interval()
