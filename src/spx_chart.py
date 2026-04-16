import json
import threading
import time
from collections import deque
from typing import Any

import numpy as np
import pandas as pd

from src.client import create_client, get_client


def _normalize_candle_row(candle: dict[str, Any]) -> dict[str, Any]:
    return {str(k).lower(): v for k, v in candle.items()}


def _errors_summary(errors: Any) -> str:
    if not errors:
        return "unknown error"
    first = errors[0] if isinstance(errors, list) and errors else errors
    if isinstance(first, dict):
        return str(
            first.get("description")
            or first.get("msg")
            or first.get("error")
            or first.get("status")
            or first
        )
    return str(first)


def _time_column_to_utc_seconds(df: pd.DataFrame) -> pd.DataFrame:
    """Lightweight Charts expects ``time`` as UTCTimestamp (Unix seconds). Schwab uses ms."""
    out = df.copy()
    t = pd.to_numeric(out["time"], errors="coerce").astype("int64")
    out["time"] = np.where(t > 10**12, t // 1000, t).astype(int)
    return out


def get_spx_candles_dataframe(
    *,
    period_type: str = "day",
    period: str = "1",
    frequency_type: str = "minute",
    frequency: int = 1,
):
    client = get_client()
    messages: list[str] = []

    for symbol in ("GOOG",):
        resp = client.price_history(
            symbol,
            periodType=period_type,
            period=period,
            frequencyType=frequency_type,
            frequency=frequency,
        )
        if not resp.ok:
            messages.append(f"{symbol}: HTTP {resp.status_code}")
            continue

        body = resp.json()
        if body.get("errors"):
            messages.append(f"{symbol}: {_errors_summary(body['errors'])}")
            continue

        candles_data = body.get("candles")
        if candles_data is None:
            raise ValueError(
                f"Price history for {symbol} has no 'candles' key. "
                f"Response keys: {list(body.keys())}."
            )
        if not isinstance(candles_data, list):
            raise ValueError(
                f"Price history 'candles' for {symbol} is not a list (got {type(candles_data).__name__})."
            )
        if len(candles_data) == 0:
            messages.append(f"{symbol}: no candles returned")
            continue

        transformed_data: list[dict[str, Any]] = []
        for candle in candles_data:
            if not isinstance(candle, dict):
                raise ValueError(
                    f"Expected each candle to be a dict for {symbol}; got {type(candle).__name__}."
                )
            norm = _normalize_candle_row(candle)
            if "datetime" not in norm:
                raise ValueError(
                    f"Candle missing 'datetime' for {symbol}. Keys after normalize: {sorted(norm.keys())}."
                )
            new_entry = dict(norm)
            new_entry["time"] = norm["datetime"]
            transformed_data.append(new_entry)

        df = pd.DataFrame(transformed_data)
        required = ("open", "high", "low", "close", "volume")
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing OHLCV columns for {symbol}: {missing}. "
                f"Got columns: {list(df.columns)}."
            )
        if df.empty:
            messages.append(f"{symbol}: empty dataframe after parse")
            continue

        df["mfm"] = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / np.where(
            df["high"] != df["low"], df["high"] - df["low"], 1
        )
        df["mfv"] = df["mfm"] * df["volume"]
        volume_sum = df["volume"].rolling(window=20, min_periods=1).sum()
        df["cmf"] = np.where(
            volume_sum != 0,
            df["mfv"].rolling(window=20, min_periods=1).sum() / volume_sum,
            0,
        )
        df["ma30"] = df["close"].rolling(window=30, min_periods=1).mean()
        return df

    raise ValueError(
        "No candle data for the Google chart (tried GOOG). "
        + " ".join(messages)
        + " Try during regular market hours for intraday data, or refresh after checking API access."
    )


