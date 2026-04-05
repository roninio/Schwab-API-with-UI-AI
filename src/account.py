from datetime import datetime, timedelta
import schwabdev


class AccountInfo:

    account = None
    account_hash = None
    client = None

    def __init__(self, client: schwabdev.Client):
        self.client = client
        acc = client.linked_accounts().json()
        self.account = acc[0]["accountNumber"]
        self.account_hash = acc[0]["hashValue"]

    def get_positions(self):
        print(
            "|\n|client.account_details(account_hash, fields='positions').json()",
            end="\n|",
        )
        print(self.client.account_details(self.account_hash, fields="positions").json())

        print("\n\nAccounts and Trading - Orders (in Schwab API documentation)")

        return self.client.account_details(self.account_hash, fields="positions").json()

    def get_orders(self, days_to_lookback=20) -> list:
        now = datetime.now()
        lookback_period = timedelta(days=days_to_lookback)
        from_entered_time = now - lookback_period
        res = self.client.account_orders(
            accountHash=self.account_hash,
            maxResults=55,
            fromEnteredTime=from_entered_time,
            toEnteredTime=now,
        ).json()
        return res
