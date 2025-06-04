import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from models import BotConfig, BotLog, BotStatus, Trade, TradeStatus
from bot import run_bot_cycle
from trader import Trader
from risk_manager import RiskManager
from market_analyzer import MarketAnalyzer
from error_recovery import ErrorRecoveryManager
from trailing_stop_manager import TrailingStopManager
import json

class BotManager:
    def __init__(self, db, scheduler):
        self.db = db
        self.scheduler = scheduler
        self.status = BotStatus.STOPPED
        self.trader = Trader()
        self.risk_manager = RiskManager(db)
        self.market_analyzer = MarketAnalyzer()
        self.error_recovery = ErrorRecoveryManager(db)
        self.trailing_stop_manager = TrailingStopManager(db, self.trader)
        self.last_run = None
        self.error_count = 0
        self.max_errors = 5
        self.job_id = 'trading_bot_job'
        self.trailing_stop_job_id = 'trailing_stop_job'
        
        # Initialize default configuration with enhanced parameters
        self._init_default_config()
        
        logging.info("BotManager initialized with autonomous features")
    
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
            ('trailing_stops_enabled', 'true', 'Enable trailing stop losses'),
            ('trail_distance_percent', '2.0', 'Trailing stop distance percentage'),
            ('auto_recovery_enabled', 'true', 'Enable automatic error recovery'),
            ('market_filter_enabled', 'true', 'Enable advanced market filtering'),
            ('min_volume_ratio', '0.5', 'Minimum volume ratio for trading'),
            ('max_volatility_percentile', '85', 'Maximum volatility percentile'),
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
        """Start the autonomous trading bot with enhanced features"""
        try:
            if self.status == BotStatus.RUNNING:
                self.log("WARNING", "Bot is already running")
                return False
            
            # Check if trading is enabled
            if not self._is_trading_enabled():
                self.log("WARNING", "Trading is disabled in configuration")
                return False
            
            # Perform health check before starting
            health_status = self.error_recovery.health_check()
            if health_status['overall_status'] == 'unhealthy':
                self.log("ERROR", "System health check failed - cannot start bot")
                return False
            elif health_status['overall_status'] == 'degraded':
                self.log("WARNING", "System health is degraded but starting anyway")
            
            # Add main trading cycle job
            if not self.scheduler.get_job(self.job_id):
                self.scheduler.add_job(
                    func=self._run_enhanced_cycle,
                    trigger="interval",
                    seconds=60,  # Run every minute
                    id=self.job_id,
                    name="Autonomous Trading Bot Cycle"
                )
            
            # Add trailing stop management job
            trailing_stops_enabled = BotConfig.get_value('trailing_stops_enabled', 'true').lower() == 'true'
            if trailing_stops_enabled and not self.scheduler.get_job(self.trailing_stop_job_id):
                self.scheduler.add_job(
                    func=self._manage_trailing_stops,
                    trigger="interval",
                    seconds=15,  # Check trailing stops every 15 seconds
                    id=self.trailing_stop_job_id,
                    name="Trailing Stop Manager"
                )
            
            self.status = BotStatus.RUNNING
            self.error_count = 0
            self.log("INFO", "Autonomous trading bot started with enhanced features")
            return True
            
        except Exception as e:
            self.log("ERROR", f"Failed to start bot: {str(e)}")
            self.status = BotStatus.ERROR
            return False
    
    def stop(self) -> bool:
        """Stop the autonomous trading bot and all related jobs"""
        try:
            # Stop main trading cycle
            if self.scheduler.get_job(self.job_id):
                self.scheduler.remove_job(self.job_id)
            
            # Stop trailing stop management
            if self.scheduler.get_job(self.trailing_stop_job_id):
                self.scheduler.remove_job(self.trailing_stop_job_id)
            
            self.status = BotStatus.STOPPED
            self.log("INFO", "Autonomous trading bot stopped")
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
    
    def _run_enhanced_cycle(self):
        """Execute one enhanced autonomous trading cycle with error recovery"""
        if self.status != BotStatus.RUNNING:
            return
        
        try:
            self.last_run = datetime.utcnow()
            
            # Apply error recovery decorator to the trading cycle
            @self.error_recovery.with_retry(max_retries=3)
            @self.error_recovery.circuit_breaker('trading_cycle')
            def execute_trading_cycle():
                if not self._check_cooldown():
                    return {'action': 'hold', 'message': 'Cooldown period active'}
                
                if not self._check_daily_limit():
                    return {'action': 'hold', 'message': 'Daily trade limit reached'}
                
                # Run the enhanced trading cycle
                result = run_bot_cycle(
                    trader=self.trader,
                    risk_manager=self.risk_manager,
                    market_analyzer=self.market_analyzer,
                    db=self.db
                )
                
                # Add trailing stops for executed trades
                if result.get('action') in ['buy', 'sell'] and result.get('trade_id'):
                    trailing_enabled = BotConfig.get_value('trailing_stops_enabled', 'true')
                    if trailing_enabled and trailing_enabled.lower() == 'true':
                        trail_distance = float(BotConfig.get_value('trail_distance_percent', '2.0')) / 100
                        self.trailing_stop_manager.add_trailing_stop(
                            result['trade_id'], 
                            trail_distance
                        )
                        self.log("INFO", f"Added trailing stop for trade {result['trade_id']}")
                
                return result
            
            # Execute the cycle with error recovery
            result = execute_trading_cycle()
            
            if result.get('error'):
                self.error_count += 1
                self.log("ERROR", f"Trading cycle error: {result['error']}")
                
                # Try to recover from specific error types
                recovery_success = self.error_recovery.recover_from_error(
                    'trading_cycle_error', 
                    {'error': result['error'], 'timestamp': datetime.utcnow()}
                )
                
                if not recovery_success and self.error_count >= self.max_errors:
                    self.log("ERROR", f"Max errors ({self.max_errors}) reached. Stopping bot.")
                    self.status = BotStatus.ERROR
                    self.stop()
            else:
                self.error_count = 0  # Reset error count on success
                
                if result.get('action') != 'hold':
                    self.log("INFO", f"Trading action: {result.get('action')} - {result.get('message', '')}")
                    
                    # Log market conditions for successful trades
                    market_filter = result.get('market_filter', {})
                    if market_filter:
                        self.log("INFO", f"Market grade: {market_filter.get('market_grade', 'Unknown')}")
            
        except Exception as e:
            self.error_count += 1
            self.log("ERROR", f"Enhanced cycle execution error: {str(e)}")
            
            # Attempt error recovery
            recovery_success = self.error_recovery.recover_from_error(
                'cycle_exception', 
                {'error': str(e), 'timestamp': datetime.utcnow()}
            )
            
            if not recovery_success and self.error_count >= self.max_errors:
                self.log("ERROR", f"Max errors ({self.max_errors}) reached. Stopping bot.")
                self.status = BotStatus.ERROR
                self.stop()
    
    def _manage_trailing_stops(self):
        """Manage trailing stop losses for all active positions"""
        try:
            if self.status != BotStatus.RUNNING:
                return
            
            # Update all trailing stops
            updates = self.trailing_stop_manager.update_trailing_stops()
            
            # Log any triggered stops
            for update in updates:
                if update.get('triggered'):
                    self.log("INFO", f"Trailing stop triggered for trade {update['trade_id']} at {update['trigger_price']}")
                    
                    # Update trade status in database
                    trade = Trade.query.get(update['trade_id'])
                    if trade:
                        trade.status = TradeStatus.EXECUTED
                        trade.pnl = update.get('pnl', 0.0)
                        trade.notes = f"Trailing stop triggered at {update['trigger_price']}"
                        self.db.session.commit()
            
            # Cleanup old trailing stops
            cleaned = self.trailing_stop_manager.cleanup_expired_stops(max_age_hours=24)
            if cleaned > 0:
                self.log("DEBUG", f"Cleaned up {cleaned} expired trailing stops")
        
        except Exception as e:
            self.log("ERROR", f"Trailing stop management error: {str(e)}")
    
    def _run_cycle(self):
        """Legacy cycle method - redirects to enhanced cycle"""
        self._run_enhanced_cycle()
    
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
