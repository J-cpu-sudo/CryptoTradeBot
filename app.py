import os
import logging
import threading
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configure the database
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    # Default to SQLite for local development
    database_url = "sqlite:///trading_bot.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

# Initialize scheduler for bot operations
scheduler = BackgroundScheduler()
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

with app.app_context():
    # Import models and routes
    import models  # noqa: F401
    import routes  # noqa: F401
    
    # Create all database tables
    db.create_all()
    
    # Set up context manager
    from context_manager import set_app_instance
    set_app_instance(app)
    
    # Initialize autonomous trading fix
    import autonomous_context_fix
    
    # Initialize enhanced bot manager
    from bot_manager import BotManager
    bot_manager = BotManager(db, scheduler)
    app.bot_manager = bot_manager
    
    # Auto-start the autonomous trading bot
    try:
        if bot_manager.status.value != 'running':
            logging.info("Starting autonomous trading bot on app initialization...")
            success = bot_manager.start()
            if success:
                logging.info("Autonomous trading bot started successfully")
            else:
                logging.error("Failed to start autonomous trading bot")
    except Exception as e:
        logging.error(f"Error starting autonomous trading bot: {e}")
    
    # Initialize real-time dashboard
    from realtime_dashboard import RealtimeDashboard, realtime_bp
    dashboard_manager = RealtimeDashboard(socketio)
    dashboard_manager.start_realtime_updates()
    app.dashboard_manager = dashboard_manager
    
    # Register real-time dashboard blueprint
    app.register_blueprint(realtime_bp, url_prefix='/realtime')
    
    # Initialize WebSocket price feed
    from websocket_feed import WebSocketManager
    websocket_manager = WebSocketManager()
    app.websocket_manager = websocket_manager
    
    # Start WebSocket feed in background with context
    def start_websocket_feed():
        try:
            with app.app_context():
                # Add callback for real-time dashboard updates
                websocket_manager.add_callback(dashboard_manager.broadcast_market_update)
                # Start multi-currency feeds
                symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "ADA-USDT", "BNB-USDT"]
                websocket_manager.start(symbols)
                logging.info(f"Multi-currency WebSocket feeds started for: {symbols}")
        except Exception as e:
            logging.error(f"Failed to start WebSocket feed: {e}")
    
    # Start WebSocket feed in separate thread
    websocket_thread = threading.Thread(target=start_websocket_feed, daemon=True)
    websocket_thread.start()
    
    # Initialize multi-currency manager
    from multi_currency_manager import MultiCurrencyManager
    currency_manager = MultiCurrencyManager()
    app.currency_manager = currency_manager
    
    # Initialize true autonomous trading service
    def start_autonomous_trading_service():
        """Start enhanced autonomous trading service with persistent operation"""
        import time
        import requests
        import json
        import hmac
        import hashlib
        import base64
        from datetime import datetime, timezone
        import threading
        
        class PersistentAutonomousTrader:
            def __init__(self):
                self.api_key = os.environ.get('OKX_API_KEY')
                self.secret_key = os.environ.get('OKX_SECRET_KEY')
                self.passphrase = os.environ.get('OKX_PASSPHRASE')
                self.base_url = 'https://www.okx.com'
                
                self.running = True
                self.autonomous_trades = 0
                self.last_trade_minute = -1
                self.error_count = 0
                self.cached_balance = 0.0
                self.last_balance_check = 0
                
                # Trading pairs optimized for low minimum orders
                self.trading_pairs = ['DOGE-USDT', 'TRX-USDT', 'SHIB-USDT', 'PEPE-USDT']
                
                print(f"[AUTONOMOUS] Persistent trading service initialized")
            
            def generate_signature(self, timestamp, method, request_path, body=''):
                message = timestamp + method + request_path + body
                mac = hmac.new(
                    bytes(self.secret_key, encoding='utf8'),
                    bytes(message, encoding='utf-8'),
                    digestmod=hashlib.sha256
                )
                return base64.b64encode(mac.digest()).decode()
            
            def get_headers(self, method, request_path, body=''):
                timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                signature = self.generate_signature(timestamp, method, request_path, body)
                
                return {
                    'OK-ACCESS-KEY': self.api_key,
                    'OK-ACCESS-SIGN': signature,
                    'OK-ACCESS-TIMESTAMP': timestamp,
                    'OK-ACCESS-PASSPHRASE': self.passphrase,
                    'Content-Type': 'application/json'
                }
            
            def safe_request(self, method, url, headers=None, data=None, timeout=10):
                """Safe request with error handling"""
                try:
                    if method.upper() == 'GET':
                        response = requests.get(url, headers=headers, timeout=timeout)
                    elif method.upper() == 'POST':
                        response = requests.post(url, headers=headers, data=data, timeout=timeout)
                    else:
                        return None
                    
                    if response.status_code in [200, 201]:
                        return response
                    elif response.status_code == 429:  # Rate limit
                        time.sleep(2)
                        return None
                    else:
                        return response
                except Exception as e:
                    print(f"[AUTONOMOUS] Request error: {e}")
                    return None
            
            def get_balance_cached(self):
                """Get balance with caching"""
                current_time = time.time()
                if current_time - self.last_balance_check < 30:
                    return self.cached_balance
                
                try:
                    path = '/api/v5/account/balance'
                    headers = self.get_headers('GET', path)
                    response = self.safe_request('GET', self.base_url + path, headers)
                    
                    if response and response.status_code == 200:
                        data = response.json()
                        if data.get('code') == '0':
                            for detail in data['data'][0]['details']:
                                if detail['ccy'] == 'USDT':
                                    self.cached_balance = float(detail['availBal'])
                                    self.last_balance_check = current_time
                                    return self.cached_balance
                    
                    return self.cached_balance
                except Exception as e:
                    print(f"[AUTONOMOUS] Balance check error: {e}")
                    return self.cached_balance
            
            def find_optimal_trading_pair(self, balance):
                """Find optimal trading pair for current balance"""
                for symbol in self.trading_pairs:
                    try:
                        # Get current price
                        response = self.safe_request('GET', f'{self.base_url}/api/v5/market/ticker?instId={symbol}')
                        if not response or response.status_code != 200:
                            continue
                        
                        price_data = response.json()
                        if not price_data.get('data'):
                            continue
                        
                        current_price = float(price_data['data'][0]['last'])
                        
                        # Get instrument specifications
                        response = self.safe_request('GET', f'{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}')
                        if not response or response.status_code != 200:
                            continue
                        
                        inst_data = response.json()
                        if not inst_data.get('data'):
                            continue
                        
                        instrument = inst_data['data'][0]
                        min_size = float(instrument.get('minSz', '0'))
                        lot_size = float(instrument.get('lotSz', '0'))
                        
                        # Calculate trade parameters
                        trade_amount = balance * 0.85  # Use 85% of balance
                        max_quantity = trade_amount / current_price
                        
                        if lot_size > 0:
                            max_quantity = int(max_quantity / lot_size) * lot_size
                        
                        if max_quantity >= min_size and trade_amount >= 1.0:
                            final_amount = max_quantity * current_price
                            return symbol, current_price, max_quantity, final_amount
                    
                    except Exception as e:
                        print(f"[AUTONOMOUS] Error analyzing {symbol}: {e}")
                        continue
                
                return None, 0, 0, 0
            
            def execute_autonomous_trade(self, symbol, quantity, price, amount):
                """Execute autonomous trade with comprehensive error handling"""
                try:
                    order_data = {
                        "instId": symbol,
                        "tdMode": "cash",
                        "side": "buy",
                        "ordType": "market",
                        "sz": str(quantity)
                    }
                    
                    path = '/api/v5/trade/order'
                    body = json.dumps(order_data)
                    headers = self.get_headers('POST', path, body)
                    
                    response = self.safe_request('POST', self.base_url + path, headers, body)
                    
                    if response and response.status_code == 200:
                        result = response.json()
                        if result.get('code') == '0':
                            order_id = result['data'][0]['ordId']
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            print(f"\n[AUTONOMOUS] TRADE EXECUTED at {timestamp}")
                            print(f"Order ID: {order_id}")
                            print(f"Pair: {symbol} | Qty: {quantity:.6f} | Price: ${price:.6f}")
                            print(f"Value: ${amount:.2f} | Trade #{self.autonomous_trades + 1}")
                            
                            self.error_count = 0
                            return True
                        else:
                            print(f"[AUTONOMOUS] Trade rejected: {result.get('msg', 'Unknown error')}")
                    else:
                        status = response.status_code if response else "No response"
                        print(f"[AUTONOMOUS] Trade failed - HTTP {status}")
                    
                    return False
                
                except Exception as e:
                    print(f"[AUTONOMOUS] Trade execution error: {e}")
                    return False
            
            def autonomous_cycle(self):
                """Execute one autonomous trading cycle"""
                try:
                    current_time = datetime.now()
                    current_minute = current_time.minute
                    
                    # Execute every 4 minutes
                    if current_minute % 4 == 0 and current_minute != self.last_trade_minute:
                        self.last_trade_minute = current_minute
                        
                        timestamp = current_time.strftime('%H:%M:%S')
                        print(f"\n[AUTONOMOUS] Cycle #{self.autonomous_trades + 1} at {timestamp}")
                        
                        balance = self.get_balance_cached()
                        print(f"[AUTONOMOUS] Available: ${balance:.2f} USDT")
                        
                        if balance >= 1.0:  # Minimum $1 for trading
                            symbol, price, quantity, amount = self.find_optimal_trading_pair(balance)
                            
                            if symbol:
                                print(f"[AUTONOMOUS] Selected: {symbol} | ${price:.6f} | Qty: {quantity:.6f}")
                                
                                if self.execute_autonomous_trade(symbol, quantity, price, amount):
                                    self.autonomous_trades += 1
                                    print(f"[AUTONOMOUS] Total trades: {self.autonomous_trades}")
                                    self.cached_balance = 0  # Force refresh
                                else:
                                    self.error_count += 1
                                    print(f"[AUTONOMOUS] Trade failed - Errors: {self.error_count}")
                            else:
                                print(f"[AUTONOMOUS] No suitable pairs found")
                        else:
                            print(f"[AUTONOMOUS] Insufficient balance: ${balance:.2f}")
                    
                    return True
                
                except Exception as e:
                    print(f"[AUTONOMOUS] Cycle error: {e}")
                    self.error_count += 1
                    return self.error_count < 10
            
            def run_persistent(self):
                """Main persistent loop"""
                print(f"[AUTONOMOUS] Starting continuous operation")
                print(f"[AUTONOMOUS] Schedule: Every 4 minutes (00, 04, 08, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56)")
                
                cycle_count = 0
                
                while self.running:
                    try:
                        if not self.autonomous_cycle():
                            print(f"[AUTONOMOUS] Error threshold reached - Resetting")
                            self.error_count = 0
                            time.sleep(60)
                        
                        cycle_count += 1
                        
                        # Status update every 50 cycles
                        if cycle_count % 50 == 0:
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            print(f"[AUTONOMOUS] Status at {timestamp}: {cycle_count} cycles, {self.autonomous_trades} trades")
                        
                        time.sleep(30)  # Check every 30 seconds
                        
                    except Exception as e:
                        print(f"[AUTONOMOUS] Main loop error: {e}")
                        self.error_count += 1
                        time.sleep(60)
                
                print(f"[AUTONOMOUS] Service stopped. Total trades: {self.autonomous_trades}")
        
        # Start persistent autonomous trader
        def start_persistent_trader():
            trader = PersistentAutonomousTrader()
            trader.run_persistent()
        
        # Run in background thread
        trader_thread = threading.Thread(target=start_persistent_trader, daemon=True)
        trader_thread.start()
        
        print("[AUTONOMOUS] Persistent trading service started in background")
    
    # Start the autonomous trading service
    start_autonomous_trading_service()
    
    logging.info("Ultra-high performance multi-currency trading system initialized")
    logging.info(f"Enabled currencies: {currency_manager.get_enabled_symbols()}")
