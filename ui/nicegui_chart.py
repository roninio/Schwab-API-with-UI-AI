from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import run, ui

from src.spx_chart import (
    apply_live_price_to_highcharts_options,
    get_spx_quote_snapshot,
    get_spx_live_stream,
    highcharts_stock_options,
)


def build_chart_page():
    exchange_tz = ZoneInfo("America/New_York")

    def format_exchange_time(epoch_ms: int) -> str:
        dt = datetime.fromtimestamp(int(epoch_ms) / 1000, tz=exchange_tz)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    ui.label("APPL — Highcharts Stock (live 1m candles & MA30)").classes("text-h5")
    is_live = {"value": True}
    is_loading = {"value": False}
    chart_state: dict[str, object] = {"options": None}
    with ui.row().classes("items-center gap-6"):
        last_price_label = ui.label("Last Price: --")
        day_change_label = ui.label("Day Change: --")
        quote_time_label = ui.label("Date/Time: --")
    last_update = ui.label("Last update: pending...")
    error_label = ui.label().classes("text-negative")
    error_label.set_visibility(False)
    chart = ui.highchart(
        {
            "title": {"text": "GOOG — loading..."},
            "series": [],
            "chart": {"height": 640},
        },
        type="stockChart",
        extras=["stock"],
    ).classes("w-full")

    async def load():
        if is_loading["value"]:
            return
        is_loading["value"] = True
        try:
            options = await run.io_bound(highcharts_stock_options)
            chart_state["options"] = options
            chart.options = options
            chart.update()
            error_label.set_visibility(False)
            # Prefer quote snapshot for current stats; fallback to latest candle.
            snapshot = await run.io_bound(get_spx_quote_snapshot)
            if snapshot:
                last_price_label.set_text(
                    f"Last Price: {float(snapshot['last_price']):,.2f}"
                )
                day_change = snapshot.get("day_change")
                if isinstance(day_change, (int, float)):
                    sign = "+" if float(day_change) >= 0 else ""
                    day_change_label.set_text(f"Day Change: {sign}{float(day_change):,.2f}")
                else:
                    day_change_label.set_text("Day Change: --")
                quote_time_label.set_text(
                    f"Date/Time: {format_exchange_time(int(snapshot['quote_time_ms']))}"
                )
            else:
                series = options.get("series", [])
                ohlc = series[0].get("data", []) if isinstance(series, list) and series else []
                if isinstance(ohlc, list) and ohlc:
                    latest = ohlc[-1]
                    if isinstance(latest, list) and len(latest) >= 5:
                        last_price = float(latest[4])
                        last_price_label.set_text(f"Last Price: {last_price:,.2f}")
                        last_ts_ms = int(latest[0])
                        quote_time_label.set_text(
                            f"Date/Time: {format_exchange_time(last_ts_ms)}"
                        )
                        if len(ohlc) >= 2 and isinstance(ohlc[-2], list) and len(ohlc[-2]) >= 5:
                            prev_close = float(ohlc[-2][4])
                            day_change = last_price - prev_close
                            sign = "+" if day_change >= 0 else ""
                            day_change_label.set_text(f"Day Change: {sign}{day_change:,.2f}")
                        else:
                            day_change_label.set_text("Day Change: --")
            last_update.set_text(
                f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except Exception as e:
            error_label.set_text(f"Chart error: {e}")
            error_label.set_visibility(True)
            last_update.set_text("Last update: failed")
        finally:
            is_loading["value"] = False

    async def tick():
        if not is_live["value"]:
            return

        live_stream = get_spx_live_stream()
        try:
            await run.io_bound(live_stream.start)
        except Exception:
            # Keep page usable even when stream auth/network fails.
            await load()
            return

        quote = await run.io_bound(live_stream.consume_latest)
        options = chart_state.get("options")
        if quote and isinstance(options, dict):
            changed = apply_live_price_to_highcharts_options(
                options,
                last_price=float(quote["last_price"]),
                quote_time_ms=int(quote["quote_time_ms"]),
            )
            if changed:
                chart.options = options
                chart.update()
                error_label.set_visibility(False)
                last_update.set_text(
                    f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (stream)"
                )
            last_price_label.set_text(f"Last Price: {float(quote['last_price']):,.2f}")
            day_change = quote.get("day_change")
            if isinstance(day_change, (int, float)):
                sign = "+" if float(day_change) >= 0 else ""
                day_change_label.set_text(f"Day Change: {sign}{float(day_change):,.2f}")
            else:
                day_change_label.set_text("Day Change: --")
            quote_time_label.set_text(
                f"Date/Time: {format_exchange_time(int(quote['quote_time_ms']))}"
            )

    def on_live_toggle(event):
        is_live["value"] = bool(event.value)
        if not is_live["value"]:
            get_spx_live_stream().stop()

    ui.button("Refresh", on_click=load, icon="refresh")
    ui.switch("Live stream", value=True, on_change=on_live_toggle)
    ui.timer(5.0, tick)
    ui.timer(0, load, once=True)
