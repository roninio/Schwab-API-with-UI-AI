from nicegui import run, ui

from src.spx_chart import highcharts_stock_options


def build_chart_page():
    ui.label("SPX — Highcharts Stock (candlestick & MA30)").classes("text-h5")
    slot = ui.column().classes("w-full")

    async def load():
        try:
            options = await run.io_bound(highcharts_stock_options)
            slot.clear()
            with slot:
                ui.highchart(
                    options,
                    type="stockChart",
                    extras=["stock"],
                ).classes("w-full")
        except Exception as e:
            slot.clear()
            with slot:
                ui.label(f"Chart error: {e}").classes("text-negative")

    ui.button("Refresh", on_click=load, icon="refresh")
    ui.timer(0, load, once=True)
