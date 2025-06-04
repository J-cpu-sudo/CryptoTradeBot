import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import json

class TrailingMode(Enum):
    FIXED_PERCENT = "fixed_percent"
    ATR_BASED = "atr_based"
    VOLATILITY_ADAPTIVE = "volatility_adaptive"

class PositionState(Enum):
    ENTRY = "entry"
    TRAILING_ACTIVE = "trailing_active"
    BREAKEVEN = "breakeven"
    PROFIT_ZONE = "profit_zone"
    CLOSED = "closed"

@dataclass
class TrailingPosition:
    trade_id: int
    symbol: str
    side: str  # 'buy' or 'sell'
    entry_price: float
    quantity: float
    entry_time: datetime
    current_price: float
    highest_price: float  # For long positions
    lowest_price: float   # For short positions
    initial_stop: float
    trailing_stop: float
    take_profit: float
    trail_distance: float
    trail_mode: TrailingMode
    state: PositionState
    unrealized_pnl: float
    roi_percent: float
    activation_threshold: float  # ROI threshold to activate trailing
    last_update: datetime
    metadata: Dict[str, Any]

class DynamicTrailingSystem:
    """Advanced dynamic trailing stop system with profit protection"""
    
    def __init__(self, market_feed=None):
        self.market_feed = market_feed
        self.active_positions: Dict[int, TrailingPosition] = {}
        self.closed_positions: List[TrailingPosition] = []
        
        # Configuration
        self.default_trail_distance = 0.02  # 2%
        self.activation_threshold = 0.015   # 1.5% ROI to activate trailing
        self.breakeven_buffer = 0.005       # 0.5% buffer for breakeven
        self.profit_lock_ratio = 0.5        # Lock 50% of profits
        
        # Performance tracking
        self.total_stops_triggered = 0
        self.profit_locks = 0
        self.breakeven_exits = 0
        
        # Thread safety
        self.lock = threading.Lock()
        self.running = False
        self.update_thread = None
        
        logging.info("Dynamic trailing system initialized")
    
    def add_position(self, trade_id: int, symbol: str, side: str, 
                    entry_price: float, quantity: float,
                    initial_stop: float, take_profit: float,
                    trail_distance: Optional[float] = None,
                    trail_mode: TrailingMode = TrailingMode.FIXED_PERCENT) -> bool:
        """Add a new position for trailing stop management"""
        try:
            with self.lock:
                if trade_id in self.active_positions:
                    logging.warning(f"Position {trade_id} already exists")
                    return False
                
                trail_dist = trail_distance or self.default_trail_distance
                
                position = TrailingPosition(
                    trade_id=trade_id,
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    quantity=quantity,
                    entry_time=datetime.utcnow(),
                    current_price=entry_price,
                    highest_price=entry_price if side == 'buy' else 0,
                    lowest_price=entry_price if side == 'sell' else float('inf'),
                    initial_stop=initial_stop,
                    trailing_stop=initial_stop,
                    take_profit=take_profit,
                    trail_distance=trail_dist,
                    trail_mode=trail_mode,
                    state=PositionState.ENTRY,
                    unrealized_pnl=0.0,
                    roi_percent=0.0,
                    activation_threshold=self.activation_threshold,
                    last_update=datetime.utcnow(),
                    metadata={}
                )
                
                self.active_positions[trade_id] = position
                
                logging.info(f"Added {side} position {trade_id} for {symbol} at {entry_price}")
                return True
                
        except Exception as e:
            logging.error(f"Error adding position: {e}")
            return False
    
    def update_position_price(self, trade_id: int, current_price: float) -> Dict[str, Any]:
        """Update position with current market price and adjust trailing stop"""
        try:
            with self.lock:
                if trade_id not in self.active_positions:
                    return {'error': f'Position {trade_id} not found'}
                
                position = self.active_positions[trade_id]
                old_price = position.current_price
                position.current_price = current_price
                position.last_update = datetime.utcnow()
                
                # Update price extremes
                if position.side == 'buy':
                    if current_price > position.highest_price:
                        position.highest_price = current_price
                else:  # sell
                    if current_price < position.lowest_price:
                        position.lowest_price = current_price
                
                # Calculate unrealized P&L and ROI
                if position.side == 'buy':
                    position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
                else:
                    position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
                
                position.roi_percent = position.unrealized_pnl / (position.entry_price * position.quantity)
                
                # Update trailing stop logic
                update_result = self._update_trailing_stop(position)
                
                # Check for stop trigger
                stop_triggered = self._check_stop_trigger(position)
                
                if stop_triggered:
                    return self._trigger_stop_loss(trade_id)
                
                return {
                    'success': True,
                    'position_id': trade_id,
                    'current_price': current_price,
                    'trailing_stop': position.trailing_stop,
                    'unrealized_pnl': position.unrealized_pnl,
                    'roi_percent': position.roi_percent,
                    'state': position.state.value,
                    'update_result': update_result
                }
                
        except Exception as e:
            logging.error(f"Error updating position price: {e}")
            return {'error': str(e)}
    
    def _update_trailing_stop(self, position: TrailingPosition) -> Dict[str, Any]:
        """Update trailing stop based on price movement and mode"""
        try:
            old_stop = position.trailing_stop
            old_state = position.state
            
            if position.side == 'buy':
                return self._update_long_position(position)
            else:
                return self._update_short_position(position)
                
        except Exception as e:
            logging.error(f"Error updating trailing stop: {e}")
            return {'error': str(e)}
    
    def _update_long_position(self, position: TrailingPosition) -> Dict[str, Any]:
        """Update trailing stop for long position"""
        current_price = position.current_price
        entry_price = position.entry_price
        highest_price = position.highest_price
        
        # Calculate current ROI
        roi = (current_price - entry_price) / entry_price
        
        # State transitions
        if position.state == PositionState.ENTRY:
            # Check if we should activate trailing
            if roi >= position.activation_threshold:
                position.state = PositionState.TRAILING_ACTIVE
                # Set initial trailing stop
                if position.trail_mode == TrailingMode.FIXED_PERCENT:
                    position.trailing_stop = current_price * (1 - position.trail_distance)
                else:
                    position.trailing_stop = self._calculate_adaptive_stop(position)
                
                logging.info(f"Activated trailing for position {position.trade_id} at ROI {roi:.2%}")
                return {'action': 'trailing_activated', 'new_stop': position.trailing_stop}
        
        elif position.state == PositionState.TRAILING_ACTIVE:
            # Update trailing stop if price moved up
            if current_price > highest_price * 0.999:  # Small buffer to avoid noise
                new_stop = self._calculate_new_stop_long(position)
                
                if new_stop > position.trailing_stop:
                    position.trailing_stop = new_stop
                    
                    # Check for breakeven
                    if position.trailing_stop >= entry_price * (1 + self.breakeven_buffer):
                        if position.state != PositionState.BREAKEVEN:
                            position.state = PositionState.BREAKEVEN
                            logging.info(f"Position {position.trade_id} moved to breakeven")
                    
                    # Check for profit zone
                    profit_threshold = entry_price * (1 + position.activation_threshold * 2)
                    if position.trailing_stop >= profit_threshold:
                        if position.state != PositionState.PROFIT_ZONE:
                            position.state = PositionState.PROFIT_ZONE
                            self.profit_locks += 1
                            logging.info(f"Position {position.trade_id} entered profit protection zone")
                    
                    return {'action': 'stop_updated', 'new_stop': position.trailing_stop}
        
        return {'action': 'no_change'}
    
    def _update_short_position(self, position: TrailingPosition) -> Dict[str, Any]:
        """Update trailing stop for short position"""
        current_price = position.current_price
        entry_price = position.entry_price
        lowest_price = position.lowest_price
        
        # Calculate current ROI
        roi = (entry_price - current_price) / entry_price
        
        # State transitions
        if position.state == PositionState.ENTRY:
            # Check if we should activate trailing
            if roi >= position.activation_threshold:
                position.state = PositionState.TRAILING_ACTIVE
                # Set initial trailing stop
                if position.trail_mode == TrailingMode.FIXED_PERCENT:
                    position.trailing_stop = current_price * (1 + position.trail_distance)
                else:
                    position.trailing_stop = self._calculate_adaptive_stop(position)
                
                logging.info(f"Activated trailing for short position {position.trade_id} at ROI {roi:.2%}")
                return {'action': 'trailing_activated', 'new_stop': position.trailing_stop}
        
        elif position.state == PositionState.TRAILING_ACTIVE:
            # Update trailing stop if price moved down
            if current_price < lowest_price * 1.001:  # Small buffer to avoid noise
                new_stop = self._calculate_new_stop_short(position)
                
                if new_stop < position.trailing_stop:
                    position.trailing_stop = new_stop
                    
                    # Check for breakeven
                    if position.trailing_stop <= entry_price * (1 - self.breakeven_buffer):
                        if position.state != PositionState.BREAKEVEN:
                            position.state = PositionState.BREAKEVEN
                            logging.info(f"Short position {position.trade_id} moved to breakeven")
                    
                    # Check for profit zone
                    profit_threshold = entry_price * (1 - position.activation_threshold * 2)
                    if position.trailing_stop <= profit_threshold:
                        if position.state != PositionState.PROFIT_ZONE:
                            position.state = PositionState.PROFIT_ZONE
                            self.profit_locks += 1
                            logging.info(f"Short position {position.trade_id} entered profit protection zone")
                    
                    return {'action': 'stop_updated', 'new_stop': position.trailing_stop}
        
        return {'action': 'no_change'}
    
    def _calculate_new_stop_long(self, position: TrailingPosition) -> float:
        """Calculate new trailing stop for long position"""
        current_price = position.current_price
        
        if position.trail_mode == TrailingMode.FIXED_PERCENT:
            return current_price * (1 - position.trail_distance)
        
        elif position.trail_mode == TrailingMode.ATR_BASED:
            # Use ATR-based trailing (simplified)
            atr_multiplier = 2.0
            estimated_atr = current_price * 0.02  # 2% as ATR estimate
            return current_price - (estimated_atr * atr_multiplier)
        
        elif position.trail_mode == TrailingMode.VOLATILITY_ADAPTIVE:
            return self._calculate_adaptive_stop(position)
        
        return position.trailing_stop
    
    def _calculate_new_stop_short(self, position: TrailingPosition) -> float:
        """Calculate new trailing stop for short position"""
        current_price = position.current_price
        
        if position.trail_mode == TrailingMode.FIXED_PERCENT:
            return current_price * (1 + position.trail_distance)
        
        elif position.trail_mode == TrailingMode.ATR_BASED:
            # Use ATR-based trailing (simplified)
            atr_multiplier = 2.0
            estimated_atr = current_price * 0.02  # 2% as ATR estimate
            return current_price + (estimated_atr * atr_multiplier)
        
        elif position.trail_mode == TrailingMode.VOLATILITY_ADAPTIVE:
            return self._calculate_adaptive_stop(position)
        
        return position.trailing_stop
    
    def _calculate_adaptive_stop(self, position: TrailingPosition) -> float:
        """Calculate volatility-adaptive stop loss"""
        # Simplified adaptive calculation
        base_distance = position.trail_distance
        
        # Adjust based on time in trade (wider stops for longer trades)
        time_factor = min((datetime.utcnow() - position.entry_time).total_seconds() / 3600, 2.0)
        adaptive_distance = base_distance * (1 + time_factor * 0.1)
        
        # Adjust based on ROI (tighter stops in profit)
        if position.roi_percent > 0.05:  # More than 5% profit
            adaptive_distance *= 0.8
        
        if position.side == 'buy':
            return position.current_price * (1 - adaptive_distance)
        else:
            return position.current_price * (1 + adaptive_distance)
    
    def _check_stop_trigger(self, position: TrailingPosition) -> bool:
        """Check if trailing stop should be triggered"""
        current_price = position.current_price
        trailing_stop = position.trailing_stop
        
        if position.side == 'buy':
            return current_price <= trailing_stop
        else:
            return current_price >= trailing_stop
    
    def _trigger_stop_loss(self, trade_id: int) -> Dict[str, Any]:
        """Trigger stop loss for position"""
        try:
            if trade_id not in self.active_positions:
                return {'error': f'Position {trade_id} not found'}
            
            position = self.active_positions[trade_id]
            trigger_price = position.trailing_stop
            
            # Calculate final P&L
            final_pnl = position.unrealized_pnl
            final_roi = position.roi_percent
            
            # Update position state
            position.state = PositionState.CLOSED
            position.metadata['exit_reason'] = 'trailing_stop'
            position.metadata['exit_price'] = trigger_price
            position.metadata['exit_time'] = datetime.utcnow().isoformat()
            position.metadata['final_pnl'] = final_pnl
            position.metadata['final_roi'] = final_roi
            
            # Move to closed positions
            self.closed_positions.append(position)
            del self.active_positions[trade_id]
            
            # Update statistics
            self.total_stops_triggered += 1
            if position.state == PositionState.BREAKEVEN:
                self.breakeven_exits += 1
            
            logging.info(f"Trailing stop triggered for position {trade_id} at {trigger_price}, P&L: {final_pnl:.2f}")
            
            return {
                'triggered': True,
                'trade_id': trade_id,
                'trigger_price': trigger_price,
                'final_pnl': final_pnl,
                'final_roi': final_roi,
                'exit_reason': 'trailing_stop',
                'position_duration': (datetime.utcnow() - position.entry_time).total_seconds()
            }
            
        except Exception as e:
            logging.error(f"Error triggering stop loss: {e}")
            return {'error': str(e)}
    
    def remove_position(self, trade_id: int, exit_reason: str = 'manual') -> bool:
        """Remove position from tracking (for manual exits)"""
        try:
            with self.lock:
                if trade_id in self.active_positions:
                    position = self.active_positions[trade_id]
                    position.state = PositionState.CLOSED
                    position.metadata['exit_reason'] = exit_reason
                    position.metadata['exit_time'] = datetime.utcnow().isoformat()
                    
                    self.closed_positions.append(position)
                    del self.active_positions[trade_id]
                    
                    logging.info(f"Removed position {trade_id} - {exit_reason}")
                    return True
                return False
                
        except Exception as e:
            logging.error(f"Error removing position: {e}")
            return False
    
    def get_position_status(self, trade_id: int) -> Optional[Dict[str, Any]]:
        """Get current status of a position"""
        with self.lock:
            if trade_id in self.active_positions:
                position = self.active_positions[trade_id]
                return {
                    'trade_id': trade_id,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'current_price': position.current_price,
                    'trailing_stop': position.trailing_stop,
                    'unrealized_pnl': position.unrealized_pnl,
                    'roi_percent': position.roi_percent,
                    'state': position.state.value,
                    'trail_distance': position.trail_distance,
                    'time_in_trade': (datetime.utcnow() - position.entry_time).total_seconds(),
                    'last_update': position.last_update.isoformat()
                }
        return None
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get status of all active positions"""
        with self.lock:
            return [self.get_position_status(trade_id) for trade_id in self.active_positions.keys()]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get trailing system performance statistics"""
        with self.lock:
            total_positions = len(self.closed_positions)
            profitable_exits = sum(1 for pos in self.closed_positions if pos.unrealized_pnl > 0)
            
            avg_roi = 0
            if self.closed_positions:
                avg_roi = sum(pos.roi_percent for pos in self.closed_positions) / len(self.closed_positions)
            
            return {
                'active_positions': len(self.active_positions),
                'total_stops_triggered': self.total_stops_triggered,
                'profit_locks': self.profit_locks,
                'breakeven_exits': self.breakeven_exits,
                'total_closed_positions': total_positions,
                'profitable_exits': profitable_exits,
                'win_rate': profitable_exits / total_positions if total_positions > 0 else 0,
                'average_roi': avg_roi,
                'positions_in_profit_zone': sum(1 for pos in self.active_positions.values() 
                                              if pos.state == PositionState.PROFIT_ZONE)
            }
    
    def start_auto_update(self, update_interval: float = 1.0):
        """Start automatic position updates"""
        if self.running:
            return
        
        self.running = True
        
        def update_loop():
            while self.running:
                try:
                    if self.market_feed:
                        # Update all positions with current market prices
                        for trade_id, position in list(self.active_positions.items()):
                            current_price = self.market_feed.get_current_price(position.symbol)
                            if current_price:
                                self.update_position_price(trade_id, current_price)
                    
                    time.sleep(update_interval)
                    
                except Exception as e:
                    logging.error(f"Auto-update error: {e}")
                    time.sleep(5)  # Wait before retrying
        
        self.update_thread = threading.Thread(target=update_loop, daemon=True)
        self.update_thread.start()
        
        logging.info("Started automatic trailing stop updates")
    
    def stop_auto_update(self):
        """Stop automatic position updates"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        logging.info("Stopped automatic trailing stop updates")
    
    def export_performance_data(self) -> Dict[str, Any]:
        """Export detailed performance data"""
        with self.lock:
            return {
                'settings': {
                    'default_trail_distance': self.default_trail_distance,
                    'activation_threshold': self.activation_threshold,
                    'breakeven_buffer': self.breakeven_buffer,
                    'profit_lock_ratio': self.profit_lock_ratio
                },
                'statistics': self.get_performance_stats(),
                'active_positions': [asdict(pos) for pos in self.active_positions.values()],
                'closed_positions': [asdict(pos) for pos in self.closed_positions],
                'export_time': datetime.utcnow().isoformat()
            }
    
    def update_settings(self, **kwargs) -> bool:
        """Update trailing system settings"""
        try:
            with self.lock:
                if 'default_trail_distance' in kwargs:
                    self.default_trail_distance = float(kwargs['default_trail_distance'])
                if 'activation_threshold' in kwargs:
                    self.activation_threshold = float(kwargs['activation_threshold'])
                if 'breakeven_buffer' in kwargs:
                    self.breakeven_buffer = float(kwargs['breakeven_buffer'])
                if 'profit_lock_ratio' in kwargs:
                    self.profit_lock_ratio = float(kwargs['profit_lock_ratio'])
                
                logging.info(f"Updated trailing system settings: {kwargs}")
                return True
                
        except Exception as e:
            logging.error(f"Error updating settings: {e}")
            return False