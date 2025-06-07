import os, ccxt, time, logging, json, csv
from datetime import datetime

# === Setup ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
exchange = ccxt.okx({
    'apiKey': os.getenv("OKX_API_KEY"),
    'secret': os.getenv("OKX_API_SECRET"),
    'password': os.getenv("OKX_API_PASSPHRASE"),
    'enableRateLimit': True,
    'options': {"defaultType": "future"}
})

# === Config ===
SYMBOLS = ['BTC/USDT']
TIMEFRAME = '1m'
RSI_PERIOD = 14
EMA_PERIOD = 50
VOL_THRESHOLD = 0.002
MIN_VOL = 10
MAX_HOLD = 120
TRAIL_TRIGGER = 0.003
MAX_LOSSES = 2
BASE_PERCENT = 0.025
STATE_FILE = 'state.json'
LOG_FILE = 'trades.csv'

# === Load Bot State ===
def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'wins': 0, 'losses': 0, 'last_trade': None}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

state = load_state()

# === Logging to CSV ===
def log_trade(symbol, side, size, entry, exit_price, pnl):
    with open(LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.utcnow(), symbol, side, size, entry, exit_price, pnl])

# === Market Analysis ===
def fetch_data(symbol):
    candles = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=EMA_PERIOD + 1)
    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    vols = [c[5] for c in candles]
    return closes, highs, lows, vols

def get_rsi(closes):
    deltas = [closes[i+1] - closes[i] for i in range(len(closes)-1)]
    gain = sum(d for d in deltas if d > 0) / RSI_PERIOD
    loss = -sum(d for d in deltas if d < 0) / RSI_PERIOD
    rs = gain / loss if loss != 0 else 100
    return 100 - (100 / (1 + rs))

def is_market_favorable(closes, highs, lows, vols):
    price = closes[-1]
    ema = sum(closes[-EMA_PERIOD:]) / EMA_PERIOD
    volatility = (max(highs[-5:]) - min(lows[-5:])) / price
    avg_vol = sum(vols[-5:]) / 5
    trend = 'bull' if price > ema else 'bear'
    return trend, volatility > VOL_THRESHOLD, avg_vol > MIN_VOL

# === Trade Logic ===
def get_trade_size(balance, price):
    tier = 0.025 if balance < 25 else 0.05 if balance < 150 else 0.1
    confidence = 1.2 if state['wins'] >= 3 else 1
    return round((balance * tier * confidence) / price, 4)

def execute_trade(symbol, side, amount):
    try:
        return exchange.create_market_order(symbol, side, amount)
    except Exception as e:
        logging.error(f"Trade failed: {e}")
        return None

def run_bot():
    global state

    while True:
        try:
            utc_hour = datetime.utcnow().hour
            if utc_hour in [0, 1, 2, 3]:
                logging.info("Low-volume hours. Sleeping 10 mins.")
                time.sleep(600)
                continue

            for symbol in SYMBOLS:
                balance = exchange.fetch_balance()['total']['USDT']
                if balance < 10:
                    logging.warning("Low balance. Sleeping 5 mins.")
                    time.sleep(300)
                    continue

                closes, highs, lows, vols = fetch_data(symbol)
                rsi = get_rsi(closes)
                trend, volatility_ok, volume_ok = is_market_favorable(closes, highs, lows, vols)

                logging.info(f"{symbol} | RSI: {rsi:.2f} | Trend: {trend} | Vol OK: {volatility_ok} | Volume OK: {volume_ok}")

                signal = None
                if rsi < 30 and trend == 'bull' and volatility_ok and volume_ok:
                    signal = 'buy'
                elif rsi > 70 and trend == 'bear' and volatility_ok and volume_ok:
                    signal = 'sell'

                if not signal:
                    logging.info("No signal, skipping.")
                    time.sleep(30)
                    continue

                price = exchange.fetch_ticker(symbol)['last']
                size = get_trade_size(balance, price)
                order = execute_trade(symbol, signal, size)

                if not order:
                    continue

                entry_price = order['average']
                logging.info(f"Entered {signal.upper()} {symbol} @ {entry_price}")
                exit_side = 'sell' if signal == 'buy' else 'buy'
                trail_stop = entry_price - entry_price * TRAIL_TRIGGER if signal == 'buy' else entry_price + entry_price * TRAIL_TRIGGER
                start = time.time()

                while time.time() - start < MAX_HOLD:
                    current = exchange.fetch_ticker(symbol)['last']
                    if signal == 'buy' and current > entry_price:
                        trail_stop = max(trail_stop, current - current * TRAIL_TRIGGER)
                    elif signal == 'sell' and current < entry_price:
                        trail_stop = min(trail_stop, current + current * TRAIL_TRIGGER)

                    # Exit logic
                    if (signal == 'buy' and current <= trail_stop) or (signal == 'sell' and current >= trail_stop):
                        result = execute_trade(symbol, exit_side, size)
                        pnl = (current - entry_price) if signal == 'buy' else (entry_price - current)
                        logging.info(f"Exited at {current:.2f} | PnL: {pnl:.4f}")
                        log_trade(symbol, signal, size, entry_price, current, pnl)
                        if pnl > 0:
                            state['wins'] += 1
                            state['losses'] = 0
                        else:
                            state['losses'] += 1
                            state['wins'] = 0
                        save_state(state)
                        break
                    time.sleep(10)

                else:
                    # Timed exit
                    result = execute_trade(symbol, exit_side, size)
                    current = exchange.fetch_ticker(symbol)['last']
                    pnl = (current - entry_price) if signal == 'buy' else (entry_price - current)
                    logging.warning(f"TIMEOUT Exit at {current:.2f} | PnL: {pnl:.4f}")
                    log_trade(symbol, signal, size, entry_price, current, pnl)
                    if pnl > 0:
                        state['wins'] += 1
                        state['losses'] = 0
                    else:
                        state['losses'] += 1
                        state['wins'] = 0
                    save_state(state)

                # Pause after loss streak
                if state['losses'] >= MAX_LOSSES:
                    logging.warning("2 losses in a row — pausing to study market.")
                    while True:
                        closes, highs, lows, vols = fetch_data(symbol)
                        trend, volatility_ok, volume_ok = is_market_favorable(closes, highs, lows, vols)
                        if volatility_ok and volume_ok:
                            logging.info("Market favorable again. Resuming.")
                            state['losses'] = 0
                            save_state(state)
                            break
                        time.sleep(60)

                time.sleep(30)

        except Exception as e:
            logging.error(f"Fatal error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
