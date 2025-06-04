import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from models import Trade, BotConfig, BotLog, TradeStatus
import json

class TrailingStopManager:
    """Manages trailing stop losses for open positions"""
    
    def __init__(self, db, trader):
        self.db = db
        self.trader = trader
        self.active_trailing_stops = {}
        
    def add_trailing_stop(self, trade_id: int, initial_stop_distance: float = 0.02) -> bool:
        """Add a trailing stop for a trade"""
        try:
            trade = Trade.query.get(trade_id)
            if not trade or trade.status != TradeStatus.EXECUTED:
                return False
            
            current_price = self._get_current_price(trade.symbol)
            if not current_price:
                return False
            
            # Calculate initial stop loss based on trade direction
            if trade.trade_type.value == 'buy':
                stop_loss = current_price * (1 - initial_stop_distance)
                trail_direction = 1  # Trail up for long positions
            else:
                stop_loss = current_price * (1 + initial_stop_distance)
                trail_direction = -1  # Trail down for short positions
            
            trailing_stop = {
                'trade_id': trade_id,
                'symbol': trade.symbol,
                'trade_type': trade.trade_type.value,
                'entry_price': trade.price,
                'current_stop': stop_loss,
                'trail_distance': initial_stop_distance,
                'trail_direction': trail_direction,
                'highest_price': current_price if trail_direction == 1 else None,
                'lowest_price': current_price if trail_direction == -1 else None,
                'created_at': datetime.utcnow(),
                'last_updated': datetime.utcnow()
            }
            
            self.active_trailing_stops[trade_id] = trailing_stop
            
            # Update trade with trailing stop info
            trade.stop_loss = stop_loss
            trade.notes = (trade.notes or '') + f' | Trailing stop activated at {stop_loss:.2f}'
            self.db.session.commit()
            
            logging.info(f"Trailing stop added for trade {trade_id} at {stop_loss:.2f}")
            return True
            
        except Exception as e:
            logging.error(f"Error adding trailing stop for trade {trade_id}: {e}")
            return False
    
    def update_trailing_stops(self) -> List[Dict[str, Any]]:
        """Update all active trailing stops and check for triggers"""
        triggered_stops = []
        
        for trade_id, stop_info in list(self.active_trailing_stops.items()):
            try:
                current_price = self._get_current_price(stop_info['symbol'])
                if not current_price:
                    continue
                
                # Check if stop should be updated
                stop_updated = False
                
                if stop_info['trail_direction'] == 1:  # Long position
                    # Update highest price seen
                    if current_price > stop_info['highest_price']:
                        stop_info['highest_price'] = current_price
                        
                        # Calculate new trailing stop
                        new_stop = current_price * (1 - stop_info['trail_distance'])
                        
                        # Only move stop up, never down
                        if new_stop > stop_info['current_stop']:
                            stop_info['current_stop'] = new_stop
                            stop_updated = True
                            
                    # Check if stop loss is triggered
                    if current_price <= stop_info['current_stop']:
                        triggered_stops.append(self._trigger_stop_loss(trade_id, current_price))
                        
                else:  # Short position
                    # Update lowest price seen
                    if current_price < stop_info['lowest_price']:
                        stop_info['lowest_price'] = current_price
                        
                        # Calculate new trailing stop
                        new_stop = current_price * (1 + stop_info['trail_distance'])
                        
                        # Only move stop down, never up
                        if new_stop < stop_info['current_stop']:
                            stop_info['current_stop'] = new_stop
                            stop_updated = True
                            
                    # Check if stop loss is triggered
                    if current_price >= stop_info['current_stop']:
                        triggered_stops.append(self._trigger_stop_loss(trade_id, current_price))
                
                if stop_updated:
                    stop_info['last_updated'] = datetime.utcnow()
                    
                    # Update trade record
                    trade = Trade.query.get(trade_id)
                    if trade:
                        trade.stop_loss = stop_info['current_stop']
                        self.db.session.commit()
                        
                    logging.info(f"Trailing stop updated for trade {trade_id}: {stop_info['current_stop']:.2f}")
                    
            except Exception as e:
                logging.error(f"Error updating trailing stop for trade {trade_id}: {e}")
                
        return triggered_stops
    
    def _trigger_stop_loss(self, trade_id: int, trigger_price: float) -> Dict[str, Any]:
        """Execute stop loss for a trade"""
        try:
            trade = Trade.query.get(trade_id)
            stop_info = self.active_trailing_stops.get(trade_id)
            
            if not trade or not stop_info:
                return {'error': f'Trade or stop info not found for {trade_id}'}
            
            # Execute the stop loss order
            if stop_info['trade_type'] == 'buy':
                # Close long position with sell order
                order_result = self.trader.sell(trade.symbol, str(trade.quantity))
            else:
                # Close short position with buy order
                order_result = self.trader.buy(trade.symbol, str(trade.quantity))
            
            # Calculate P&L
            if stop_info['trade_type'] == 'buy':
                pnl = (trigger_price - trade.price) * trade.quantity
            else:
                pnl = (trade.price - trigger_price) * trade.quantity
            
            # Update trade record
            trade.pnl = pnl
            trade.status = TradeStatus.EXECUTED
            trade.notes = (trade.notes or '') + f' | Stop loss triggered at {trigger_price:.2f}'
            
            if order_result:
                trade.notes += f' | Exit order: {order_result.get("ordId")}'
            
            self.db.session.commit()
            
            # Remove from active trailing stops
            del self.active_trailing_stops[trade_id]
            
            # Log the stop loss execution
            self._log_stop_loss(trade_id, trigger_price, pnl)
            
            logging.info(f"Stop loss triggered for trade {trade_id} at {trigger_price:.2f}, P&L: {pnl:.2f}")
            
            return {
                'trade_id': trade_id,
                'trigger_price': trigger_price,
                'pnl': pnl,
                'order_result': order_result
            }
            
        except Exception as e:
            logging.error(f"Error triggering stop loss for trade {trade_id}: {e}")
            return {'error': str(e)}
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        try:
            ticker = self.trader.get_ticker(symbol)
            if ticker and 'last' in ticker:
                return float(ticker['last'])
        except Exception as e:
            logging.error(f"Error getting current price for {symbol}: {e}")
        return None
    
    def _log_stop_loss(self, trade_id: int, trigger_price: float, pnl: float):
        """Log stop loss execution to database"""
        try:
            log_entry = BotLog(
                level='INFO',
                message=f'Trailing stop loss triggered for trade {trade_id}',
                component='trailing_stop',
                details=json.dumps({
                    'trade_id': trade_id,
                    'trigger_price': trigger_price,
                    'pnl': pnl,
                    'timestamp': datetime.utcnow().isoformat()
                })
            )
            self.db.session.add(log_entry)
            self.db.session.commit()
        except Exception as e:
            logging.error(f"Error logging stop loss: {e}")
    
    def remove_trailing_stop(self, trade_id: int) -> bool:
        """Remove a trailing stop for a trade"""
        if trade_id in self.active_trailing_stops:
            del self.active_trailing_stops[trade_id]
            logging.info(f"Trailing stop removed for trade {trade_id}")
            return True
        return False
    
    def get_active_stops(self) -> Dict[int, Dict[str, Any]]:
        """Get all active trailing stops"""
        return self.active_trailing_stops.copy()
    
    def cleanup_expired_stops(self, max_age_hours: int = 24) -> int:
        """Remove trailing stops for trades older than specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        removed_count = 0
        
        for trade_id, stop_info in list(self.active_trailing_stops.items()):
            if stop_info['created_at'] < cutoff_time:
                del self.active_trailing_stops[trade_id]
                removed_count += 1
                logging.info(f"Expired trailing stop removed for trade {trade_id}")
        
        return removed_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trailing stop statistics"""
        return {
            'active_stops': len(self.active_trailing_stops),
            'stops_by_symbol': self._get_stops_by_symbol(),
            'average_trail_distance': self._get_average_trail_distance(),
            'oldest_stop_age': self._get_oldest_stop_age()
        }
    
    def _get_stops_by_symbol(self) -> Dict[str, int]:
        """Count active stops by symbol"""
        symbol_counts = {}
        for stop_info in self.active_trailing_stops.values():
            symbol = stop_info['symbol']
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        return symbol_counts
    
    def _get_average_trail_distance(self) -> float:
        """Calculate average trail distance across all stops"""
        if not self.active_trailing_stops:
            return 0.0
        
        total_distance = sum(stop['trail_distance'] for stop in self.active_trailing_stops.values())
        return total_distance / len(self.active_trailing_stops)
    
    def _get_oldest_stop_age(self) -> Optional[float]:
        """Get age of oldest trailing stop in hours"""
        if not self.active_trailing_stops:
            return None
        
        oldest_time = min(stop['created_at'] for stop in self.active_trailing_stops.values())
        age_delta = datetime.utcnow() - oldest_time
        return age_delta.total_seconds() / 3600  # Convert to hours