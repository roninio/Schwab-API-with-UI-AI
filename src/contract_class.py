import datetime
from enum import Enum


class OptionContractType(Enum):
    CALL = "CALL"
    PUT = "PUT"


class OptionContract:
    putCall: OptionContractType = None
    bid: float = 0
    ask: float = 0
    symbol = ""
    strikePrice: float = 0
    experationDate = ""
    daysToExiration = 0
    putCall = ""
    sigma_sum = 0
    current_datetime = None

    def __init__(
        self,
        **kwargs,
    ):
        for key, value in kwargs.items():
            # print(key, value)
            setattr(self, key, value)
        self.current_datetime = datetime.datetime.now()

    def get_symbol(self):
        split = self.symbol.split(" ")
        return split[0]

    def __str__(self) -> str:
        return f"Contract {self.symbol} {self.strikePrice} (putCall={self.putCall}, bid={self.bid},ask={self.ask} )"

    def compare_to(self, other_contract):
        diff_attrs = []
        for attr in [
            "strikePrice",
            "symbol",
            "ask",
            "bid",
            "daysToExiration",
            "putCall",
        ]:
            if not callable(getattr(self, attr)) and not attr.startswith("__"):
                if getattr(self, attr) != getattr(other_contract, attr):
                    diff_attrs.append(attr)
        return diff_attrs

    @staticmethod
    def dataframe_row_to_dict(input_contract):
        """
        input is expected to be a DataFrame with a single row, and the function returns a dictionary containing the same information.
        """
        values = input_contract.values.tolist()
        keys = input_contract.columns.values.tolist()
        dictionary = dict(zip(keys, values[0]))
        return dictionary

    def to_list(self):
        return [
            self.current_datetime,
            self.putCall,
            self.symbol,
            self.description,
            self.exchangeName,
            self.bid,
            self.ask,
            self.last,
            self.mark,
            self.bidSize,
            self.askSize,
            self.bidAskSize,
            self.lastSize,
            self.highPrice,
            self.lowPrice,
            self.openPrice,
            self.closePrice,
            self.totalVolume,
            self.tradeTimeInLong,
            self.quoteTimeInLong,
            self.netChange,
            self.volatility,
            self.delta,
            self.gamma,
            self.theta,
            self.vega,
            self.rho,
            self.openInterest,
            self.timeValue,
            self.theoreticalOptionValue,
            self.theoreticalVolatility,
            self.optionDeliverablesList,
            self.strikePrice,
            self.expirationDate,
            self.daysToExpiration,
            self.expirationType,
            self.lastTradingDay,
            self.multiplier,
            self.settlementType,
            self.deliverableNote,
            self.percentChange,
            self.markChange,
            self.markPercentChange,
            self.intrinsicValue,
            self.extrinsicValue,
            self.optionRoot,
            self.exerciseType,
            self.high52Week,
            self.low52Week,
            self.pennyPilot,
            self.inTheMoney,
            self.mini,
            self.nonStandard,
            self.experationDate,
            self.sigma_sum,
        ]
