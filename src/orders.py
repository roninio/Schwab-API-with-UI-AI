from enum import Enum
import json
import logging
import src.app_logging_config as log_conf

import schwabdev
from requests.exceptions import (
    ConnectionError,
    Timeout,
    TooManyRedirects,
    RequestException,
)


logging = log_conf.loger()

logger = logging


class SubmitOrders:

    client = None
    account_hash = None
    order_id = None

    def __init__(self, client: schwabdev.Client):
        self.client = client

    def get_order(self, order_id, account_hash):
        # get specific order details
        # print("|\n|client.order_details(account_hash, order_id).json()", end="\n|")
        res = self.client.order_details(account_hash, order_id).json()
        return res

    def place_order(
        self,
        symbol,
        account_hash,
        price,
        instruction,
        quantity=1,
    ):

        # place order
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
                    "instrument": {
                        "symbol": "{symbol}".format(symbol=symbol),
                        "assetType": "OPTION",
                    },
                }
            ],
        }
        # print(order)
        # exit()
        resp = self.client.place_order(account_hash, order)
        # print("|\n|client.place_order(self.account_hash, order).json()", end="\n|")
        logger.debug(f"Response code: {resp}")
        # get the order ID - if order is immediately filled then the id might not be returned
        order_id = resp.headers.get("location", "/").split("/")[-1]
        self.order_id = order_id
        logger.debug(f"Order id: {order_id}")
        return order_id

    def cancel_order(self, order_id, account_hash):
        # cancel specific order
        retries = 2
        for i in range(retries):

            try:

                respone = self.client.cancel_order(account_hash, order_id)
            except (ConnectionError, Timeout, TooManyRedirects) as err:
                logger.info(f"Request error occurred: {err}, retrying...")
            else:

                break
        if respone.status_code == 200:
            logger.info(f"Cancel order successful. {order_id} ")
            return True
        else:
            logger.info(f"Cancel order unsuccessful. {order_id} ")
            return False
