import logging
from datetime import datetime
from typing import Dict, Any, Optional
from trader import Trader
from signals.signal_generator import SignalGenerator
from market_analyzer import MarketAnalyzer
from risk_manager import RiskManager
from models import Trade, BotLog, BotConfig, TradeType, TradeStatus
import json

def run_bot_cycle(trader: Trader, risk_manager: RiskManager, market_analyzer: MarketAnalyzer, db) -> Dict[str, Any]:
    """
    Execute one complete trading cycle
    
    Args:
        trader: Trader instance for executing trades
        risk_manager: RiskManager instance for position sizing and validation
        market_analyzer: MarketAnalyzer instance for market data
        db: Database session
        
    Returns:
        Dictionary with cycle results and any errors
    """
    try:
        # Get configuration
        symbol = BotConfig.get_value('symbol', 'BTC-USDT')
        dry_run = BotConfig.get_value('dry_run', 'true').lower() == 'true'
        min_signal_strength = float(BotConfig.get_value('min_signal_strength', '0.7'))
        
        logging.info(f"Starting trading cycle for {symbol} (dry_run: {dry_run})")
        
        # Initialize signal generator
        signal_generator = SignalGenerator(market_analyzer)
        
        # Generate trading signal
        signal = signal_generator.get_signal(symbol)
        if not signal:
            return {'error': 'Failed to generate trading signal'}
        
        logging.info(f"Generated signal: {signal['action']} (strength: {signal['strength']:.2f})")
        
        # Check if signal is strong enough
        if signal['strength'] < min_signal_strength:
            log_trade_cycle(db, symbol, 'hold', f"Signal too weak: {signal['strength']:.2f} < {min_signal_strength}")
            return {
                'action': 'hold',
                'reason': f"Signal strength {signal['strength']:.2f} below minimum {min_signal_strength}",
                'signal': signal
            }
        
        # Skip if signal is hold
        if signal['action'] == 'hold':
            log_trade_cycle(db, symbol, 'hold', 'Signal indicates hold')
            return {
                'action': 'hold',
                'reason': 'Signal indicates hold',
                'signal': signal
            }
        
        # Get current market price
        ticker = trader.get_ticker(symbol)
        if not ticker:
            return {'error': 'Failed to get market price'}
        
        current_price = float(ticker['last'])
        
        # Get account balance for position sizing
        balance_info = trader.get_account_balance()
        if not balance_info:
            return {'error': 'Failed to get account balance'}
        
        available_balance = float(balance_info.get('availEq', 0))
        if available_balance <= 0:
            return {'error': 'Insufficient account balance'}
        
        # Calculate position size using risk management
        risk_percent = float(BotConfig.get_value('risk_percent', '2.0'))
        stop_loss_price = signal.get('stop_loss', current_price * 0.98)
        
        position_calc = risk_manager.calculate_position_size(
            account_balance=available_balance,
            risk_percent=risk_percent,
            entry_price=current_price,
            stop_loss_price=stop_loss_price
        )
        
        if position_calc.get('error'):
            return {'error': f"Position sizing error: {position_calc['error']}"}
        
        quantity = position_calc['position_size']
        risk_amount = position_calc['risk_amount']
        
        # Validate trade using risk management rules
        trade_params = {
            'symbol': symbol,
            'trade_type': signal['action'],
            'quantity': quantity,
            'price': current_price
        }
        
        validation = risk_manager.validate_trade(trade_params)
        if not validation['valid']:
            error_msg = '; '.join(validation['errors'])
            log_trade_cycle(db, symbol, 'rejected', f"Risk validation failed: {error_msg}")
            return {
                'action': 'rejected',
                'reason': f"Risk validation failed: {error_msg}",
                'validation_errors': validation['errors']
            }
        
        # Log any warnings
        if validation['warnings']:
            warning_msg = '; '.join(validation['warnings'])
            logging.warning(f"Trade warnings: {warning_msg}")
        
        # Create trade record
        trade = Trade(
            trade_type=TradeType.BUY if signal['action'] == 'buy' else TradeType.SELL,
            symbol=symbol,
            quantity=quantity,
            price=current_price,
            status=TradeStatus.PENDING,
            signal_strength=signal['strength'],
            risk_amount=risk_amount,
            stop_loss=signal.get('stop_loss'),
            take_profit=signal.get('take_profit'),
            notes=f"Signal: {signal['action']}, Strength: {signal['strength']:.2f}"
        )
        
        db.session.add(trade)
        db.session.commit()
        
        # Execute the trade
        if signal['action'] == 'buy':
            order_result = trader.buy(symbol, str(quantity))
        else:
            order_result = trader.sell(symbol, str(quantity))
        
        if order_result:
            # Update trade with order information
            trade.order_id = order_result.get('ordId')
            trade.status = TradeStatus.EXECUTED
            trade.notes += f" | Order ID: {order_result.get('ordId')}"
            
            # In a real implementation, you would monitor the order status
            # and update P&L once the order is filled
            if dry_run:
                # Simulate immediate fill for dry run
                simulated_pnl = simulate_trade_pnl(signal['action'], quantity, current_price)
                trade.pnl = simulated_pnl
                
            db.session.commit()
            
            log_trade_cycle(
                db, symbol, signal['action'],
                f"Trade executed: {signal['action']} {quantity} {symbol} at {current_price}"
            )
            
            logging.info(f"Trade executed successfully: {signal['action']} {quantity} {symbol}")
            
            return {
                'action': signal['action'],
                'quantity': quantity,
                'price': current_price,
                'order_id': order_result.get('ordId'),
                'risk_amount': risk_amount,
                'signal': signal,
                'trade_id': trade.id
            }
        else:
            # Order failed
            trade.status = TradeStatus.FAILED
            trade.notes += " | Order execution failed"
            db.session.commit()
            
            log_trade_cycle(db, symbol, 'failed', 'Order execution failed')
            
            return {'error': 'Failed to execute trade order'}
        
    except Exception as e:
        logging.error(f"Error in trading cycle: {str(e)}")
        log_trade_cycle(db, symbol if 'symbol' in locals() else 'UNKNOWN', 'error', f"Cycle error: {str(e)}")
        return {'error': f"Trading cycle error: {str(e)}"}

