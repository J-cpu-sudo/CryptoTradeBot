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
    
    # Initialize enhanced bot manager
    from bot_manager import BotManager
    bot_manager = BotManager(db, scheduler)
    app.bot_manager = bot_manager
    
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
    
    # Start WebSocket feed in background
    def start_websocket_feed():
        try:
            # Add callback for real-time dashboard updates
            websocket_manager.add_callback(dashboard_manager.broadcast_market_update)
            websocket_manager.start(["BTC-USDT"])
            logging.info("WebSocket price feed started")
        except Exception as e:
            logging.error(f"Failed to start WebSocket feed: {e}")
    
    # Start WebSocket feed in separate thread
    websocket_thread = threading.Thread(target=start_websocket_feed, daemon=True)
    websocket_thread.start()
    
    logging.info("Ultra-high performance trading system initialized")
