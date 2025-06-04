import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from models import BotConfig, BotLog, BotStatus
from bot import run_bot_cycle
from trader import Trader
from risk_manager import RiskManager
from market_analyzer import MarketAnalyzer
import json

class BotManager:
    def __init__(self, db, scheduler):
        self.db = db
        self.scheduler = scheduler
        self.status = BotStatus.STOPPED
        self.trader = Trader()
        self.risk_manager = RiskManager(db)
        self.market_analyzer = MarketAnalyzer()
        self.last_run = None
        self.error_count = 0
        self.max_errors = 5
        self.job_id = 'trading_bot_job'
        
        # Initialize default configuration
        self._init_default_config()
        
        logging.info("BotManager initialized")
    
    def _init_default_config(self):
        """Initialize default bot configuration"""
        default_configs = [
            ('risk_percent', '2.0', 'Risk percentage per trade'),
            ('max_trades_per_day', '10', 'Maximum trades per day'),
            ('trading_enabled', 'true', 'Enable/disable trading'),
            ('dry_run', 'true', 'Run in simulation mode'),
            ('symbol', 'BTC-USDT', 'Trading symbol'),
            ('min_signal_strength', '0.7', 'Minimum signal strength for trade'),
            ('stop_loss_percent', '2.0', 'Stop loss percentage'),
            ('take_profit_percent', '4.0', 'Take profit percentage'),
            ('cooldown_minutes', '15', 'Cooldown between trades (minutes)'),
        ]
        
        for key, value, description in default_configs:
            if not BotConfig.query.filter_by(key=key).first():
                config = BotConfig(key=key, value=value, description=description)
                self.db.session.add(config)
        
        try:
            self.db.session.commit()
        except Exception as e:
            logging.error(f"Error initializing default config: {e}")
            self.db.session.rollback()
    
    def start(self) -> bool:
        """Start the trading bot"""
        try:
            if self.status == BotStatus.RUNNING:
                self.log("WARNING", "Bot is already running")
                return False
            
            # Check if trading is enabled
            if not self._is_trading_enabled():
                self.log("WARNING", "Trading is disabled in configuration")
                return False
            
            # Add scheduled job
            if not self.scheduler.get_job(self.job_id):
                self.scheduler.add_job(
                    func=self._run_cycle,
                    trigger="interval",
                    seconds=60,  # Run every minute
                    id=self.job_id,
                    name="Trading Bot Cycle"
                )
            
            self.status = BotStatus.RUNNING
            self.error_count = 0
            self.log("INFO", "Trading bot started")
            return True
            
        except Exception as e:
            self.log("ERROR", f"Failed to start bot: {str(e)}")
            self.status = BotStatus.ERROR
            return False
    
    def stop(self) -> bool:
        """Stop the trading bot"""
        try:
            if self.scheduler.get_job(self.job_id):
                self.scheduler.remove_job(self.job_id)
            
            self.status = BotStatus.STOPPED
            self.log("INFO", "Trading bot stopped")
            return True
            
        except Exception as e:
            self.log("ERROR", f"Failed to stop bot: {str(e)}")
            return False
    
    def pause(self) -> bool:
        """Pause the trading bot"""
        try:
            if self.status != BotStatus.RUNNING:
                return False
            
            self.status = BotStatus.PAUSED
            self.log("INFO", "Trading bot paused")
            return True
            
        except Exception as e:
            self.log("ERROR", f"Failed to pause bot: {str(e)}")
            return False
    
    def resume(self) -> bool:
        """Resume the trading bot"""
        try:
            if self.status != BotStatus.PAUSED:
                return False
            
            self.status = BotStatus.RUNNING
            self.log("INFO", "Trading bot resumed")
            return True
            
        except Exception as e:
            self.log("ERROR", f"Failed to resume bot: {str(e)}")
            return False
    
    def _run_cycle(self):
        """Execute one trading cycle"""
        if self.status != BotStatus.RUNNING:
            return
        
        try:
            self.last_run = datetime.utcnow()
            
            # Check cooldown
            if not self._check_cooldown():
                return
            
            # Check daily trade limit
            if not self._check_daily_limit():
                self.log("WARNING", "Daily trade limit reached")
                return
            
            # Run the trading cycle
            result = run_bot_cycle(
                trader=self.trader,
                risk_manager=self.risk_manager,
                market_analyzer=self.market_analyzer,
                db=self.db
            )
            
            if result.get('error'):
                self.error_count += 1
                self.log("ERROR", f"Trading cycle error: {result['error']}")
                
                if self.error_count >= self.max_errors:
                    self.status = BotStatus.ERROR
                    self.log("ERROR", f"Bot stopped due to {self.max_errors} consecutive errors")
            else:
                self.error_count = 0  # Reset error count on success
                if result.get('action'):
                    self.log("INFO", f"Trading action: {result['action']}")
            
        except Exception as e:
            self.error_count += 1
            self.log("ERROR", f"Unexpected error in trading cycle: {str(e)}")
            
            if self.error_count >= self.max_errors:
                self.status = BotStatus.ERROR
    
    def _is_trading_enabled(self) -> bool:
        """Check if trading is enabled in configuration"""
        return BotConfig.get_value('trading_enabled', 'false').lower() == 'true'
    
    def _check_cooldown(self) -> bool:
        """Check if enough time has passed since last trade"""
        cooldown_minutes = int(BotConfig.get_value('cooldown_minutes', '15'))
        
        # Get the last trade from database
        from models import Trade
        last_trade = Trade.query.order_by(Trade.timestamp.desc()).first()
        
        if not last_trade:
            return True
        
        time_diff = datetime.utcnow() - last_trade.timestamp
        return time_diff.total_seconds() >= (cooldown_minutes * 60)
    
    def _check_daily_limit(self) -> bool:
        """Check if daily trade limit has been reached"""
        max_trades = int(BotConfig.get_value('max_trades_per_day', '10'))
        
        # Count trades from today
        from models import Trade
        today = datetime.utcnow().date()
        today_trades = Trade.query.filter(
            Trade.timestamp >= datetime.combine(today, datetime.min.time())
        ).count()
        
        return today_trades < max_trades
    
    def log(self, level: str, message: str, component: str = "bot_manager", details: dict = None):
        """Log a message to the database"""
        try:
            log_entry = BotLog(
                level=level,
                message=message,
                component=component,
                details=json.dumps(details) if details else None
            )
            self.db.session.add(log_entry)
            self.db.session.commit()
            
            # Also log to console
            logging.log(getattr(logging, level), f"[{component}] {message}")
            
        except Exception as e:
            logging.error(f"Failed to log message: {e}")
    
    def get_status(self) -> dict:
        """Get current bot status and statistics"""
        from models import Trade
        
        # Get recent trades
        recent_trades = Trade.query.order_by(Trade.timestamp.desc()).limit(5).all()
        
        # Calculate daily P&L
        today = datetime.utcnow().date()
        daily_pnl = self.db.session.query(
            self.db.func.sum(Trade.pnl)
        ).filter(
            Trade.timestamp >= datetime.combine(today, datetime.min.time())
        ).scalar() or 0.0
        
        # Get total P&L
        total_pnl = self.db.session.query(
            self.db.func.sum(Trade.pnl)
        ).scalar() or 0.0
        
        return {
            'status': self.status.value,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'error_count': self.error_count,
            'daily_pnl': round(daily_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'recent_trades': [trade.to_dict() for trade in recent_trades],
            'config': {
                'dry_run': BotConfig.get_value('dry_run', 'true'),
                'risk_percent': BotConfig.get_value('risk_percent', '2.0'),
                'symbol': BotConfig.get_value('symbol', 'BTC-USDT'),
                'trading_enabled': BotConfig.get_value('trading_enabled', 'false')
            }
        }
