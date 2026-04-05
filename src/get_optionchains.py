import concurrent.futures
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import os
import schwabdev
import numpy as np

os.environ["PYDEVD_INTERRUPT_THREAD_TIMEOUT"] = "30"

import math

symbol_price = 0

ORDERS_CSV_PATH = Path(__file__).resolve().parent.parent / "orders.csv"






class Get_option_chain:

    client: schwabdev.Client = None
    symbol_price = 0
    netPercentChange = 0
    filter_options = True

    def __init__(self, client) -> None:
        self.client = client

    @property
    def filter_optionchains(self) -> bool:
        return self.filter_options

    @filter_optionchains.setter
    def filter_optionchains(self, value: bool) -> None:
        self.filter_options = value

    def _filter_data(self, b):
        """Filter rows not relevant return true to filter the row"""
      
        if b["inTheMoney"] == True:
            return True
        if b["bidSize"] < 10 or b["askSize"] < 10:
            return True
      
    def _create_options_list(self, data, filter=True):
        df = pd.DataFrame()
        callExpDateMap = list(data)
        for extDate in callExpDateMap:
            for a in data[extDate]:
                for b in data[extDate][a]:
                    if self.filter_options == True:
                        if self._filter_data(b) == True:
                            continue

                    b["experationDate"] = extDate
                    b["optionDeliverablesList"] = 0
                    
                    if len(df) == 0:
                        df = pd.DataFrame(b, index=[0])
                    else:
                        df.loc[len(df)] = b
        return df

    def get_symbol(self, symbol="SOFI"):
        try:
            symbol_res = self.client.quote(symbol).json()
            print("Percentage change", symbol_res[symbol]["quote"]["netPercentChange"])
            return symbol_res[symbol]["quote"]["netPercentChange"]
        except:
            return "error try again " + symbol

    def get_option(self, **kwargs) -> pd:

        pass

    def get_options(self, symbol="SOFI", numdays_start= 1, numdays_end=30) -> pd:
        global symbol_price
        symbol = symbol.upper()
        symbol = symbol.strip()

        netPercentChange = self.get_symbol(symbol=symbol)

        today = datetime.now()
        future_date = today 
        future_date = future_date.strftime("%Y-%m-%d")

        toDate = today + timedelta(days=numdays_end)
        toDate = toDate.strftime("%Y-%m-%d")
        print(future_date, toDate)
        try:
            res = self.client.option_chains(
                symbol=symbol, fromDate=future_date, toDate=toDate
            ).json()
            symbol_price = res["underlyingPrice"]
            print(res["symbol"], symbol_price)
            self.netPercentChange = netPercentChange
            self.symbol_price = symbol_price
            call_options = res["callExpDateMap"]
            put_options = res["putExpDateMap"]
            call_df = self._create_options_list(call_options)
            puts_df = self._create_options_list(put_options)
            frames = [call_df, puts_df]
            if len(frames) == 0 or (len(call_df) == 0 and len(puts_df) == 0):
                print("No Strikes found")
                return pd.DataFrame([["No striks found "]], columns=["Result"])

        except Exception as e:  # Catches any other exception
            print("Unexpected error:", e)
            return "Error found"

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
            "intrinsicValue",
        ]
        frames1 = pd.concat(frames)

        return frames1[columns_to_print]

    def load_contracts_from_csv(self, days_to_load: int = 0) -> list:
        orders: list = []
        if not ORDERS_CSV_PATH.is_file():
            return orders
        today = datetime.now() - timedelta(days=days_to_load)
        with open(ORDERS_CSV_PATH, "r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) < 3:
                    continue
                try:
                    given_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    continue
                if given_date.date() == today.date():
                    orders.append(row[2])
        return list(set(orders))

    def get_list_symbols(self, list_symbols: list[str]) -> pd.DataFrame:
        """Fetch option chains for many tickers and concatenate into one DataFrame."""
        syms = [
            (s or "").strip().upper()
            for s in list_symbols
            if (s or "").strip()
        ]
        if not syms:
            return pd.DataFrame()
        max_workers = min(len(syms), 12) or 1
        list_frames: list[pd.DataFrame] = []

        def _fetch_one(symbol: str) -> pd.DataFrame:
            df = self.get_options(symbol=symbol)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return pd.DataFrame()
            if list(df.columns) == ["Result"]:
                return pd.DataFrame()
            return df

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch_one, sym): sym for sym in syms}
            for fut in concurrent.futures.as_completed(futures):
                try:
                    piece = fut.result()
                except Exception:
                    continue
                if isinstance(piece, pd.DataFrame) and not piece.empty:
                    list_frames.append(piece)
        if not list_frames:
            return pd.DataFrame()
        return pd.concat(list_frames, ignore_index=True)
