from trader import Trader
from signals.signal_generator import get_signal

def run_bot():
    trader = Trader()
    signal = get_signal()

    if signal == "buy":
        trader.buy()
    elif signal == "sell":
        trader.sell()
    else:
        print("No action")