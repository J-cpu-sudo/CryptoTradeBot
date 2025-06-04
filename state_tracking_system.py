import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import os

class BotState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    RECOVERING = "recovering"

class SessionPhase(Enum):
    WARMUP = "warmup"
    ACTIVE = "active"
    COOLING_DOWN = "cooling_down"
    ENDED = "ended"

@dataclass
class PerformanceMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    consecutive_wins: int
    consecutive_losses: int
    max_consecutive_wins: int
    max_consecutive_losses: int
    total_pnl: float
    best_trade: float
    worst_trade: float
    avg_trade: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    current_drawdown: float
    roi: float
    trades_today: int
    pnl_today: float
    session_start: datetime
    session_duration: float
    last_trade_time: Optional[datetime]

@dataclass
class TradingSession:
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    phase: SessionPhase
    initial_balance: float
    current_balance: float
    trades_executed: List[Dict[str, Any]]
    performance: PerformanceMetrics
    strategy_mode: str
    bot_state: BotState
    recovery_attempts: int
    metadata: Dict[str, Any]

class StateTrackingSystem:
    """Comprehensive state tracking with crash-safe persistence"""
    
    def __init__(self, state_file: str = "bot_state.json", backup_interval: int = 30):
        self.state_file = state_file
        self.backup_interval = backup_interval
        
        # Current session
        self.current_session: Optional[TradingSession] = None
        self.session_history: List[TradingSession] = []
        
        # State tracking
        self.bot_state = BotState.STOPPED
        self.last_heartbeat = datetime.utcnow()
        self.state_changes: List[Dict[str, Any]] = []
        
        # Performance tracking
        self.performance_snapshots: List[Dict[str, Any]] = []
        self.real_time_metrics = {}
        
        # Recovery tracking
        self.crash_recovery_count = 0
        self.last_recovery_time = None
        self.recovery_success_rate = 1.0
        
        # Thread safety and persistence
        self.lock = threading.Lock()
        self.auto_save_thread = None
        self.auto_save_running = False
        
        # Initialize from saved state
        self._load_state()
        self._start_auto_save()
        
        logging.info("State tracking system initialized")
    
    def start_session(self, initial_balance: float, strategy_mode: str = "precision") -> str:
        """Start a new trading session"""
        with self.lock:
            session_id = f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            # End previous session if exists
            if self.current_session:
                self.end_session()
            
            # Create new session
            performance = PerformanceMetrics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                consecutive_wins=0,
                consecutive_losses=0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                total_pnl=0.0,
                best_trade=0.0,
                worst_trade=0.0,
                avg_trade=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                current_drawdown=0.0,
                roi=0.0,
                trades_today=0,
                pnl_today=0.0,
                session_start=datetime.utcnow(),
                session_duration=0.0,
                last_trade_time=None
            )
            
            self.current_session = TradingSession(
                session_id=session_id,
                start_time=datetime.utcnow(),
                end_time=None,
                phase=SessionPhase.WARMUP,
                initial_balance=initial_balance,
                current_balance=initial_balance,
                trades_executed=[],
                performance=performance,
                strategy_mode=strategy_mode,
                bot_state=BotState.STARTING,
                recovery_attempts=0,
                metadata={}
            )
            
            self._log_state_change("session_started", {
                'session_id': session_id,
                'initial_balance': initial_balance,
                'strategy_mode': strategy_mode
            })
            
            logging.info(f"Started new trading session: {session_id}")
            return session_id
    
    def update_bot_state(self, new_state: BotState, details: Optional[Dict[str, Any]] = None):
        """Update bot state with logging"""
        with self.lock:
            old_state = self.bot_state
            self.bot_state = new_state
            self.last_heartbeat = datetime.utcnow()
            
            if self.current_session:
                self.current_session.bot_state = new_state
            
            self._log_state_change("bot_state_changed", {
                'old_state': old_state.value,
                'new_state': new_state.value,
                'details': details or {}
            })
            
            logging.info(f"Bot state: {old_state.value} → {new_state.value}")
    
    def record_trade(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a trade execution and update performance metrics"""
        with self.lock:
            if not self.current_session:
                return {'error': 'No active session'}
            
            # Extract trade information
            pnl = trade_data.get('pnl', 0.0)
            trade_time = trade_data.get('timestamp', datetime.utcnow())
            
            # Add to session trades
            trade_record = {
                'timestamp': trade_time.isoformat() if hasattr(trade_time, 'isoformat') else str(trade_time),
                'symbol': trade_data.get('symbol'),
                'side': trade_data.get('side'),
                'quantity': trade_data.get('quantity'),
                'price': trade_data.get('price'),
                'pnl': pnl,
                'trade_id': trade_data.get('trade_id'),
                'strategy_signal': trade_data.get('strategy_signal', {})
            }
            
            self.current_session.trades_executed.append(trade_record)
            self.current_session.current_balance += pnl
            
            # Update performance metrics
            self._update_performance_metrics(pnl, trade_time)
            
            # Move to active phase if in warmup
            if self.current_session.phase == SessionPhase.WARMUP:
                self.current_session.phase = SessionPhase.ACTIVE
            
            self._log_state_change("trade_recorded", trade_record)
            
            # Take performance snapshot
            self._take_performance_snapshot()
            
            logging.info(f"Recorded trade: {trade_data.get('side')} {trade_data.get('symbol')} P&L: ${pnl:.2f}")
            
            return {
                'success': True,
                'session_id': self.current_session.session_id,
                'total_trades': self.current_session.performance.total_trades,
                'session_pnl': self.current_session.performance.total_pnl,
                'consecutive_wins': self.current_session.performance.consecutive_wins,
                'consecutive_losses': self.current_session.performance.consecutive_losses
            }
    
    def _update_performance_metrics(self, pnl: float, trade_time: datetime):
        """Update detailed performance metrics"""
        perf = self.current_session.performance
        
        # Basic counters
        perf.total_trades += 1
        perf.total_pnl += pnl
        perf.last_trade_time = trade_time
        
        # Update balance tracking for drawdown
        old_balance = self.current_session.current_balance - pnl
        new_balance = self.current_session.current_balance
        
        # Win/Loss tracking
        if pnl > 0:
            perf.winning_trades += 1
            perf.consecutive_wins += 1
            perf.consecutive_losses = 0
            perf.max_consecutive_wins = max(perf.max_consecutive_wins, perf.consecutive_wins)
            
            if pnl > perf.best_trade:
                perf.best_trade = pnl
        
        elif pnl < 0:
            perf.losing_trades += 1
            perf.consecutive_losses += 1
            perf.consecutive_wins = 0
            perf.max_consecutive_losses = max(perf.max_consecutive_losses, perf.consecutive_losses)
            
            if pnl < perf.worst_trade:
                perf.worst_trade = pnl
        
        # Calculate derived metrics
        if perf.total_trades > 0:
            perf.win_rate = perf.winning_trades / perf.total_trades
            perf.avg_trade = perf.total_pnl / perf.total_trades
        
        # Profit factor
        gross_profit = sum(t['pnl'] for t in self.current_session.trades_executed if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in self.current_session.trades_executed if t['pnl'] < 0))
        perf.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # ROI
        perf.roi = (new_balance - self.current_session.initial_balance) / self.current_session.initial_balance
        
        # Drawdown calculation
        peak_balance = self.current_session.initial_balance
        for trade in self.current_session.trades_executed:
            balance_at_time = self.current_session.initial_balance + sum(t['pnl'] for t in self.current_session.trades_executed[:self.current_session.trades_executed.index(trade)+1])
            if balance_at_time > peak_balance:
                peak_balance = balance_at_time
        
        if peak_balance > 0:
            current_dd = (peak_balance - new_balance) / peak_balance
            perf.current_drawdown = current_dd
            perf.max_drawdown = max(perf.max_drawdown, current_dd)
        
        # Daily metrics
        today = datetime.utcnow().date()
        today_trades = [t for t in self.current_session.trades_executed 
                       if datetime.fromisoformat(t['timestamp']).date() == today]
        perf.trades_today = len(today_trades)
        perf.pnl_today = sum(t['pnl'] for t in today_trades)
        
        # Session duration
        perf.session_duration = (datetime.utcnow() - perf.session_start).total_seconds()
        
        # Sharpe ratio (simplified daily calculation)
        if len(self.current_session.trades_executed) >= 5:
            daily_returns = []
            daily_pnl = {}
            
            for trade in self.current_session.trades_executed:
                trade_date = datetime.fromisoformat(trade['timestamp']).date()
                if trade_date not in daily_pnl:
                    daily_pnl[trade_date] = 0
                daily_pnl[trade_date] += trade['pnl']
            
            daily_returns = list(daily_pnl.values())
            if len(daily_returns) > 1:
                import numpy as np
                mean_return = np.mean(daily_returns)
                std_return = np.std(daily_returns)
                perf.sharpe_ratio = mean_return / std_return if std_return > 0 else 0
    
    def handle_recovery_attempt(self, error_details: Dict[str, Any]) -> bool:
        """Handle crash recovery attempt"""
        with self.lock:
            self.crash_recovery_count += 1
            self.last_recovery_time = datetime.utcnow()
            
            if self.current_session:
                self.current_session.recovery_attempts += 1
                self.current_session.bot_state = BotState.RECOVERING
            
            self._log_state_change("recovery_attempt", {
                'attempt_number': self.crash_recovery_count,
                'error_details': error_details,
                'session_id': self.current_session.session_id if self.current_session else None
            })
            
            # Update recovery success rate
            total_attempts = len([change for change in self.state_changes 
                                if change['event'] == 'recovery_attempt'])
            successful_recoveries = len([change for change in self.state_changes 
                                       if change['event'] == 'recovery_successful'])
            
            self.recovery_success_rate = successful_recoveries / total_attempts if total_attempts > 0 else 1.0
            
            logging.warning(f"Recovery attempt #{self.crash_recovery_count}")
            return True
    
    def mark_recovery_successful(self):
        """Mark recovery as successful"""
        with self.lock:
            self._log_state_change("recovery_successful", {
                'recovery_time': self.last_recovery_time.isoformat() if self.last_recovery_time else None,
                'session_id': self.current_session.session_id if self.current_session else None
            })
            
            if self.current_session:
                self.current_session.bot_state = BotState.RUNNING
            
            logging.info("Recovery successful")
    
    def end_session(self, reason: str = "manual"):
        """End the current trading session"""
        with self.lock:
            if not self.current_session:
                return
            
            self.current_session.end_time = datetime.utcnow()
            self.current_session.phase = SessionPhase.ENDED
            
            # Final performance calculation
            self.current_session.performance.session_duration = (
                self.current_session.end_time - self.current_session.start_time
            ).total_seconds()
            
            # Add to history
            self.session_history.append(self.current_session)
            
            self._log_state_change("session_ended", {
                'session_id': self.current_session.session_id,
                'reason': reason,
                'duration_hours': self.current_session.performance.session_duration / 3600,
                'total_trades': self.current_session.performance.total_trades,
                'final_pnl': self.current_session.performance.total_pnl,
                'roi': self.current_session.performance.roi
            })
            
            logging.info(f"Session ended: {self.current_session.session_id}, P&L: ${self.current_session.performance.total_pnl:.2f}")
            
            # Clear current session
            self.current_session = None
    
    def _take_performance_snapshot(self):
        """Take a performance snapshot for trend analysis"""
        if not self.current_session:
            return
        
        snapshot = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': self.current_session.session_id,
            'balance': self.current_session.current_balance,
            'total_trades': self.current_session.performance.total_trades,
            'total_pnl': self.current_session.performance.total_pnl,
            'win_rate': self.current_session.performance.win_rate,
            'consecutive_wins': self.current_session.performance.consecutive_wins,
            'consecutive_losses': self.current_session.performance.consecutive_losses,
            'current_drawdown': self.current_session.performance.current_drawdown,
            'roi': self.current_session.performance.roi
        }
        
        self.performance_snapshots.append(snapshot)
        
        # Keep only recent snapshots (last 1000)
        if len(self.performance_snapshots) > 1000:
            self.performance_snapshots = self.performance_snapshots[-500:]
    
    def _log_state_change(self, event: str, data: Dict[str, Any]):
        """Log state change for audit trail"""
        change_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'event': event,
            'data': data,
            'bot_state': self.bot_state.value,
            'session_id': self.current_session.session_id if self.current_session else None
        }
        
        self.state_changes.append(change_record)
        
        # Keep only recent changes (last 1000)
        if len(self.state_changes) > 1000:
            self.state_changes = self.state_changes[-500:]
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get comprehensive current status"""
        with self.lock:
            status = {
                'bot_state': self.bot_state.value,
                'last_heartbeat': self.last_heartbeat.isoformat(),
                'session_active': self.current_session is not None,
                'crash_recovery_count': self.crash_recovery_count,
                'recovery_success_rate': self.recovery_success_rate
            }
            
            if self.current_session:
                status.update({
                    'session_id': self.current_session.session_id,
                    'session_phase': self.current_session.phase.value,
                    'session_duration_hours': (datetime.utcnow() - self.current_session.start_time).total_seconds() / 3600,
                    'strategy_mode': self.current_session.strategy_mode,
                    'current_balance': self.current_session.current_balance,
                    'session_pnl': self.current_session.performance.total_pnl,
                    'session_roi': self.current_session.performance.roi,
                    'total_trades': self.current_session.performance.total_trades,
                    'win_rate': self.current_session.performance.win_rate,
                    'consecutive_wins': self.current_session.performance.consecutive_wins,
                    'consecutive_losses': self.current_session.performance.consecutive_losses,
                    'current_drawdown': self.current_session.performance.current_drawdown,
                    'max_drawdown': self.current_session.performance.max_drawdown,
                    'trades_today': self.current_session.performance.trades_today,
                    'pnl_today': self.current_session.performance.pnl_today
                })
            
            return status
    
    def get_session_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent session history"""
        with self.lock:
            sessions = []
            for session in self.session_history[-limit:]:
                sessions.append({
                    'session_id': session.session_id,
                    'start_time': session.start_time.isoformat(),
                    'end_time': session.end_time.isoformat() if session.end_time else None,
                    'duration_hours': session.performance.session_duration / 3600,
                    'strategy_mode': session.strategy_mode,
                    'initial_balance': session.initial_balance,
                    'final_balance': session.current_balance,
                    'total_pnl': session.performance.total_pnl,
                    'roi': session.performance.roi,
                    'total_trades': session.performance.total_trades,
                    'win_rate': session.performance.win_rate,
                    'max_drawdown': session.performance.max_drawdown,
                    'recovery_attempts': session.recovery_attempts
                })
            return sessions
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over specified period"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        recent_snapshots = [
            s for s in self.performance_snapshots 
            if datetime.fromisoformat(s['timestamp']) > cutoff_time
        ]
        
        if not recent_snapshots:
            return {'error': 'No data available for specified period'}
        
        # Calculate trends
        balance_trend = []
        pnl_trend = []
        win_rate_trend = []
        drawdown_trend = []
        
        for snapshot in recent_snapshots:
            balance_trend.append(snapshot['balance'])
            pnl_trend.append(snapshot['total_pnl'])
            win_rate_trend.append(snapshot['win_rate'])
            drawdown_trend.append(snapshot['current_drawdown'])
        
        return {
            'period_hours': hours,
            'data_points': len(recent_snapshots),
            'balance_trend': balance_trend,
            'pnl_trend': pnl_trend,
            'win_rate_trend': win_rate_trend,
            'drawdown_trend': drawdown_trend,
            'timestamps': [s['timestamp'] for s in recent_snapshots]
        }
    
    def _save_state(self):
        """Save current state to file"""
        try:
            state_data = {
                'bot_state': self.bot_state.value,
                'last_heartbeat': self.last_heartbeat.isoformat(),
                'crash_recovery_count': self.crash_recovery_count,
                'recovery_success_rate': self.recovery_success_rate,
                'current_session': asdict(self.current_session) if self.current_session else None,
                'session_history': [asdict(s) for s in self.session_history[-10:]],  # Last 10 sessions
                'state_changes': self.state_changes[-100:],  # Last 100 changes
                'performance_snapshots': self.performance_snapshots[-100:],  # Last 100 snapshots
                'save_timestamp': datetime.utcnow().isoformat()
            }
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(state_data, f, indent=2, default=str)
            
            os.rename(temp_file, self.state_file)
            
        except Exception as e:
            logging.error(f"Error saving state: {e}")
    
    def _load_state(self):
        """Load state from file"""
        try:
            if not os.path.exists(self.state_file):
                logging.info("No existing state file found")
                return
            
            with open(self.state_file, 'r') as f:
                state_data = json.load(f)
            
            # Restore basic state
            self.bot_state = BotState(state_data.get('bot_state', 'stopped'))
            self.crash_recovery_count = state_data.get('crash_recovery_count', 0)
            self.recovery_success_rate = state_data.get('recovery_success_rate', 1.0)
            self.state_changes = state_data.get('state_changes', [])
            self.performance_snapshots = state_data.get('performance_snapshots', [])
            
            # Restore session history
            session_history_data = state_data.get('session_history', [])
            self.session_history = []
            
            for session_data in session_history_data:
                # Convert datetime strings back to datetime objects
                session_data['start_time'] = datetime.fromisoformat(session_data['start_time'])
                if session_data.get('end_time'):
                    session_data['end_time'] = datetime.fromisoformat(session_data['end_time'])
                
                performance_data = session_data['performance']
                performance_data['session_start'] = datetime.fromisoformat(performance_data['session_start'])
                if performance_data.get('last_trade_time'):
                    performance_data['last_trade_time'] = datetime.fromisoformat(performance_data['last_trade_time'])
                
                # Reconstruct session
                session = TradingSession(**session_data)
                self.session_history.append(session)
            
            # Restore current session if it exists and was running
            current_session_data = state_data.get('current_session')
            if current_session_data and self.bot_state in [BotState.RUNNING, BotState.PAUSED]:
                current_session_data['start_time'] = datetime.fromisoformat(current_session_data['start_time'])
                if current_session_data.get('end_time'):
                    current_session_data['end_time'] = datetime.fromisoformat(current_session_data['end_time'])
                
                performance_data = current_session_data['performance']
                performance_data['session_start'] = datetime.fromisoformat(performance_data['session_start'])
                if performance_data.get('last_trade_time'):
                    performance_data['last_trade_time'] = datetime.fromisoformat(performance_data['last_trade_time'])
                
                self.current_session = TradingSession(**current_session_data)
                
                # Mark as recovered
                self.handle_recovery_attempt({'reason': 'system_restart', 'previous_state': self.bot_state.value})
                self.mark_recovery_successful()
            
            logging.info(f"State loaded from {self.state_file}")
            
        except Exception as e:
            logging.error(f"Error loading state: {e}")
    
    def _start_auto_save(self):
        """Start automatic state saving"""
        def auto_save_loop():
            while self.auto_save_running:
                try:
                    time.sleep(self.backup_interval)
                    if self.auto_save_running:  # Check again after sleep
                        self._save_state()
                except Exception as e:
                    logging.error(f"Auto-save error: {e}")
        
        self.auto_save_running = True
        self.auto_save_thread = threading.Thread(target=auto_save_loop, daemon=True)
        self.auto_save_thread.start()
        
        logging.info(f"Auto-save started (interval: {self.backup_interval}s)")
    
    def stop_auto_save(self):
        """Stop automatic state saving"""
        self.auto_save_running = False
        if self.auto_save_thread:
            self.auto_save_thread.join(timeout=5)
        
        # Final save
        self._save_state()
        logging.info("Auto-save stopped")
    
    def export_comprehensive_data(self) -> Dict[str, Any]:
        """Export all state and performance data"""
        with self.lock:
            return {
                'export_timestamp': datetime.utcnow().isoformat(),
                'system_info': {
                    'bot_state': self.bot_state.value,
                    'crash_recovery_count': self.crash_recovery_count,
                    'recovery_success_rate': self.recovery_success_rate,
                    'last_heartbeat': self.last_heartbeat.isoformat()
                },
                'current_session': asdict(self.current_session) if self.current_session else None,
                'session_history': [asdict(s) for s in self.session_history],
                'state_changes': self.state_changes,
                'performance_snapshots': self.performance_snapshots,
                'current_status': self.get_current_status(),
                'performance_trends_24h': self.get_performance_trends(24)
            }