def _candle_time_to_epoch_ms(df: pd.DataFrame) -> np.ndarray:
    """Schwab / dataframe ``time`` may be ms or seconds; Highcharts Stock wants ms."""
    t = pd.to_numeric(df["time"], errors="coerce").astype("int64").to_numpy()
    return np.where(t > 10**12, t, t * 1000).astype(int)


def highcharts_stock_options() -> dict[str, Any]:
    """Options dict for ``ui.highchart(..., type='stockChart', extras=['stock'])``."""
    df = get_spx_candles_dataframe()
    t_ms = _candle_time_to_epoch_ms(df)

    ohlc: list[list[Any]] = []
    for i in range(len(df)):
        ohlc.append(
            [
                int(t_ms[i]),
                float(df["open"].iloc[i]),
                float(df["high"].iloc[i]),
                float(df["low"].iloc[i]),
                float(df["close"].iloc[i]),
            ]
        )

    ma30: list[list[Any]] = []
    for i in range(len(df)):
        v = df["ma30"].iloc[i]
        if pd.notna(v):
            ma30.append([int(t_ms[i]), float(v)])

    return {
        "title": {"text": "GOOG — live (1m candles) & MA30"},
        "chart": {"height": 640},
        "rangeSelector": {"selected": 2},
        "series": [
            {"type": "candlestick", "name": "GOOG", "id": "goog", "data": ohlc},
            {"type": "line", "name": "MA30", "data": ma30, "lineWidth": 1.5, "color": "#2980b9"},
        ],
    }


def get_spx_quote_snapshot() -> dict[str, Any] | None:
    """Best-effort real-time-ish quote snapshot for GOOG stats labels."""
    client = get_client()
    for symbol in ("GOOG",):
        try:
            resp = client.quote(symbol)
            if not resp.ok:
                continue
            body = resp.json()
            if not isinstance(body, dict) or not body:
                continue

            # Schwab quote response can vary by instrument type; search common sections.
            record = body.get(symbol) if symbol in body else next(iter(body.values()))
            if not isinstance(record, dict):
                continue
            quote = record.get("quote", {}) if isinstance(record.get("quote"), dict) else {}
            ref = (
                record.get("reference", {})
                if isinstance(record.get("reference"), dict)
                else {}
            )

            last_price = quote.get("lastPrice", quote.get("mark", quote.get("closePrice")))
            if last_price is None:
                continue
            last_price = float(last_price)

            prev_close = quote.get("closePrice")
            day_change = None
            if prev_close is not None:
                day_change = float(last_price - float(prev_close))

            quote_time_ms = (
                quote.get("quoteTime")
                or quote.get("tradeTime")
                or ref.get("quoteTime")
                or int(time.time() * 1000)
            )

            return {
                "last_price": last_price,
                "day_change": day_change,
                "quote_time_ms": int(float(quote_time_ms)),
            }
        except Exception:
            continue
    return None


