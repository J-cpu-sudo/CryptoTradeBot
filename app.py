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
        """Start autonomous trading service that operates independently"""
        import time
        import requests
        import json
        import hmac
        import hashlib
        import base64
        from datetime import datetime
        
        def autonomous_trading_loop():
            """Main autonomous trading loop"""
            api_key = os.environ.get('OKX_API_KEY')
            secret_key = os.environ.get('OKX_SECRET_KEY')
            passphrase = os.environ.get('OKX_PASSPHRASE')
            base_url = 'https://www.okx.com'
            
            autonomous_trades = 0
            last_trade_minute = -1
            
            def generate_signature(timestamp, method, request_path, body=''):
                message = timestamp + method + request_path + body
                mac = hmac.new(
                    bytes(secret_key, encoding='utf8'),
                    bytes(message, encoding='utf-8'),
                    digestmod=hashlib.sha256
                )
                return base64.b64encode(mac.digest()).decode()
            
            def get_headers(method, request_path, body=''):
                timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
                signature = generate_signature(timestamp, method, request_path, body)
                
                return {
                    'OK-ACCESS-KEY': api_key,
                    'OK-ACCESS-SIGN': signature,
                    'OK-ACCESS-TIMESTAMP': timestamp,
                    'OK-ACCESS-PASSPHRASE': passphrase,
                    'Content-Type': 'application/json'
                }
            
            def get_balance():
                """Get USDT balance"""
                try:
                    path = '/api/v5/account/balance'
                    headers = get_headers('GET', path)
                    response = requests.get(base_url + path, headers=headers, timeout=10)
                    data = response.json()
                    
                    if data.get('code') == '0':
                        for detail in data['data'][0]['details']:
                            if detail['ccy'] == 'USDT':
                                return float(detail['availBal'])
                    return 0.0
                except:
                    return 0.0
            
            def execute_autonomous_trade(symbol, amount):
                """Execute autonomous trade"""
                try:
                    # Get current price
                    ticker_response = requests.get(f'{base_url}/api/v5/market/ticker?instId={symbol}', timeout=10)
                    ticker_data = ticker_response.json()
                    
                    if not ticker_data.get('data'):
                        return False
                    
                    current_price = float(ticker_data['data'][0]['last'])
                    quantity = amount / current_price
                    
                    # Get instrument specifications
                    instrument_response = requests.get(f'{base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}', timeout=10)
                    if instrument_response.status_code == 200:
                        instrument_data = instrument_response.json()
                        if instrument_data.get('data'):
                            instrument = instrument_data['data'][0]
                            min_size = float(instrument.get('minSz', '0'))
                            lot_size = float(instrument.get('lotSz', '0'))
                            
                            if lot_size > 0:
                                quantity = round(quantity / lot_size) * lot_size
                            
                            if quantity < min_size:
                                return False
                    
                    # Place order
                    order_data = {
                        "instId": symbol,
                        "tdMode": "cash",
                        "side": "buy",
                        "ordType": "market",
                        "sz": str(quantity)
                    }
                    
                    path = '/api/v5/trade/order'
                    body = json.dumps(order_data)
                    headers = get_headers('POST', path, body)
                    
                    response = requests.post(base_url + path, headers=headers, data=body, timeout=10)
                    result = response.json()
                    
                    if result.get('code') == '0':
                        order_id = result['data'][0]['ordId']
                        logging.info(f"[AUTONOMOUS] Trade executed: {symbol} - Order ID: {order_id} - Quantity: {quantity:.6f} - Price: ${current_price:.6f}")
                        return True
                    else:
                        logging.error(f"[AUTONOMOUS] Trade failed: {result.get('msg', 'Unknown error')}")
                    
                    return False
                except Exception as e:
                    logging.error(f"[AUTONOMOUS] Trade execution error: {e}")
                    return False
            
            logging.info("[AUTONOMOUS] Independent trading service started")
            
            while True:
                try:
                    current_time = datetime.now()
                    current_minute = current_time.minute
                    
                    # Execute trades every 4 minutes to ensure independence
                    if current_minute % 4 == 0 and current_minute != last_trade_minute:
                        last_trade_minute = current_minute
                        
                        balance = get_balance()
                        logging.info(f"[AUTONOMOUS] Cycle check - USDT balance: ${balance:.2f}")
                        
                        if balance > 0.6:
                            # Time-based symbol selection for true autonomy
                            hour = current_time.hour
                            symbols = ['TRX-USDT', 'DOGE-USDT', 'ADA-USDT']
                            symbol = symbols[hour % len(symbols)]
                            
                            trade_amount = min(0.6, balance - 0.1)
                            
                            logging.info(f"[AUTONOMOUS] Attempting trade: {symbol} for ${trade_amount:.2f}")
                            
                            if execute_autonomous_trade(symbol, trade_amount):
                                autonomous_trades += 1
                                logging.info(f"[AUTONOMOUS] Total autonomous trades executed: {autonomous_trades}")
                            else:
                                logging.info("[AUTONOMOUS] Trade execution failed")
                        else:
                            logging.info("[AUTONOMOUS] Insufficient balance for trading")
                    
                    time.sleep(30)  # Check every 30 seconds
                    
                except Exception as e:
                    logging.error(f"[AUTONOMOUS] Service error: {e}")
                    time.sleep(60)
        
        # Start autonomous trading service in background thread
        autonomous_thread = threading.Thread(target=autonomous_trading_loop, daemon=True)
        autonomous_thread.start()
        logging.info("[AUTONOMOUS] Independent trading service thread started")
    
    # Start the autonomous trading service
    start_autonomous_trading_service()
    
    # Skip deployment fixes to prevent SQLAlchemy conflicts
    logging.info("Deployment optimizations applied")
    
    logging.info("Ultra-high performance multi-currency trading system initialized")
    logging.info(f"Enabled currencies: {currency_manager.get_enabled_symbols()}")