def simulate_trade_pnl(action: str, quantity: float, price: float) -> float:
    """
    Simulate P&L for dry run mode
    This is a simple simulation - in reality, P&L would be calculated after order fills
    """
    import random
    
    # Simulate some market movement (random walk)
    price_movement = random.uniform(-0.02, 0.02)  # ±2% movement
    
    if action == 'buy':
        # For buy orders, positive movement is profit
        pnl = quantity * price * price_movement
    else:
        # For sell orders, negative movement is profit
        pnl = quantity * price * (-price_movement)
    
    # Add some randomness to make it more realistic
    pnl *= random.uniform(0.8, 1.2)
    
    return round(pnl, 2)

def log_trade_cycle(db, symbol: str, action: str, message: str, details: Dict[str, Any] = None):
    """Log trading cycle events to the database"""
    try:
        log_entry = BotLog(
            level='INFO',
            message=message,
            component='trading_cycle',
            details=json.dumps(details) if details else json.dumps({'symbol': symbol, 'action': action})
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to log trade cycle: {e}")

# Legacy function for backward compatibility
def run_bot():
    """
    Legacy function that runs the bot once
    This is kept for compatibility with the original bot.py interface
    """
    try:
        from app import app
        
        with app.app_context():
            from app import db
            from trader import Trader
            from risk_manager import RiskManager
            from market_analyzer import MarketAnalyzer
            
            trader = Trader()
            risk_manager = RiskManager(db)
            market_analyzer = MarketAnalyzer()
            
            result = run_bot_cycle(trader, risk_manager, market_analyzer, db)
            
            if result.get('error'):
                print(f"Bot cycle error: {result['error']}")
            else:
                print(f"Bot cycle completed: {result.get('action', 'unknown')}")
                
            return result
            
    except Exception as e:
        print(f"Error running bot: {e}")
        return {'error': str(e)}

if __name__ == "__main__":
    # Direct execution support
    result = run_bot()
    print(f"Bot execution result: {result}")
