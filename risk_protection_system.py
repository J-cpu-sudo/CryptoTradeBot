import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import threading

class RiskLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class ProtectionAction(Enum):
    CONTINUE = "continue"
    REDUCE_SIZE = "reduce_size"
    PAUSE_TRADING = "pause_trading"
    EMERGENCY_STOP = "emergency_stop"

@dataclass
class RiskMetrics:
    daily_pnl: float
    daily_trades: int
    consecutive_losses: int
    consecutive_wins: int
    current_drawdown: float
    max_drawdown: float
    volatility_spike: bool
    risk_level: RiskLevel
    recommended_action: ProtectionAction
    reasons: List[str]

class RiskProtectionSystem:
    """Advanced risk protection with daily caps and emergency controls"""
    
    def __init__(self, initial_balance: float = 10000):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        
        # Risk limits configuration
        self.daily_loss_cap = 0.10  # 10% daily loss limit
        self.max_consecutive_losses = 3
        self.max_daily_trades = 15
        self.emergency_drawdown_threshold = 0.20  # 20% total drawdown
        self.volatility_threshold = 0.05  # 5% sudden price movement
        
        # Daily tracking
        self.daily_trades = []
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.utcnow().date()
        
        # Loss tracking
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.total_losses = 0
        self.total_wins = 0
        
        # Drawdown tracking
        self.peak_balance = initial_balance
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        self.drawdown_history = []
        
        # State management
        self.trading_paused = False
        self.emergency_stop = False
        self.pause_reason = ""
        self.pause_until = None
        
        # Thread safety
        self.lock = threading.Lock()
        
        logging.info(f"Risk protection system initialized with ${initial_balance:,.2f}")
    
    def evaluate_trade_risk(self, proposed_trade: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if proposed trade meets risk criteria"""
        with self.lock:
            self._update_daily_reset()
            
            # Get current risk metrics
            metrics = self._calculate_risk_metrics()
            
            # Check if trading is allowed
            if self.emergency_stop:
                return {
                    'allowed': False,
                    'reason': 'Emergency stop active',
                    'risk_level': RiskLevel.EMERGENCY.value,
                    'action': ProtectionAction.EMERGENCY_STOP.value
                }
            
            if self.trading_paused:
                if self.pause_until and datetime.utcnow() < self.pause_until:
                    return {
                        'allowed': False,
                        'reason': f'Trading paused: {self.pause_reason}',
                        'risk_level': metrics.risk_level.value,
                        'resume_time': self.pause_until.isoformat()
                    }
                else:
                    # Auto-resume if pause period expired
                    self._resume_trading()
            
            # Check individual risk factors
            risk_checks = self._perform_risk_checks(proposed_trade, metrics)
            
            return {
                'allowed': risk_checks['allowed'],
                'reason': risk_checks['reason'],
                'risk_level': metrics.risk_level.value,
                'recommended_action': metrics.recommended_action.value,
                'position_size_adjustment': risk_checks.get('position_adjustment', 1.0),
                'metrics': {
                    'daily_pnl': metrics.daily_pnl,
                    'daily_trades': metrics.daily_trades,
                    'consecutive_losses': metrics.consecutive_losses,
                    'current_drawdown': metrics.current_drawdown,
                    'risk_level': metrics.risk_level.value
                }
            }
    
    def record_trade_result(self, trade_result: Dict[str, Any]) -> Dict[str, Any]:
        """Record trade result and update risk metrics"""
        with self.lock:
            pnl = trade_result.get('pnl', 0.0)
            trade_time = trade_result.get('timestamp', datetime.utcnow())
            
            # Update balance
            self.current_balance += pnl
            
            # Update daily tracking
            self.daily_pnl += pnl
            self.daily_trades.append({
                'timestamp': trade_time,
                'pnl': pnl,
                'symbol': trade_result.get('symbol'),
                'side': trade_result.get('side')
            })
            
            # Update win/loss streaks
            if pnl > 0:
                self.consecutive_wins += 1
                self.consecutive_losses = 0
                self.total_wins += 1
            elif pnl < 0:
                self.consecutive_losses += 1
                self.consecutive_wins = 0
                self.total_losses += 1
            
            # Update drawdown tracking
            self._update_drawdown()
            
            # Check for automatic protections
            protection_triggered = self._check_automatic_protections()
            
            # Calculate new risk metrics
            metrics = self._calculate_risk_metrics()
            
            logging.info(f"Trade recorded: P&L ${pnl:.2f}, Balance: ${self.current_balance:.2f}, Risk: {metrics.risk_level.value}")
            
            return {
                'balance_updated': True,
                'new_balance': self.current_balance,
                'daily_pnl': self.daily_pnl,
                'consecutive_losses': self.consecutive_losses,
                'consecutive_wins': self.consecutive_wins,
                'current_drawdown': self.current_drawdown,
                'risk_level': metrics.risk_level.value,
                'protection_triggered': protection_triggered,
                'automatic_actions': metrics.recommended_action.value if protection_triggered else None
            }
    
    def _calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        # Daily P&L percentage
        daily_pnl_percent = self.daily_pnl / self.initial_balance
        
        # Determine risk level
        risk_level = RiskLevel.NORMAL
        recommended_action = ProtectionAction.CONTINUE
        reasons = []
        
        # Check daily loss cap
        if abs(daily_pnl_percent) >= self.daily_loss_cap * 0.8:  # 80% of limit
            risk_level = RiskLevel.WARNING
            reasons.append(f"Approaching daily loss limit ({abs(daily_pnl_percent):.1%})")
            
        if abs(daily_pnl_percent) >= self.daily_loss_cap:
            risk_level = RiskLevel.CRITICAL
            recommended_action = ProtectionAction.PAUSE_TRADING
            reasons.append(f"Daily loss limit exceeded ({abs(daily_pnl_percent):.1%})")
        
        # Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses - 1:
            risk_level = max(risk_level, RiskLevel.WARNING)
            reasons.append(f"High consecutive losses ({self.consecutive_losses})")
            
        if self.consecutive_losses >= self.max_consecutive_losses:
            risk_level = RiskLevel.CRITICAL
            recommended_action = ProtectionAction.PAUSE_TRADING
            reasons.append(f"Maximum consecutive losses reached ({self.consecutive_losses})")
        
        # Check daily trade limit
        daily_trade_count = len([t for t in self.daily_trades if t['timestamp'].date() == datetime.utcnow().date()])
        if daily_trade_count >= self.max_daily_trades * 0.8:
            risk_level = max(risk_level, RiskLevel.WARNING)
            reasons.append(f"Approaching daily trade limit ({daily_trade_count})")
            
        if daily_trade_count >= self.max_daily_trades:
            risk_level = RiskLevel.CRITICAL
            recommended_action = ProtectionAction.PAUSE_TRADING
            reasons.append(f"Daily trade limit exceeded ({daily_trade_count})")
        
        # Check total drawdown
        if self.current_drawdown >= self.emergency_drawdown_threshold * 0.7:
            risk_level = max(risk_level, RiskLevel.WARNING)
            reasons.append(f"High drawdown warning ({self.current_drawdown:.1%})")
            
        if self.current_drawdown >= self.emergency_drawdown_threshold:
            risk_level = RiskLevel.EMERGENCY
            recommended_action = ProtectionAction.EMERGENCY_STOP
            reasons.append(f"Emergency drawdown threshold exceeded ({self.current_drawdown:.1%})")
        
        # Check for volatility spikes (simplified)
        volatility_spike = self._detect_volatility_spike()
        if volatility_spike:
            risk_level = max(risk_level, RiskLevel.WARNING)
            reasons.append("High market volatility detected")
        
        return RiskMetrics(
            daily_pnl=self.daily_pnl,
            daily_trades=daily_trade_count,
            consecutive_losses=self.consecutive_losses,
            consecutive_wins=self.consecutive_wins,
            current_drawdown=self.current_drawdown,
            max_drawdown=self.max_drawdown,
            volatility_spike=volatility_spike,
            risk_level=risk_level,
            recommended_action=recommended_action,
            reasons=reasons
        )
    
    def _perform_risk_checks(self, proposed_trade: Dict[str, Any], metrics: RiskMetrics) -> Dict[str, Any]:
        """Perform specific risk checks for proposed trade"""
        
        # Base position size adjustment
        position_adjustment = 1.0
        
        # Check daily loss limit
        if abs(metrics.daily_pnl / self.initial_balance) >= self.daily_loss_cap:
            return {
                'allowed': False,
                'reason': f'Daily loss limit exceeded: {abs(metrics.daily_pnl / self.initial_balance):.1%}'
            }
        
        # Check consecutive losses
        if metrics.consecutive_losses >= self.max_consecutive_losses:
            return {
                'allowed': False,
                'reason': f'Maximum consecutive losses ({self.max_consecutive_losses}) reached'
            }
        
        # Check daily trade limit
        if metrics.daily_trades >= self.max_daily_trades:
            return {
                'allowed': False,
                'reason': f'Daily trade limit ({self.max_daily_trades}) exceeded'
            }
        
        # Check emergency drawdown
        if metrics.current_drawdown >= self.emergency_drawdown_threshold:
            return {
                'allowed': False,
                'reason': f'Emergency drawdown threshold ({self.emergency_drawdown_threshold:.1%}) exceeded'
            }
        
        # Risk-based position sizing adjustments
        if metrics.risk_level == RiskLevel.WARNING:
            position_adjustment = 0.5  # Half position size
        elif metrics.risk_level == RiskLevel.CRITICAL:
            position_adjustment = 0.25  # Quarter position size
        
        # Consecutive loss adjustments
        if metrics.consecutive_losses >= 2:
            position_adjustment *= 0.7  # Reduce by 30%
        
        # High drawdown adjustments
        if metrics.current_drawdown >= 0.10:  # 10% drawdown
            position_adjustment *= 0.6  # Reduce by 40%
        
        return {
            'allowed': True,
            'reason': 'Risk checks passed',
            'position_adjustment': position_adjustment
        }
    
    def _check_automatic_protections(self) -> bool:
        """Check and trigger automatic protection measures"""
        protection_triggered = False
        
        # Daily loss cap protection
        daily_loss_percent = abs(self.daily_pnl / self.initial_balance)
        if daily_loss_percent >= self.daily_loss_cap:
            self._pause_trading("Daily loss limit exceeded", hours=24)
            protection_triggered = True
        
        # Consecutive loss protection
        if self.consecutive_losses >= self.max_consecutive_losses:
            pause_hours = min(self.consecutive_losses * 2, 12)  # Max 12 hours
            self._pause_trading(f"Too many consecutive losses ({self.consecutive_losses})", hours=pause_hours)
            protection_triggered = True
        
        # Emergency drawdown protection
        if self.current_drawdown >= self.emergency_drawdown_threshold:
            self._emergency_stop("Emergency drawdown threshold exceeded")
            protection_triggered = True
        
        # Volatility spike protection
        if self._detect_volatility_spike():
            self._pause_trading("High volatility spike detected", hours=1)
            protection_triggered = True
        
        return protection_triggered
    
    def _pause_trading(self, reason: str, hours: int = 1):
        """Pause trading for specified duration"""
        self.trading_paused = True
        self.pause_reason = reason
        self.pause_until = datetime.utcnow() + timedelta(hours=hours)
        
        logging.warning(f"Trading paused for {hours}h: {reason}")
    
    def _emergency_stop(self, reason: str):
        """Trigger emergency stop"""
        self.emergency_stop = True
        self.trading_paused = True
        self.pause_reason = f"EMERGENCY STOP: {reason}"
        
        logging.critical(f"Emergency stop activated: {reason}")
    
    def _resume_trading(self):
        """Resume trading after pause period"""
        if not self.emergency_stop:
            self.trading_paused = False
            self.pause_reason = ""
            self.pause_until = None
            logging.info("Trading resumed automatically")
    
    def manual_resume(self) -> bool:
        """Manually resume trading (emergency stop requires manual intervention)"""
        with self.lock:
            if self.emergency_stop:
                # Require manual confirmation for emergency stops
                return False
            
            self.trading_paused = False
            self.pause_reason = ""
            self.pause_until = None
            logging.info("Trading resumed manually")
            return True
    
    def reset_emergency_stop(self) -> bool:
        """Reset emergency stop (manual intervention required)"""
        with self.lock:
            self.emergency_stop = False
            self.trading_paused = False
            self.pause_reason = ""
            self.pause_until = None
            
            # Reset consecutive losses to break the cycle
            self.consecutive_losses = 0
            
            logging.info("Emergency stop reset manually")
            return True
    
    def _update_drawdown(self):
        """Update drawdown calculations"""
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        if self.peak_balance > 0:
            self.current_drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
        
        # Store drawdown history
        self.drawdown_history.append({
            'timestamp': datetime.utcnow(),
            'balance': self.current_balance,
            'peak': self.peak_balance,
            'drawdown': self.current_drawdown
        })
        
        # Keep only recent history
        if len(self.drawdown_history) > 1000:
            self.drawdown_history = self.drawdown_history[-500:]
    
    def _detect_volatility_spike(self) -> bool:
        """Detect sudden volatility spikes (simplified)"""
        # This would normally use real market data
        # For now, return False as a placeholder
        return False
    
    def _update_daily_reset(self):
        """Reset daily counters if new day"""
        current_date = datetime.utcnow().date()
        if current_date > self.last_reset_date:
            self.daily_pnl = 0.0
            self.daily_trades = []
            self.last_reset_date = current_date
            logging.info("Daily risk counters reset")
    
    def get_risk_status(self) -> Dict[str, Any]:
        """Get comprehensive risk status"""
        with self.lock:
            self._update_daily_reset()
            metrics = self._calculate_risk_metrics()
            
            return {
                'risk_level': metrics.risk_level.value,
                'trading_allowed': not (self.trading_paused or self.emergency_stop),
                'emergency_stop_active': self.emergency_stop,
                'trading_paused': self.trading_paused,
                'pause_reason': self.pause_reason,
                'pause_until': self.pause_until.isoformat() if self.pause_until else None,
                'current_balance': self.current_balance,
                'daily_pnl': self.daily_pnl,
                'daily_pnl_percent': self.daily_pnl / self.initial_balance,
                'daily_trades_count': metrics.daily_trades,
                'consecutive_losses': metrics.consecutive_losses,
                'consecutive_wins': metrics.consecutive_wins,
                'current_drawdown': metrics.current_drawdown,
                'max_drawdown': self.max_drawdown,
                'peak_balance': self.peak_balance,
                'total_return': (self.current_balance - self.initial_balance) / self.initial_balance,
                'limits': {
                    'daily_loss_cap': self.daily_loss_cap,
                    'max_consecutive_losses': self.max_consecutive_losses,
                    'max_daily_trades': self.max_daily_trades,
                    'emergency_drawdown_threshold': self.emergency_drawdown_threshold
                },
                'warnings': metrics.reasons
            }
    
    def update_limits(self, **kwargs) -> bool:
        """Update risk protection limits"""
        try:
            with self.lock:
                if 'daily_loss_cap' in kwargs:
                    self.daily_loss_cap = float(kwargs['daily_loss_cap'])
                if 'max_consecutive_losses' in kwargs:
                    self.max_consecutive_losses = int(kwargs['max_consecutive_losses'])
                if 'max_daily_trades' in kwargs:
                    self.max_daily_trades = int(kwargs['max_daily_trades'])
                if 'emergency_drawdown_threshold' in kwargs:
                    self.emergency_drawdown_threshold = float(kwargs['emergency_drawdown_threshold'])
                
                logging.info(f"Updated risk limits: {kwargs}")
                return True
                
        except Exception as e:
            logging.error(f"Error updating limits: {e}")
            return False
    
    def export_risk_data(self) -> Dict[str, Any]:
        """Export comprehensive risk data for analysis"""
        with self.lock:
            return {
                'configuration': {
                    'initial_balance': self.initial_balance,
                    'daily_loss_cap': self.daily_loss_cap,
                    'max_consecutive_losses': self.max_consecutive_losses,
                    'max_daily_trades': self.max_daily_trades,
                    'emergency_drawdown_threshold': self.emergency_drawdown_threshold
                },
                'current_status': self.get_risk_status(),
                'trade_history': self.daily_trades[-100:],  # Last 100 trades
                'drawdown_history': self.drawdown_history[-100:],  # Last 100 points
                'statistics': {
                    'total_trades': len(self.daily_trades),
                    'total_wins': self.total_wins,
                    'total_losses': self.total_losses,
                    'win_rate': self.total_wins / (self.total_wins + self.total_losses) if (self.total_wins + self.total_losses) > 0 else 0,
                    'best_day': max([sum(t['pnl'] for t in self.daily_trades if t['timestamp'].date() == date) 
                                   for date in set(t['timestamp'].date() for t in self.daily_trades)], default=0),
                    'worst_day': min([sum(t['pnl'] for t in self.daily_trades if t['timestamp'].date() == date) 
                                    for date in set(t['timestamp'].date() for t in self.daily_trades)], default=0)
                },
                'export_timestamp': datetime.utcnow().isoformat()
            }