from app import db
from datetime import datetime
from sqlalchemy import Enum
import enum

class TradeStatus(enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class TradeType(enum.Enum):
    BUY = "buy"
    SELL = "sell"

class BotStatus(enum.Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    trade_type = db.Column(Enum(TradeType), nullable=False)
    symbol = db.Column(db.String(20), nullable=False, default="BTC-USDT")
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(Enum(TradeStatus), nullable=False, default=TradeStatus.PENDING)
    order_id = db.Column(db.String(100))
    signal_strength = db.Column(db.Float)
    risk_amount = db.Column(db.Float)
    stop_loss = db.Column(db.Float)
    take_profit = db.Column(db.Float)
    pnl = db.Column(db.Float, default=0.0)
    fees = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'trade_type': self.trade_type.value,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'status': self.status.value,
            'order_id': self.order_id,
            'signal_strength': self.signal_strength,
            'risk_amount': self.risk_amount,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'pnl': self.pnl,
            'fees': self.fees,
            'notes': self.notes
        }

class BotConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_value(cls, key, default=None):
        config = cls.query.filter_by(key=key).first()
        return config.value if config else default
    
    @classmethod
    def set_value(cls, key, value, description=None):
        config = cls.query.filter_by(key=key).first()
        if config:
            config.value = str(value)
            config.updated_at = datetime.utcnow()
        else:
            config = cls(key=key, value=str(value), description=description)
            db.session.add(config)
        db.session.commit()

class BotLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    level = db.Column(db.String(20), nullable=False)  # INFO, WARNING, ERROR
    message = db.Column(db.Text, nullable=False)
    component = db.Column(db.String(50))  # bot, trader, signal_generator, etc.
    details = db.Column(db.Text)  # JSON string for additional details
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'message': self.message,
            'component': self.component,
            'details': self.details
        }

class MarketData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    symbol = db.Column(db.String(20), nullable=False, default="BTC-USDT")
    price = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Float)
    atr = db.Column(db.Float)  # Average True Range
    ema_12 = db.Column(db.Float)  # 12-period EMA
    ema_26 = db.Column(db.Float)  # 26-period EMA
    rsi = db.Column(db.Float)  # Relative Strength Index
    macd = db.Column(db.Float)  # MACD indicator
    signal_score = db.Column(db.Float)  # Combined signal strength
