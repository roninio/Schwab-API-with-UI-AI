"""
Agent tool definitions and implementations for all schwabdev API calls.
Each tool wraps a schwabdev Client method and returns JSON-serialisable data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from src.client import get_client
from src.account import AccountInfo
from src.orders import SubmitOrders


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ToolParam:
    name: str
    type: str           # "string" | "number" | "integer" | "boolean"
    description: str
    required: bool = True
    enum: list[str] | None = None


@dataclass
class ToolDefinition:
    name: str
    label: str
    description: str
    category: str       # "Market Data" | "Account Info" | "Trading"
    params: list[ToolParam]
    fn: Callable[..., Any]
    enabled_by_default: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _account_hash() -> str:
    """Fetch the primary account hash (makes one linked_accounts API call)."""
    client = get_client()
    acc = client.linked_accounts().json()
    return acc[0]["hashValue"]


def _date_range(days_back: int) -> tuple[datetime, datetime]:
    now = datetime.now()
    return now - timedelta(days=days_back), now


def _safe_json(resp) -> Any:
    """Return .json() from a requests.Response, or an error dict."""
    try:
        return resp.json()
    except Exception:
        return {"status_code": resp.status_code, "text": resp.text[:500]}


# ---------------------------------------------------------------------------
# Market Data tools
# ---------------------------------------------------------------------------

def _tool_get_quote(symbol: str) -> Any:
    return _safe_json(get_client().quote(symbol))


def _tool_get_quotes(symbols: str) -> Any:
    syms = [s.strip() for s in symbols.split(",")]
    return _safe_json(get_client().quotes(syms))


def _tool_get_option_chain(
    symbol: str,
    contract_type: str = "ALL",
    strike_count: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    days_to_expiration: int | None = None,
) -> Any:
    kwargs: dict[str, Any] = {"symbol": symbol, "contractType": contract_type}
    if strike_count is not None:
        kwargs["strikeCount"] = strike_count
    if from_date:
        kwargs["fromDate"] = from_date
    if to_date:
        kwargs["toDate"] = to_date
    if days_to_expiration is not None:
        kwargs["daysToExpiration"] = days_to_expiration
    return _safe_json(get_client().option_chains(**kwargs))


def _tool_get_option_expirations(symbol: str) -> Any:
    return _safe_json(get_client().option_expiration_chain(symbol))


def _tool_get_price_history(
    symbol: str,
    period_type: str = "month",
    period: int | None = None,
    frequency_type: str = "daily",
    frequency: int = 1,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
        "symbol": symbol,
        "periodType": period_type,
        "frequencyType": frequency_type,
        "frequency": frequency,
    }
    if period is not None:
        kwargs["period"] = period
    if start_date:
        kwargs["startDate"] = start_date
    if end_date:
        kwargs["endDate"] = end_date
    return _safe_json(get_client().price_history(**kwargs))


def _tool_get_movers(
    index: str,
    sort: str | None = None,
    frequency: int | None = None,
) -> Any:
    kwargs: dict[str, Any] = {"symbol": index}
    if sort:
        kwargs["sort"] = sort
    if frequency is not None:
        kwargs["frequency"] = frequency
    return _safe_json(get_client().movers(**kwargs))


def _tool_get_market_hours(markets: str, date: str | None = None) -> Any:
    market_list = [m.strip() for m in markets.split(",")]
    kwargs: dict[str, Any] = {"symbols": market_list}
    if date:
        kwargs["date"] = date
    return _safe_json(get_client().market_hours(**kwargs))


def _tool_search_instruments(query: str, projection: str = "symbol-search") -> Any:
    return _safe_json(get_client().instruments(query, projection))


def _tool_get_instrument_by_cusip(cusip: str) -> Any:
    return _safe_json(get_client().instrument_cusip(cusip))


# ---------------------------------------------------------------------------
# Account Info tools
# ---------------------------------------------------------------------------

def _tool_get_linked_accounts() -> Any:
    return _safe_json(get_client().linked_accounts())


def _tool_get_account_details(fields: str | None = None) -> Any:
    return _safe_json(get_client().account_details(_account_hash(), fields=fields or None))


def _tool_get_all_account_details(fields: str | None = None) -> Any:
    return _safe_json(get_client().account_details_all(fields=fields or None))


def _tool_get_positions() -> Any:
    return _safe_json(get_client().account_details(_account_hash(), fields="positions"))


def _tool_get_account_orders(
    days_back: int = 10,
    status: str | None = None,
    max_results: int | None = None,
) -> Any:
    from_dt, to_dt = _date_range(days_back)
    kwargs: dict[str, Any] = {
        "accountHash": _account_hash(),
        "fromEnteredTime": from_dt,
        "toEnteredTime": to_dt,
    }
    if status:
        kwargs["status"] = status
    if max_results is not None:
        kwargs["maxResults"] = max_results
    return _safe_json(get_client().account_orders(**kwargs))


def _tool_get_all_orders(
    days_back: int = 10,
    status: str | None = None,
    max_results: int | None = None,
) -> Any:
    from_dt, to_dt = _date_range(days_back)
    kwargs: dict[str, Any] = {
        "fromEnteredTime": from_dt,
        "toEnteredTime": to_dt,
    }
    if status:
        kwargs["status"] = status
    if max_results is not None:
        kwargs["maxResults"] = max_results
    return _safe_json(get_client().account_orders_all(**kwargs))


def _tool_get_order_details(order_id: str) -> Any:
    return _safe_json(get_client().order_details(_account_hash(), order_id))


def _tool_get_transactions(
    days_back: int = 30,
    types: str = "TRADE",
    symbol: str | None = None,
) -> Any:
    from_dt, to_dt = _date_range(days_back)
    kwargs: dict[str, Any] = {
        "accountHash": _account_hash(),
        "startDate": from_dt,
        "endDate": to_dt,
        "types": types,
    }
    if symbol:
        kwargs["symbol"] = symbol
    return _safe_json(get_client().transactions(**kwargs))


def _tool_get_transaction_details(transaction_id: str) -> Any:
    return _safe_json(get_client().transaction_details(_account_hash(), transaction_id))


def _tool_get_preferences() -> Any:
    return _safe_json(get_client().preferences())


def _tool_preview_order(
    symbol: str,
    instruction: str,
    quantity: int,
    price: float,
    asset_type: str = "OPTION",
) -> Any:
    order = {
        "orderType": "LIMIT",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "price": price,
        "orderLegCollection": [
            {
                "instruction": instruction,
                "quantity": quantity,
                "instrument": {"symbol": symbol, "assetType": asset_type},
            }
        ],
    }
    return _safe_json(get_client().preview_order(_account_hash(), order))


# ---------------------------------------------------------------------------
# Trading tools  (enabled_by_default=False)
# ---------------------------------------------------------------------------

def _tool_buy_option(symbol: str, quantity: int, price: float) -> dict:
    client = get_client()
    orders = SubmitOrders(client)
    account_hash = _account_hash()
    order_id = orders.place_order(
        symbol=symbol,
        account_hash=account_hash,
        price=price,
        instruction="BUY_TO_OPEN",
        quantity=quantity,
        asset_type="OPTION",
    )
    return {"order_id": order_id, "status": "submitted", "action": "BUY_TO_OPEN"}


def _tool_sell_option(symbol: str, quantity: int, price: float) -> dict:
    client = get_client()
    orders = SubmitOrders(client)
    account_hash = _account_hash()
    order_id = orders.place_order(
        symbol=symbol,
        account_hash=account_hash,
        price=price,
        instruction="SELL_TO_OPEN",
        quantity=quantity,
        asset_type="OPTION",
    )
    return {"order_id": order_id, "status": "submitted", "action": "SELL_TO_OPEN"}


def _tool_buy_stock(symbol: str, quantity: int, price: float) -> dict:
    client = get_client()
    orders = SubmitOrders(client)
    account_hash = _account_hash()
    order_id = orders.place_order(
        symbol=symbol,
        account_hash=account_hash,
        price=price,
        instruction="BUY",
        quantity=quantity,
        asset_type="EQUITY",
    )
    return {"order_id": order_id, "status": "submitted", "action": "BUY", "asset_type": "EQUITY"}


def _tool_sell_stock(symbol: str, quantity: int, price: float) -> dict:
    client = get_client()
    orders = SubmitOrders(client)
    account_hash = _account_hash()
    order_id = orders.place_order(
        symbol=symbol,
        account_hash=account_hash,
        price=price,
        instruction="SELL",
        quantity=quantity,
        asset_type="EQUITY",
    )
    return {"order_id": order_id, "status": "submitted", "action": "SELL", "asset_type": "EQUITY"}


def _tool_cancel_order(order_id: str) -> dict:
    client = get_client()
    orders = SubmitOrders(client)
    account_hash = _account_hash()
    success = orders.cancel_order(order_id, account_hash)
    return {"cancelled": success, "order_id": order_id}


def _tool_replace_order(
    order_id: str,
    symbol: str,
    instruction: str,
    quantity: int,
    price: float,
    asset_type: str = "OPTION",
) -> Any:
    order = {
        "orderType": "LIMIT",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "price": price,
        "orderLegCollection": [
            {
                "instruction": instruction,
                "quantity": quantity,
                "instrument": {"symbol": symbol, "assetType": asset_type},
            }
        ],
    }
    return _safe_json(get_client().replace_order(_account_hash(), order_id, order))


# ---------------------------------------------------------------------------
# Chart tool
# ---------------------------------------------------------------------------

def _tool_create_stock_chart(
    symbol: str,
    period_type: str = "month",
    period: int = 1,
    frequency_type: str = "daily",
    frequency: int = 1,
) -> dict:
    """Fetch OHLCV history and return Highcharts Stock options for inline rendering."""
    kwargs: dict[str, Any] = {
        "symbol": symbol,
        "periodType": period_type,
        "frequencyType": frequency_type,
        "frequency": frequency,
        "period": period,
    }
    resp = get_client().price_history(**kwargs)
    body = resp.json()
    candles = body.get("candles", [])

    ohlc: list[list] = []
    vol: list[list] = []
    for c in candles:
        t = int(c.get("datetime", 0))
        ohlc.append([t, c["open"], c["high"], c["low"], c["close"]])
        vol.append([t, c["volume"]])

    options: dict[str, Any] = {
        "title": {"text": f"{symbol.upper()} — {period}{period_type[0].upper()}"},
        "chart": {"height": 420},
        "rangeSelector": {"selected": 1},
        "yAxis": [
            {"labels": {"align": "right", "x": -3}, "height": "65%"},
            {"labels": {"align": "right", "x": -3}, "top": "65%", "height": "35%", "offset": 0},
        ],
        "series": [
            {"type": "candlestick", "name": symbol.upper(), "data": ohlc, "yAxis": 0},
            {"type": "column",      "name": "Volume",        "data": vol,  "yAxis": 1, "color": "#7cb5ec"},
        ],
    }

    return {"__chart_type__": "highcharts_stock", "options": options, "symbol": symbol.upper()}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_TOOLS: list[ToolDefinition] = [
    # ---- Market Data ----
    ToolDefinition(
        name="get_quote",
        label="Get Quote",
        description="Fetch real-time quote for a single stock or option symbol.",
        category="Market Data",
        params=[ToolParam("symbol", "string", "Ticker symbol, e.g. SOFI or AAPL")],
        fn=_tool_get_quote,
    ),
    ToolDefinition(
        name="get_quotes",
        label="Get Quotes (multiple)",
        description="Fetch real-time quotes for multiple symbols at once.",
        category="Market Data",
        params=[ToolParam("symbols", "string", "Comma-separated ticker symbols, e.g. SOFI,AAPL,TSLA")],
        fn=_tool_get_quotes,
    ),
    ToolDefinition(
        name="get_option_chain",
        label="Get Option Chain",
        description="Fetch the option chain for a stock. Optionally filter by contract type, strike count, date range, or days to expiration.",
        category="Market Data",
        params=[
            ToolParam("symbol", "string", "Stock ticker, e.g. SOFI"),
            ToolParam("contract_type", "string", "CALL, PUT, or ALL", required=False, enum=["CALL", "PUT", "ALL"]),
            ToolParam("strike_count", "integer", "Number of strikes around ATM", required=False),
            ToolParam("from_date", "string", "Start date YYYY-MM-DD", required=False),
            ToolParam("to_date", "string", "End date YYYY-MM-DD", required=False),
            ToolParam("days_to_expiration", "integer", "Max days to expiration", required=False),
        ],
        fn=_tool_get_option_chain,
    ),
    ToolDefinition(
        name="get_option_expirations",
        label="Option Expiration Dates",
        description="Get all available option expiration dates for a ticker.",
        category="Market Data",
        params=[ToolParam("symbol", "string", "Stock ticker, e.g. SOFI")],
        fn=_tool_get_option_expirations,
    ),
    ToolDefinition(
        name="get_price_history",
        label="Price History",
        description="Fetch historical OHLCV candle data for a symbol.",
        category="Market Data",
        params=[
            ToolParam("symbol", "string", "Ticker symbol"),
            ToolParam("period_type", "string", "day, month, year, or ytd", required=False, enum=["day", "month", "year", "ytd"]),
            ToolParam("period", "integer", "Number of periods", required=False),
            ToolParam("frequency_type", "string", "minute, daily, weekly, or monthly", required=False, enum=["minute", "daily", "weekly", "monthly"]),
            ToolParam("frequency", "integer", "Frequency value (e.g. 1, 5, 15 for minutes)", required=False),
            ToolParam("start_date", "string", "Start date YYYY-MM-DD", required=False),
            ToolParam("end_date", "string", "End date YYYY-MM-DD", required=False),
        ],
        fn=_tool_get_price_history,
    ),
    ToolDefinition(
        name="get_movers",
        label="Market Movers",
        description="Get top movers for an index. Best called during market hours.",
        category="Market Data",
        params=[
            ToolParam("index", "string", "Index symbol: $SPX, $DJI, $COMPX, NYSE, NASDAQ, OTCBB, INDEX_ALL, EQUITY_ALL, OPTION_ALL, OPTION_PUT, OPTION_CALL"),
            ToolParam("sort", "string", "VOLUME, TRADES, PERCENT_CHANGE_UP, or PERCENT_CHANGE_DOWN", required=False, enum=["VOLUME", "TRADES", "PERCENT_CHANGE_UP", "PERCENT_CHANGE_DOWN"]),
            ToolParam("frequency", "integer", "0, 1, 5, 10, 30, or 60", required=False),
        ],
        fn=_tool_get_movers,
    ),
    ToolDefinition(
        name="get_market_hours",
        label="Market Hours",
        description="Get trading hours for one or more markets on a specific date.",
        category="Market Data",
        params=[
            ToolParam("markets", "string", "Comma-separated markets: equity, option, bond, future, forex"),
            ToolParam("date", "string", "Date YYYY-MM-DD (defaults to today)", required=False),
        ],
        fn=_tool_get_market_hours,
    ),
    ToolDefinition(
        name="search_instruments",
        label="Search Instruments",
        description="Search for instruments by symbol or description.",
        category="Market Data",
        params=[
            ToolParam("query", "string", "Symbol or description to search for"),
            ToolParam("projection", "string", "symbol-search, fundamental, desc-search, or desc-regex", required=False, enum=["symbol-search", "fundamental", "desc-search", "desc-regex"]),
        ],
        fn=_tool_search_instruments,
    ),
    ToolDefinition(
        name="get_instrument_by_cusip",
        label="Instrument by CUSIP",
        description="Look up instrument details by CUSIP identifier.",
        category="Market Data",
        params=[ToolParam("cusip", "string", "CUSIP identifier string")],
        fn=_tool_get_instrument_by_cusip,
    ),

    # ---- Account Info ----
    ToolDefinition(
        name="get_linked_accounts",
        label="Linked Accounts",
        description="Get all linked account numbers and their hashes.",
        category="Account Info",
        params=[],
        fn=_tool_get_linked_accounts,
    ),
    ToolDefinition(
        name="get_account_details",
        label="Account Details",
        description="Get details and balances for the primary account. Pass fields='positions' to include holdings.",
        category="Account Info",
        params=[ToolParam("fields", "string", "Optional: 'positions' to include position data", required=False)],
        fn=_tool_get_account_details,
    ),
    ToolDefinition(
        name="get_all_account_details",
        label="All Accounts Details",
        description="Get balances and details for all linked accounts.",
        category="Account Info",
        params=[ToolParam("fields", "string", "Optional: 'positions' to include position data", required=False)],
        fn=_tool_get_all_account_details,
    ),
    ToolDefinition(
        name="get_positions",
        label="Get Positions",
        description="Get all current open positions in the primary account.",
        category="Account Info",
        params=[],
        fn=_tool_get_positions,
    ),
    ToolDefinition(
        name="get_account_orders",
        label="Account Orders",
        description="Get orders for the primary account over a lookback period.",
        category="Account Info",
        params=[
            ToolParam("days_back", "integer", "How many days back to look (default 10)", required=False),
            ToolParam("status", "string", "Filter by status: AWAITING_PARENT_ORDER, AWAITING_CONDITION, AWAITING_STOP_CONDITION, AWAITING_MANUAL_REVIEW, ACCEPTED, AWAITING_UR_OUT, PENDING_ACTIVATION, QUEUED, WORKING, REJECTED, PENDING_CANCEL, CANCELED, PENDING_REPLACE, REPLACED, FILLED, EXPIRED, NEW, AWAITING_RELEASE_TIME, PENDING_ACKNOWLEDGEMENT, PENDING_RECALL, UNKNOWN", required=False),
            ToolParam("max_results", "integer", "Maximum number of orders to return", required=False),
        ],
        fn=_tool_get_account_orders,
    ),
    ToolDefinition(
        name="get_all_orders",
        label="All Accounts Orders",
        description="Get orders across all linked accounts over a lookback period.",
        category="Account Info",
        params=[
            ToolParam("days_back", "integer", "How many days back to look (default 10)", required=False),
            ToolParam("status", "string", "Filter by order status", required=False),
            ToolParam("max_results", "integer", "Maximum number of orders to return", required=False),
        ],
        fn=_tool_get_all_orders,
    ),
    ToolDefinition(
        name="get_order_details",
        label="Order Details",
        description="Get full details for a specific order by ID.",
        category="Account Info",
        params=[ToolParam("order_id", "string", "The Schwab order ID")],
        fn=_tool_get_order_details,
    ),
    ToolDefinition(
        name="get_transactions",
        label="Transactions",
        description="Get account transactions (trades, dividends, etc.) over a lookback period.",
        category="Account Info",
        params=[
            ToolParam("days_back", "integer", "How many days back to look (default 30)", required=False),
            ToolParam("types", "string", "Transaction type: TRADE, RECEIVE_AND_DELIVER, DIVIDEND_OR_INTEREST, ACH_RECEIPT, ACH_DISBURSEMENT, CASH_RECEIPT, CASH_DISBURSEMENT, ELECTRONIC_FUND, WIRE_OUT, WIRE_IN, JOURNAL, MEMORANDUM, MARGIN_CALL, MONEY_MARKET, SMA_ADJUSTMENT", required=False),
            ToolParam("symbol", "string", "Optional: filter by symbol", required=False),
        ],
        fn=_tool_get_transactions,
    ),
    ToolDefinition(
        name="get_transaction_details",
        label="Transaction Details",
        description="Get full details for a specific transaction by ID.",
        category="Account Info",
        params=[ToolParam("transaction_id", "string", "The transaction ID")],
        fn=_tool_get_transaction_details,
    ),
    ToolDefinition(
        name="get_preferences",
        label="User Preferences",
        description="Get user preferences and streaming configuration.",
        category="Account Info",
        params=[],
        fn=_tool_get_preferences,
    ),
    ToolDefinition(
        name="preview_order",
        label="Preview Order",
        description="Preview an order without placing it. Use asset_type EQUITY with BUY/SELL for stocks; OPTION with BUY_TO_OPEN etc. for options.",
        category="Account Info",
        params=[
            ToolParam("symbol", "string", "Stock ticker (e.g. AAPL) or full OCC option symbol"),
            ToolParam("instruction", "string", "EQUITY: BUY or SELL. OPTION: BUY_TO_OPEN, SELL_TO_OPEN, BUY_TO_CLOSE, SELL_TO_CLOSE", enum=["BUY", "SELL", "BUY_TO_OPEN", "SELL_TO_OPEN", "BUY_TO_CLOSE", "SELL_TO_CLOSE"]),
            ToolParam("quantity", "integer", "Shares or option contracts"),
            ToolParam("price", "number", "Limit price"),
            ToolParam("asset_type", "string", "EQUITY for stock, OPTION for options", required=False, enum=["EQUITY", "OPTION"]),
        ],
        fn=_tool_preview_order,
    ),

    # ---- Skills ----
    ToolDefinition(
        name="create_stock_chart",
        label="Create Stock Chart",
        description="Fetch OHLCV price history for a symbol and display an interactive candlestick chart with volume.",
        category="Skills",
        params=[
            ToolParam("symbol", "string", "Stock ticker, e.g. SOFI"),
            ToolParam("period_type", "string", "day, month, year, or ytd", required=False, enum=["day", "month", "year", "ytd"]),
            ToolParam("period", "integer", "Number of periods (e.g. 1 month, 3 months)", required=False),
            ToolParam("frequency_type", "string", "minute, daily, weekly, or monthly", required=False, enum=["minute", "daily", "weekly", "monthly"]),
            ToolParam("frequency", "integer", "Frequency value (1, 5, 10, 15, 30 for minutes; 1 for others)", required=False),
        ],
        fn=_tool_create_stock_chart,
    ),

    # ---- Trading (disabled by default) ----
    ToolDefinition(
        name="buy_option",
        label="Buy Option",
        description="Place a BUY_TO_OPEN limit order for an option contract.",
        category="Trading",
        params=[
            ToolParam("symbol", "string", "Full OCC option symbol, e.g. SOFI  250117C00010000"),
            ToolParam("quantity", "integer", "Number of contracts"),
            ToolParam("price", "number", "Limit price per contract"),
        ],
        fn=_tool_buy_option,
        enabled_by_default=False,
    ),
    ToolDefinition(
        name="sell_option",
        label="Sell Option",
        description="Place a SELL_TO_OPEN limit order for an option contract.",
        category="Trading",
        params=[
            ToolParam("symbol", "string", "Full OCC option symbol"),
            ToolParam("quantity", "integer", "Number of contracts"),
            ToolParam("price", "number", "Limit price per contract"),
        ],
        fn=_tool_sell_option,
        enabled_by_default=False,
    ),
    ToolDefinition(
        name="buy_stock",
        label="Buy Stock",
        description="Place a BUY limit order for shares of a stock (EQUITY).",
        category="Trading",
        params=[
            ToolParam("symbol", "string", "Stock ticker, e.g. AAPL"),
            ToolParam("quantity", "integer", "Number of shares"),
            ToolParam("price", "number", "Limit price per share"),
        ],
        fn=_tool_buy_stock,
        enabled_by_default=False,
    ),
    ToolDefinition(
        name="sell_stock",
        label="Sell Stock",
        description="Place a SELL limit order for shares of a stock (EQUITY).",
        category="Trading",
        params=[
            ToolParam("symbol", "string", "Stock ticker, e.g. AAPL"),
            ToolParam("quantity", "integer", "Number of shares"),
            ToolParam("price", "number", "Limit price per share"),
        ],
        fn=_tool_sell_stock,
        enabled_by_default=False,
    ),
    ToolDefinition(
        name="cancel_order",
        label="Cancel Order",
        description="Cancel an open order by its order ID.",
        category="Trading",
        params=[ToolParam("order_id", "string", "The Schwab order ID to cancel")],
        fn=_tool_cancel_order,
        enabled_by_default=False,
    ),
    ToolDefinition(
        name="replace_order",
        label="Replace Order",
        description="Replace an existing order. Match asset_type to the original order (EQUITY vs OPTION).",
        category="Trading",
        params=[
            ToolParam("order_id", "string", "The Schwab order ID to replace"),
            ToolParam("symbol", "string", "Stock ticker or OCC option symbol"),
            ToolParam("instruction", "string", "EQUITY: BUY or SELL. OPTION: BUY_TO_OPEN, SELL_TO_OPEN, BUY_TO_CLOSE, SELL_TO_CLOSE", enum=["BUY", "SELL", "BUY_TO_OPEN", "SELL_TO_OPEN", "BUY_TO_CLOSE", "SELL_TO_CLOSE"]),
            ToolParam("quantity", "integer", "Shares or contracts"),
            ToolParam("price", "number", "New limit price"),
            ToolParam("asset_type", "string", "EQUITY or OPTION", required=False, enum=["EQUITY", "OPTION"]),
        ],
        fn=_tool_replace_order,
        enabled_by_default=False,
    ),
]

# Convenience lookup
_TOOL_MAP: dict[str, ToolDefinition] = {t.name: t for t in ALL_TOOLS}


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

def execute_tool(name: str, arguments: dict, enabled_names: set[str]) -> Any:
    """
    Look up and call a tool by name.
    Raises ValueError if the tool is not enabled or does not exist.
    Returns a JSON-serialisable value.
    """
    if name not in enabled_names:
        raise ValueError(f"Tool '{name}' is not enabled.")
    tool = _TOOL_MAP.get(name)
    if tool is None:
        raise ValueError(f"Unknown tool: '{name}'")
    # Filter out None values for optional params so defaults apply
    filtered = {k: v for k, v in arguments.items() if v is not None}
    return tool.fn(**filtered)
