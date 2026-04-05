import json
from typing import Any

import numpy as np
import pandas as pd

from src.client import get_client


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


def get_spx_candles_dataframe():
    client = get_client()
    messages: list[str] = []

    for symbol in ("$SPX", "SPX"):
        resp = client.price_history(
            symbol, periodType="day", period="10", frequencyType="minute", frequency=10
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
        "No candle data for the S&P 500 chart (tried $SPX and SPX). "
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
        "title": {"text": "SPX — candlestick & MA30"},
        "chart": {"height": 640},
        "rangeSelector": {"selected": 2},
        "series": [
            {"type": "candlestick", "name": "SPX", "id": "spx", "data": ohlc},
            {"type": "line", "name": "MA30", "data": ma30, "lineWidth": 1.5, "color": "#2980b9"},
        ],
    }


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
            "text": "SPX",
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
