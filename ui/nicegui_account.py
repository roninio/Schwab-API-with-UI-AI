import json
from typing import Any

from nicegui import run, ui

from src.client import get_client
from src.account import AccountInfo


def _rows_for_ui_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """NiceGUI tables cannot render nested list/dict cells without custom slots; stringify them."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            out.append({"_value": row})
            continue
        flat = {}
        for key, val in row.items():
            if isinstance(val, (list, dict)):
                flat[key] = json.dumps(val, default=str)
            else:
                flat[key] = val
        out.append(flat)
    return out


def build_account_page():
    ui.label("Account details").classes("text-h5")

    async def load():
        try:

            def _fetch():
                client = get_client()
                ac = AccountInfo(client)
                account_number = ac.account
                orders = ac.get_orders(days_to_lookback=12)
                return account_number, orders

            account_number, orders = await run.io_bound(_fetch)
            content.clear()
            with content:
                ui.label(f"Account number: {account_number}")
                if isinstance(orders, dict) and "message" in orders:
                    ui.label("No orders found on account")
                    return
                if orders is None or len(orders) == 0:
                    ui.label("No orders found on account")
                    return
                ui.label("Orders").classes("text-h6")
                table_rows = _rows_for_ui_table(orders)
                ui.table(
                    rows=table_rows,
                    columns=_rows_to_columns(table_rows),
                ).classes("w-full")

        except Exception as e:
            content.clear()
            with content:
                ui.label(f"Error: {e}").classes("text-negative")

    def _rows_to_columns(rows: list) -> list[dict]:
        if not rows:
            return []
        keys = set()
        for row in rows:
            if isinstance(row, dict):
                keys.update(row.keys())
        return [
            {"name": k, "label": k, "field": k, "align": "left"}
            for k in sorted(keys)
        ]

    content = ui.column()
    ui.button("Refresh", on_click=load, icon="refresh")
    ui.timer(0, load, once=True)
