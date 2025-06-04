import os

class Trader:
    def __init__(self):
        self.api_key = os.getenv("OKX_API_KEY")
        self.secret_key = os.getenv("OKX_SECRET_KEY")
        self.passphrase = os.getenv("OKX_PASSPHRASE")
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    def buy(self):
        if self.dry_run:
            print("Simulated BUY order")
        else:
            print("Real BUY order placed")

    def sell(self):
        if self.dry_run:
            print("Simulated SELL order")
        else:
            print("Real SELL order placed")