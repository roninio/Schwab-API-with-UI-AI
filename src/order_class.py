import datetime
from enum import Enum


class OrderType(Enum):
    SELL = "SELL_TO_OPEN"
    BUY = "BUY_TO_CLOSE"


class OrderStatus(Enum):
    FILLED = 1
    CANCELED = 2
    REJECTED = 3
    WORKING = 4
    FAILED = 10  # no Buyer found for order


class OrderData:
    order_type: OrderType = None
    price: float = 0
    current_datetime: datetime
    approved = False
    quantity = 1
    account_hash = 0
    symbol = None
    instruction = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        # self.kwargs = kwargs
        self.current_datetime = datetime.datetime.now()

    def __str__(self) -> str:
        return f"OrderData(order_type={self.order_type}, price={self.price},amount={self.quantity}, datetime={self.current_datetime} instuction {self.instruction})"

    def __eq__(self, other):
        if isinstance(other, OrderData):
            return self.order_type == other.order_type and self.price == other.price
        return False

    def to_list(self):
        return [
            self.current_datetime,
            self.order_type,
            self.symbol,
            self.price,
            self.quantity,
            self.instruction,
        ]
