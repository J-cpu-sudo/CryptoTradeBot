import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from models import Trade, BotConfig

class RiskManager:
    def __init__(self, db):
        self.db = db
        
    def calculate_position_size(self, 
                              account_balance: float, 
                              risk_percent: float = 2.0,
                              entry_price: float = 0,
                              stop_loss_price: float = 0) -> Dict[str, Any]:
        """
        Calculate position size based on risk management rules
        
        Args:
            account_balance: Available account balance
            risk_percent: Percentage of account to risk per trade
            entry_price: Entry price for the position
            stop_loss_price: Stop loss price
            
        Returns:
            Dictionary with position size and risk details
        """
        try:
            if not all([account_balance, entry_price, stop_loss_price]):
                return {'error': 'Missing required parameters for position sizing'}
            
            # Calculate risk amount (2% of account balance by default)
            risk_amount = account_balance * (risk_percent / 100)
            
            # Calculate price difference (risk per unit)
            price_diff = abs(entry_price - stop_loss_price)
            if price_diff == 0:
                return {'error': 'Entry price and stop loss cannot be the same'}
            
            # Calculate position size
            position_size = risk_amount / price_diff
            
            # Calculate position value
            position_value = position_size * entry_price
            
            # Check if position value exceeds account balance
            max_position_value = account_balance * 0.8  # Max 80% of balance per trade
            if position_value > max_position_value:
                position_size = max_position_value / entry_price
                actual_risk = position_size * price_diff
                risk_amount = actual_risk
            
            return {
                'position_size': round(position_size, 8),
                'position_value': round(position_value, 2),
                'risk_amount': round(risk_amount, 2),
                'risk_percent': round((risk_amount / account_balance) * 100, 2),
                'price_diff': round(price_diff, 2)
            }
            
        except Exception as e:
            logging.error(f"Error calculating position size: {e}")
            return {'error': str(e)}
    
    def validate_trade(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate if a trade meets risk management criteria
        
        Args:
            trade_params: Dictionary containing trade parameters
            
        Returns:
            Dictionary with validation result and reasons
        """
        try:
            symbol = trade_params.get('symbol', 'BTC-USDT')
            trade_type = trade_params.get('trade_type')
            quantity = trade_params.get('quantity', 0)
            price = trade_params.get('price', 0)
            
            validation_errors = []
            warnings = []
            
            # Check daily trade limit
            if not self._check_daily_trade_limit():
                validation_errors.append("Daily trade limit exceeded")
            
            # Check position concentration
            concentration_check = self._check_position_concentration(symbol, quantity * price)
            if not concentration_check['valid']:
                validation_errors.append(concentration_check['reason'])
            
            # Check recent trade frequency
            frequency_check = self._check_trade_frequency()
            if not frequency_check['valid']:
                if frequency_check['severity'] == 'error':
                    validation_errors.append(frequency_check['reason'])
                else:
                    warnings.append(frequency_check['reason'])
            
            # Check drawdown limits
            drawdown_check = self._check_drawdown_limits()
            if not drawdown_check['valid']:
                validation_errors.append(drawdown_check['reason'])
            
            # Check minimum trade size
            if quantity * price < 10:  # Minimum $10 trade
                validation_errors.append("Trade size too small (minimum $10)")
            
            return {
                'valid': len(validation_errors) == 0,
                'errors': validation_errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logging.error(f"Error validating trade: {e}")
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': []
            }
    
    def _check_daily_trade_limit(self) -> bool:
        """Check if daily trade limit has been reached"""
        max_trades = int(BotConfig.get_value('max_trades_per_day', '10'))
        
        today = datetime.utcnow().date()
        today_trades = Trade.query.filter(
            Trade.timestamp >= datetime.combine(today, datetime.min.time())
        ).count()
        
        return today_trades < max_trades
    
    def _check_position_concentration(self, symbol: str, position_value: float) -> Dict[str, Any]:
        """Check if position concentration is within limits"""
        try:
            # Get current open positions for this symbol
            open_trades = Trade.query.filter(
                Trade.symbol == symbol,
                Trade.status.in_(['pending', 'executed'])
            ).all()
            
            current_exposure = sum(trade.quantity * trade.price for trade in open_trades)
            total_exposure = current_exposure + position_value
            
            # Maximum 30% exposure to single symbol
            # This would need account balance to calculate properly
            # For now, use a simple absolute limit
            max_exposure = 5000  # $5000 max per symbol
            
            if total_exposure > max_exposure:
                return {
                    'valid': False,
                    'reason': f"Position concentration risk: ${total_exposure:.2f} exposure to {symbol} exceeds limit"
                }
            
            return {'valid': True}
            
        except Exception as e:
            logging.error(f"Error checking position concentration: {e}")
            return {'valid': True}  # Allow trade if check fails
    
    def _check_trade_frequency(self) -> Dict[str, Any]:
        """Check trade frequency to prevent overtrading"""
        try:
            # Check trades in last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_trades = Trade.query.filter(
                Trade.timestamp >= one_hour_ago
            ).count()
            
            if recent_trades >= 5:
                return {
                    'valid': False,
                    'severity': 'error',
                    'reason': f"Too many trades in last hour: {recent_trades}"
                }
            elif recent_trades >= 3:
                return {
                    'valid': True,
                    'severity': 'warning',
                    'reason': f"High trade frequency: {recent_trades} trades in last hour"
                }
            
            return {'valid': True}
            
        except Exception as e:
            logging.error(f"Error checking trade frequency: {e}")
            return {'valid': True}
    
    def _check_drawdown_limits(self) -> Dict[str, Any]:
        """Check if current drawdown is within acceptable limits"""
        try:
            # Calculate current daily P&L
            today = datetime.utcnow().date()
            daily_pnl = self.db.session.query(
                self.db.func.sum(Trade.pnl)
            ).filter(
                Trade.timestamp >= datetime.combine(today, datetime.min.time())
            ).scalar() or 0.0
            
            # Stop trading if daily loss exceeds 5%
            # This would need account balance to calculate properly
            max_daily_loss = -500  # $500 max daily loss
            
            if daily_pnl < max_daily_loss:
                return {
                    'valid': False,
                    'reason': f"Daily drawdown limit exceeded: ${daily_pnl:.2f}"
                }
            
            return {'valid': True}
            
        except Exception as e:
            logging.error(f"Error checking drawdown limits: {e}")
            return {'valid': True}
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics and statistics"""
        try:
            # Get recent performance data
            week_ago = datetime.utcnow() - timedelta(days=7)
            month_ago = datetime.utcnow() - timedelta(days=30)
            
            # Weekly P&L
            weekly_pnl = self.db.session.query(
                self.db.func.sum(Trade.pnl)
            ).filter(
                Trade.timestamp >= week_ago
            ).scalar() or 0.0
            
            # Monthly P&L
            monthly_pnl = self.db.session.query(
                self.db.func.sum(Trade.pnl)
            ).filter(
                Trade.timestamp >= month_ago
            ).scalar() or 0.0
            
            # Win rate calculation
            total_trades = Trade.query.filter(
                Trade.timestamp >= month_ago,
                Trade.pnl != 0
            ).count()
            
            winning_trades = Trade.query.filter(
                Trade.timestamp >= month_ago,
                Trade.pnl > 0
            ).count()
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Average trade size
            avg_trade_size = self.db.session.query(
                self.db.func.avg(Trade.quantity * Trade.price)
            ).filter(
                Trade.timestamp >= month_ago
            ).scalar() or 0.0
            
            return {
                'weekly_pnl': round(weekly_pnl, 2),
                'monthly_pnl': round(monthly_pnl, 2),
                'win_rate': round(win_rate, 1),
                'total_trades_month': total_trades,
                'winning_trades_month': winning_trades,
                'avg_trade_size': round(avg_trade_size, 2),
                'risk_percent': float(BotConfig.get_value('risk_percent', '2.0')),
                'max_daily_trades': int(BotConfig.get_value('max_trades_per_day', '10'))
            }
            
        except Exception as e:
            logging.error(f"Error getting risk metrics: {e}")
            return {}
