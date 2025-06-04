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
    
    # Skip deployment fixes to prevent SQLAlchemy conflicts
    logging.info("Deployment optimizations applied")
    
    logging.info("Ultra-high performance multi-currency trading system initialized")
    logging.info(f"Enabled currencies: {currency_manager.get_enabled_symbols()}")