def apply_live_price_to_highcharts_options(
    options: dict[str, Any], *, last_price: float, quote_time_ms: int
) -> bool:
    """Apply streamed quote to the existing Highcharts options in-place."""
    if not options.get("series"):
        return False
    if not np.isfinite(last_price):
        return False

    ohlc = options["series"][0].get("data", [])
    if not isinstance(ohlc, list):
        return False

    bucket_ms = int((int(quote_time_ms) // 60_000) * 60_000)
    p = float(last_price)

    if not ohlc:
        ohlc.append([bucket_ms, p, p, p, p])
    else:
        last = ohlc[-1]
        if not isinstance(last, list) or len(last) < 5:
            return False
        last_t = int(last[0])
        if bucket_ms == last_t:
            last[2] = max(float(last[2]), p)  # high
            last[3] = min(float(last[3]), p)  # low
            last[4] = p  # close
        elif bucket_ms > last_t:
            prev_close = float(last[4])
            ohlc.append(
                [
                    bucket_ms,
                    prev_close,
                    max(prev_close, p),
                    min(prev_close, p),
                    p,
                ]
            )
        else:
            return False

    closes = [float(c[4]) for c in ohlc if isinstance(c, list) and len(c) >= 5]
    ma_data: list[list[Any]] = []
    for idx, candle in enumerate(ohlc):
        if not isinstance(candle, list) or len(candle) < 5:
            continue
        start = max(0, idx - 29)
        ma = float(sum(closes[start : idx + 1]) / (idx - start + 1))
        ma_data.append([int(candle[0]), ma])
    if len(options["series"]) > 1:
        options["series"][1]["data"] = ma_data

    return True


class SpxLiveStream:
    """Thread-safe bridge from schwabdev stream callbacks to UI polling."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buffer: deque[dict[str, Any]] = deque(maxlen=1)
        self._stream: Any | None = None
        self._started = False

    @staticmethod
    def _first_float(row: dict[str, Any], keys: list[str]) -> float | None:
        for key in keys:
            value = row.get(key)
            try:
                if value is not None and value != "":
                    return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _first_int(row: dict[str, Any], keys: list[str]) -> int | None:
        for key in keys:
            value = row.get(key)
            try:
                if value is not None and value != "":
                    return int(float(value))
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _extract_quote(data: dict[str, Any]) -> dict[str, Any] | None:
        payload = data.get("data", [])
        if not isinstance(payload, list):
            return None
        for item in payload:
            if not isinstance(item, dict):
                continue
            if item.get("service") != "LEVELONE_EQUITIES":
                continue
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for row in content:
                if not isinstance(row, dict):
                    continue
                key = str(row.get("key") or "").upper()
                if key not in {"GOOG"}:
                    continue
                last_price = SpxLiveStream._first_float(row, ["3", "2", "1"])
                if last_price is None:
                    continue
                # Try known net-change fields; if unavailable, keep None.
                day_change = SpxLiveStream._first_float(row, ["28", "18", "10", "7"])
                quote_time_ms = SpxLiveStream._first_int(row, ["35", "34", "17", "36"])
                if quote_time_ms is None:
                    quote_time_ms = int(time.time() * 1000)
                return {
                    "last_price": last_price,
                    "day_change": day_change,
                    "quote_time_ms": quote_time_ms,
                }
        return None

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            client = create_client(timeout=9)
            self._stream = client.stream

            def _receiver(message: Any) -> None:
                try:
                    parsed = json.loads(message) if isinstance(message, str) else message
                    if not isinstance(parsed, dict):
                        return
                    quote = self._extract_quote(parsed)
                    if quote is not None:
                        with self._lock:
                            self._buffer.append(quote)
                except Exception:
                    return

            req = self._stream.level_one_equities(keys=["GOOG"], fields="0,1,2,3,4,5")
            self._stream.send(req)
            self._stream.start(receiver=_receiver, daemon=True)
            self._started = True

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
            self._started = False
            self._buffer.clear()
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass

    def consume_latest(self) -> dict[str, Any] | None:
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer.pop()


_spx_live_stream = SpxLiveStream()


def get_spx_live_stream() -> SpxLiveStream:
    return _spx_live_stream


def lightweight_charts_payload():
    """Return chart options and series as JSON for TradingView lightweight-charts."""
    df = _time_column_to_utc_seconds(get_spx_candles_dataframe())
    data_list = df.to_dict("records")

    chart_options = {
        "height": 690,
        "layout": {"textColor": "black", "background": {"type": "solid", "color": "white"}},
        "watermark": {
            "visible": True,
            "fontSize": 48,
            "horzAlign": "center",
            "vertAlign": "center",
            "color": "rgba(171, 71, 188, 0.3)",
            "text": "GOOG",
        },
    }

    series = [
        {
            "type": "Candlestick",
            "data": data_list,
            "options": {
                "upColor": "#26a69a",
                "downColor": "#ef5350",
                "borderVisible": False,
                "wickUpColor": "#26a69a",
                "wickDownColor": "#ef5350",
            },
        },
        {
            "type": "Line",
            "data": df[["time", "ma30"]]
            .rename(columns={"ma30": "value"})
            .dropna()
            .to_dict("records"),
            "options": {"color": "blue"},
        },
        {
            "type": "Histogram",
            "data": df[["time", "cmf"]]
            .rename(columns={"cmf": "value"})
            .fillna(0.0)
            .to_dict("records"),
            "options": {
                "color": "#26a69a",
                "priceFormat": {"type": "volume"},
                "priceScaleId": "",
            },
            "priceScale": {"scaleMargins": {"top": 0.7, "bottom": 0}},
        },
    ]
    return chart_options, series


LIGHTWEIGHT_CHARTS_CDN_SRC = (
    "https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"
)


def lightweight_charts_container_html(element_id: str = "spx_chart_root") -> str:
    """Markup safe for NiceGUI ``ui.html`` (no ``<script>`` tags)."""
    return f'<div id="{element_id}" style="width:100%;height:690px;"></div>'


def lightweight_charts_mount_javascript(element_id: str = "spx_chart_root") -> str:
    """Client-side bootstrap + chart mount. Run with ``await ui.run_javascript(...)``."""
    chart_options, series_list = lightweight_charts_payload()
    opts = json.dumps(chart_options)
    series_json = json.dumps(series_list)
    lw_src = json.dumps(LIGHTWEIGHT_CHARTS_CDN_SRC)
    eid = json.dumps(element_id)
    return f"""
return (async () => {{
  const LW_SRC = {lw_src};
  const elementId = {eid};
  if (typeof LightweightCharts === 'undefined') {{
    if (!window.__spxLWChartLoadP) {{
      window.__spxLWChartLoadP = new Promise((resolve, reject) => {{
        const s = document.createElement('script');
        s.src = LW_SRC;
        s.onload = () => resolve(undefined);
        s.onerror = () => reject(new Error('Failed to load LightweightCharts'));
        document.head.appendChild(s);
      }});
    }}
    await window.__spxLWChartLoadP;
  }}
  if (typeof LightweightCharts === 'undefined') {{
    throw new Error('LightweightCharts is not available after load');
  }}
  const container = document.getElementById(elementId);
  if (!container) {{
    throw new Error('Chart container not found: #' + elementId + ' (DOM not ready?)');
  }}
  if (window.__spxLWChart) {{
    try {{ window.__spxLWChart.remove(); }} catch (e) {{}}
    window.__spxLWChart = null;
  }}
  if (window.__spxLWChartRO) {{
    try {{ window.__spxLWChartRO.disconnect(); }} catch (e) {{}}
    window.__spxLWChartRO = null;
  }}
  const options = {opts};
  const chart = LightweightCharts.createChart(container, {{
    width: container.clientWidth,
    height: options.height || 690,
    layout: options.layout,
    watermark: options.watermark,
  }});
  window.__spxLWChart = chart;
  const seriesArr = {series_json};
  for (const spec of seriesArr) {{
    if (spec.type === 'Candlestick') {{
      const s = chart.addCandlestickSeries(spec.options || {{}});
      s.setData(spec.data.map(d => ({{
        time: d.time, open: d.open, high: d.high, low: d.low, close: d.close
      }})));
    }} else if (spec.type === 'Line') {{
      const s = chart.addLineSeries(spec.options || {{}});
      s.setData(spec.data);
    }} else if (spec.type === 'Histogram') {{
      const s = chart.addHistogramSeries(spec.options || {{}});
      if (spec.priceScale) {{
        s.priceScale().applyOptions(spec.priceScale);
      }}
      s.setData(spec.data);
    }}
  }}
  window.__spxLWChartRO = new ResizeObserver(() => {{
    chart.applyOptions({{ width: container.clientWidth }});
  }});
  window.__spxLWChartRO.observe(container);
}})();
"""
