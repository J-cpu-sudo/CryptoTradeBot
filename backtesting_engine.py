import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"

@dataclass
class BacktestOrder:
    id: str
    timestamp: datetime
    symbol: str
    side: str  # buy/sell
    type: OrderType
    quantity: float
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    filled: bool = False
    fill_price: Optional[float] = None
    fill_timestamp: Optional[datetime] = None

@dataclass
class BacktestPosition:
    symbol: str
    side: PositionSide
    entry_price: float
    quantity: float
    entry_timestamp: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    trailing_stop: Optional[float] = None
    highest_price: float = 0.0
    lowest_price: float = float('inf')

@dataclass
class BacktestMetrics:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_fees: float = 0.0
    net_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    volatility: float = 0.0

class BacktestingEngine:
    """Advanced backtesting engine with paper trading capabilities"""
    
    def __init__(self, initial_balance: float = 10000, fee_rate: float = 0.001):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.fee_rate = fee_rate
        
        # Trading state
        self.orders: List[BacktestOrder] = []
        self.positions: List[BacktestPosition] = []
        self.closed_positions: List[BacktestPosition] = []
        self.balance_history: List[Tuple[datetime, float]] = []
        self.equity_curve: List[float] = []
        
        # Performance tracking
        self.daily_returns: List[float] = []
        self.drawdown_series: List[float] = []
        self.peak_balance = initial_balance
        
        # Paper trading mode
        self.paper_trading = False
        self.real_time_data = []
        
        logging.info(f"Backtesting engine initialized with ${initial_balance:,.2f}")
    
    def set_paper_trading_mode(self, enabled: bool):
        """Enable or disable paper trading mode"""
        self.paper_trading = enabled
        if enabled:
            logging.info("Paper trading mode enabled - using real-time data")
        else:
            logging.info("Backtesting mode enabled - using historical data")
    
    def run_backtest(self, historical_data: pd.DataFrame, strategy_func, 
                    start_date: Optional[datetime] = None, 
                    end_date: Optional[datetime] = None) -> BacktestMetrics:
        """
        Run comprehensive backtest with historical data
        
        Args:
            historical_data: DataFrame with OHLCV data
            strategy_func: Trading strategy function
            start_date: Start date for backtest
            end_date: End date for backtest
            
        Returns:
            BacktestMetrics with performance statistics
        """
        try:
            # Filter data by date range
            if start_date or end_date:
                if start_date:
                    historical_data = historical_data[historical_data.index >= start_date]
                if end_date:
                    historical_data = historical_data[historical_data.index <= end_date]
            
            logging.info(f"Starting backtest from {historical_data.index[0]} to {historical_data.index[-1]}")
            logging.info(f"Total data points: {len(historical_data)}")
            
            # Reset engine state
            self._reset_state()
            
            # Process each bar
            for timestamp, row in historical_data.iterrows():
                current_data = {
                    'timestamp': timestamp,
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume']
                }
                
                # Update positions with current price
                self._update_positions(current_data['close'])
                
                # Process pending orders
                self._process_orders(current_data)
                
                # Generate trading signals
                signals = strategy_func(historical_data.loc[:timestamp])
                
                # Execute trades based on signals
                if signals:
                    self._execute_signals(signals, current_data)
                
                # Update balance history
                total_equity = self._calculate_total_equity(current_data['close'])
                self.balance_history.append((timestamp, total_equity))
                self.equity_curve.append(total_equity)
                
                # Update drawdown tracking
                self._update_drawdown(total_equity)
            
            # Close any remaining positions
            final_price = historical_data.iloc[-1]['close']
            self._close_all_positions(final_price, historical_data.index[-1])
            
            # Calculate final metrics
            metrics = self._calculate_metrics()
            
            logging.info(f"Backtest completed - Net P&L: ${metrics.net_pnl:,.2f}")
            logging.info(f"Win Rate: {metrics.win_rate:.1%}, Total Trades: {metrics.total_trades}")
            
            return metrics
            
        except Exception as e:
            logging.error(f"Backtest error: {e}")
            raise
    
    def place_order(self, symbol: str, side: str, quantity: float, 
                   order_type: OrderType = OrderType.MARKET, 
                   price: Optional[float] = None,
                   stop_loss: Optional[float] = None,
                   take_profit: Optional[float] = None) -> str:
        """Place an order in backtesting or paper trading mode"""
        order_id = f"order_{len(self.orders)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        order = BacktestOrder(
            id=order_id,
            timestamp=datetime.now(),
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            price=price or 0,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        self.orders.append(order)
        logging.info(f"Order placed: {side} {quantity} {symbol} at {price or 'market'}")
        
        return order_id
    
    def update_trailing_stop(self, position_symbol: str, trail_distance: float, current_price: float):
        """Update trailing stop for a position"""
        for position in self.positions:
            if position.symbol == position_symbol:
                if position.side == PositionSide.LONG:
                    # For long positions, trailing stop moves up
                    if current_price > position.highest_price:
                        position.highest_price = current_price
                        new_stop = current_price * (1 - trail_distance)
                        if position.trailing_stop is None or new_stop > position.trailing_stop:
                            position.trailing_stop = new_stop
                            logging.info(f"Trailing stop updated to {new_stop:.2f} for {position_symbol}")
                
                elif position.side == PositionSide.SHORT:
                    # For short positions, trailing stop moves down
                    if current_price < position.lowest_price:
                        position.lowest_price = current_price
                        new_stop = current_price * (1 + trail_distance)
                        if position.trailing_stop is None or new_stop < position.trailing_stop:
                            position.trailing_stop = new_stop
                            logging.info(f"Trailing stop updated to {new_stop:.2f} for {position_symbol}")
    
    def get_position(self, symbol: str) -> Optional[BacktestPosition]:
        """Get current position for symbol"""
        for position in self.positions:
            if position.symbol == symbol:
                return position
        return None
    
    def get_open_positions(self) -> List[BacktestPosition]:
        """Get all open positions"""
        return self.positions.copy()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary"""
        metrics = self._calculate_metrics()
        current_equity = self._calculate_total_equity()
        
        return {
            'current_balance': self.current_balance,
            'total_equity': current_equity,
            'total_return': (current_equity - self.initial_balance) / self.initial_balance,
            'total_trades': len(self.closed_positions),
            'open_positions': len(self.positions),
            'win_rate': metrics.win_rate,
            'profit_factor': metrics.profit_factor,
            'max_drawdown': metrics.max_drawdown,
            'sharpe_ratio': metrics.sharpe_ratio
        }
    
    def export_results(self, filename: str):
        """Export backtest results to JSON file"""
        results = {
            'settings': {
                'initial_balance': self.initial_balance,
                'fee_rate': self.fee_rate,
                'paper_trading': self.paper_trading
            },
            'metrics': asdict(self._calculate_metrics()),
            'trades': [self._position_to_dict(pos) for pos in self.closed_positions],
            'equity_curve': self.equity_curve,
            'balance_history': [(ts.isoformat(), bal) for ts, bal in self.balance_history]
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logging.info(f"Results exported to {filename}")
    
    def _reset_state(self):
        """Reset engine state for new backtest"""
        self.current_balance = self.initial_balance
        self.orders.clear()
        self.positions.clear()
        self.closed_positions.clear()
        self.balance_history.clear()
        self.equity_curve.clear()
        self.daily_returns.clear()
        self.drawdown_series.clear()
        self.peak_balance = self.initial_balance
    
    def _update_positions(self, current_price: float):
        """Update all positions with current market price"""
        for position in self.positions:
            position.current_price = current_price
            
            # Calculate unrealized P&L
            if position.side == PositionSide.LONG:
                position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
            else:
                position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
    
    def _process_orders(self, market_data: Dict[str, Any]):
        """Process pending orders against market data"""
        executed_orders = []
        
        for order in self.orders:
            if order.filled:
                continue
            
            # Check if order should be filled
            if self._should_fill_order(order, market_data):
                fill_price = self._get_fill_price(order, market_data)
                order.filled = True
                order.fill_price = fill_price
                order.fill_timestamp = market_data['timestamp']
                
                # Execute the order
                self._execute_order(order, fill_price, market_data['timestamp'])
                executed_orders.append(order)
        
        # Remove executed orders
        self.orders = [o for o in self.orders if not o.filled]
    
    def _should_fill_order(self, order: BacktestOrder, market_data: Dict[str, Any]) -> bool:
        """Determine if order should be filled based on market data"""
        if order.type == OrderType.MARKET:
            return True
        
        elif order.type == OrderType.LIMIT:
            if order.side == 'buy':
                return market_data['low'] <= order.price
            else:
                return market_data['high'] >= order.price
        
        elif order.type == OrderType.STOP_LOSS:
            if order.side == 'sell':
                return market_data['low'] <= order.price
            else:
                return market_data['high'] >= order.price
        
        return False
    
    def _get_fill_price(self, order: BacktestOrder, market_data: Dict[str, Any]) -> float:
        """Get realistic fill price for order"""
        if order.type == OrderType.MARKET:
            # Market orders get filled at open price (next bar)
            return market_data['open']
        
        elif order.type == OrderType.LIMIT:
            # Limit orders get filled at limit price or better
            return order.price
        
        elif order.type == OrderType.STOP_LOSS:
            # Stop orders might get slippage
            slippage = 0.001  # 0.1% slippage
            if order.side == 'sell':
                return order.price * (1 - slippage)
            else:
                return order.price * (1 + slippage)
        
        return order.price
    
    def _execute_order(self, order: BacktestOrder, fill_price: float, timestamp: datetime):
        """Execute a filled order"""
        cost = order.quantity * fill_price
        fee = cost * self.fee_rate
        
        if order.side == 'buy':
            # Check if we have enough balance
            total_cost = cost + fee
            if total_cost > self.current_balance:
                logging.warning(f"Insufficient balance for order {order.id}")
                return
            
            # Deduct balance
            self.current_balance -= total_cost
            
            # Create or add to position
            self._add_position(order, fill_price, timestamp)
        
        else:  # sell
            # Close position
            self._close_position(order, fill_price, timestamp)
            self.current_balance += cost - fee
    
    def _add_position(self, order: BacktestOrder, fill_price: float, timestamp: datetime):
        """Add new position or increase existing position"""
        side = PositionSide.LONG if order.side == 'buy' else PositionSide.SHORT
        
        # Check if we already have a position in this symbol
        existing_position = self.get_position(order.symbol)
        
        if existing_position and existing_position.side == side:
            # Add to existing position (average price)
            total_quantity = existing_position.quantity + order.quantity
            total_value = (existing_position.entry_price * existing_position.quantity + 
                          fill_price * order.quantity)
            existing_position.entry_price = total_value / total_quantity
            existing_position.quantity = total_quantity
        else:
            # Create new position
            position = BacktestPosition(
                symbol=order.symbol,
                side=side,
                entry_price=fill_price,
                quantity=order.quantity,
                entry_timestamp=timestamp,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                current_price=fill_price,
                highest_price=fill_price,
                lowest_price=fill_price
            )
            self.positions.append(position)
        
        logging.info(f"Position opened: {side.value} {order.quantity} {order.symbol} at {fill_price:.2f}")
    
    def _close_position(self, order: BacktestOrder, fill_price: float, timestamp: datetime):
        """Close position and calculate P&L"""
        position = self.get_position(order.symbol)
        if not position:
            logging.warning(f"No position found for {order.symbol}")
            return
        
        # Calculate P&L
        if position.side == PositionSide.LONG:
            pnl = (fill_price - position.entry_price) * order.quantity
        else:
            pnl = (position.entry_price - fill_price) * order.quantity
        
        # Calculate fees
        entry_fee = position.entry_price * order.quantity * self.fee_rate
        exit_fee = fill_price * order.quantity * self.fee_rate
        total_fees = entry_fee + exit_fee
        net_pnl = pnl - total_fees
        
        # Update position for closing
        position.current_price = fill_price
        position.unrealized_pnl = net_pnl
        
        # Move to closed positions
        self.closed_positions.append(position)
        self.positions.remove(position)
        
        logging.info(f"Position closed: {position.side.value} {order.quantity} {order.symbol} "
                    f"at {fill_price:.2f}, P&L: ${net_pnl:.2f}")
    
    def _close_all_positions(self, final_price: float, timestamp: datetime):
        """Close all remaining positions at backtest end"""
        for position in self.positions.copy():
            # Create closing order
            side = 'sell' if position.side == PositionSide.LONG else 'buy'
            close_order = BacktestOrder(
                id=f"close_{position.symbol}",
                timestamp=timestamp,
                symbol=position.symbol,
                side=side,
                type=OrderType.MARKET,
                quantity=position.quantity,
                price=final_price
            )
            
            self._close_position(close_order, final_price, timestamp)
    
    def _calculate_total_equity(self, current_price: Optional[float] = None) -> float:
        """Calculate total account equity including unrealized P&L"""
        total_equity = self.current_balance
        
        for position in self.positions:
            if current_price:
                self._update_positions(current_price)
            total_equity += position.unrealized_pnl
        
        return total_equity
    
    def _update_drawdown(self, current_equity: float):
        """Update drawdown tracking"""
        if current_equity > self.peak_balance:
            self.peak_balance = current_equity
        
        drawdown = (self.peak_balance - current_equity) / self.peak_balance
        self.drawdown_series.append(drawdown)
    
    def _calculate_metrics(self) -> BacktestMetrics:
        """Calculate comprehensive backtest metrics"""
        if not self.closed_positions:
            return BacktestMetrics()
        
        # Basic trade statistics
        total_trades = len(self.closed_positions)
        winning_trades = sum(1 for pos in self.closed_positions if pos.unrealized_pnl > 0)
        losing_trades = total_trades - winning_trades
        
        # P&L calculations
        total_pnl = sum(pos.unrealized_pnl for pos in self.closed_positions)
        wins = [pos.unrealized_pnl for pos in self.closed_positions if pos.unrealized_pnl > 0]
        losses = [pos.unrealized_pnl for pos in self.closed_positions if pos.unrealized_pnl < 0]
        
        # Calculate metrics
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0
        
        # Risk metrics
        max_drawdown = max(self.drawdown_series) if self.drawdown_series else 0
        
        # Returns and ratios
        final_equity = self.equity_curve[-1] if self.equity_curve else self.initial_balance
        total_return = (final_equity - self.initial_balance) / self.initial_balance
        
        # Calculate Sharpe ratio if we have enough data
        if len(self.equity_curve) > 1:
            returns = [(self.equity_curve[i] - self.equity_curve[i-1]) / self.equity_curve[i-1] 
                      for i in range(1, len(self.equity_curve))]
            returns_array = np.array(returns)
            sharpe_ratio = np.mean(returns_array) / np.std(returns_array) * np.sqrt(252) if np.std(returns_array) > 0 else 0
        else:
            sharpe_ratio = 0
        
        return BacktestMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            net_pnl=total_pnl,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            largest_win=max(wins) if wins else 0,
            largest_loss=min(losses) if losses else 0,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio
        )
    
    def _execute_signals(self, signals: Dict[str, Any], market_data: Dict[str, Any]):
        """Execute trading signals"""
        if signals.get('action') in ['buy', 'sell']:
            symbol = signals.get('symbol', 'BTC-USDT')
            quantity = signals.get('quantity', 0.01)
            
            self.place_order(
                symbol=symbol,
                side=signals['action'],
                quantity=quantity,
                order_type=OrderType.MARKET,
                stop_loss=signals.get('stop_loss'),
                take_profit=signals.get('take_profit')
            )
    
    def _position_to_dict(self, position: BacktestPosition) -> Dict[str, Any]:
        """Convert position to dictionary for export"""
        return {
            'symbol': position.symbol,
            'side': position.side.value,
            'entry_price': position.entry_price,
            'quantity': position.quantity,
            'entry_timestamp': position.entry_timestamp.isoformat(),
            'pnl': position.unrealized_pnl,
            'return_pct': position.unrealized_pnl / (position.entry_price * position.quantity)
        }


class RiskAnalyzer:
    """Advanced risk analysis for backtesting and live trading"""
    
    def __init__(self):
        self.max_drawdown_threshold = 0.20  # 20% max drawdown
        self.risk_per_trade = 0.02  # 2% risk per trade
        self.max_correlation = 0.7  # Maximum correlation between positions
        
    def analyze_portfolio_risk(self, positions: List[BacktestPosition], 
                             current_prices: Dict[str, float]) -> Dict[str, Any]:
        """Analyze portfolio-level risk metrics"""
        if not positions:
            return {'status': 'no_positions', 'risk_level': 'low'}
        
        # Calculate position values
        total_value = 0
        position_values = {}
        
        for position in positions:
            current_price = current_prices.get(position.symbol, position.current_price)
            position_value = position.quantity * current_price
            position_values[position.symbol] = position_value
            total_value += abs(position_value)
        
        # Concentration risk
        max_position_pct = max(abs(val) / total_value for val in position_values.values()) if total_value > 0 else 0
        
        # Calculate portfolio beta (simplified)
        portfolio_beta = self._calculate_portfolio_beta(positions, current_prices)
        
        # Risk level determination
        risk_level = 'low'
        if max_position_pct > 0.3 or portfolio_beta > 1.5:
            risk_level = 'high'
        elif max_position_pct > 0.2 or portfolio_beta > 1.2:
            risk_level = 'medium'
        
        return {
            'status': 'analyzed',
            'risk_level': risk_level,
            'max_position_concentration': max_position_pct,
            'portfolio_beta': portfolio_beta,
            'total_exposure': total_value,
            'position_count': len(positions),
            'recommendations': self._generate_risk_recommendations(max_position_pct, portfolio_beta)
        }
    
    def check_drawdown_limits(self, equity_curve: List[float], 
                            peak_balance: float) -> Dict[str, Any]:
        """Check if drawdown limits are exceeded"""
        if not equity_curve:
            return {'status': 'no_data', 'action': 'continue'}
        
        current_equity = equity_curve[-1]
        current_drawdown = (peak_balance - current_equity) / peak_balance
        
        if current_drawdown >= self.max_drawdown_threshold:
            return {
                'status': 'limit_exceeded',
                'action': 'stop_trading',
                'current_drawdown': current_drawdown,
                'threshold': self.max_drawdown_threshold,
                'message': f"Maximum drawdown of {self.max_drawdown_threshold:.1%} exceeded"
            }
        
        elif current_drawdown >= self.max_drawdown_threshold * 0.8:
            return {
                'status': 'warning',
                'action': 'reduce_risk',
                'current_drawdown': current_drawdown,
                'threshold': self.max_drawdown_threshold,
                'message': f"Approaching maximum drawdown limit"
            }
        
        return {
            'status': 'normal',
            'action': 'continue',
            'current_drawdown': current_drawdown
        }
    
    def _calculate_portfolio_beta(self, positions: List[BacktestPosition], 
                                current_prices: Dict[str, float]) -> float:
        """Calculate simplified portfolio beta"""
        # This is a simplified calculation
        # In practice, you'd need historical correlation data
        total_beta = 0
        total_weight = 0
        
        for position in positions:
            # Assume crypto has beta of 1.5, major pairs 1.0
            asset_beta = 1.5 if 'BTC' in position.symbol or 'ETH' in position.symbol else 1.0
            
            current_price = current_prices.get(position.symbol, position.current_price)
            position_value = abs(position.quantity * current_price)
            
            total_beta += asset_beta * position_value
            total_weight += position_value
        
        return total_beta / total_weight if total_weight > 0 else 1.0
    
    def _generate_risk_recommendations(self, concentration: float, beta: float) -> List[str]:
        """Generate risk management recommendations"""
        recommendations = []
        
        if concentration > 0.3:
            recommendations.append("High position concentration detected - consider diversification")
        
        if beta > 1.5:
            recommendations.append("High portfolio beta - consider reducing leverage or position sizes")
        
        if concentration > 0.2 and beta > 1.2:
            recommendations.append("Both concentration and beta risks elevated - implement strict position sizing")
        
        if not recommendations:
            recommendations.append("Portfolio risk levels are within acceptable ranges")
        
        return recommendations