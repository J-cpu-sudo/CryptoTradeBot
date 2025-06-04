from flask import Blueprint, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from models import db, BotLog, Trade, MarketData, BotConfig
from market_analyzer import MarketAnalyzer
from confluence_signals import AdvancedConfluenceAnalyzer
from backtesting_engine import BacktestingEngine, RiskAnalyzer
import pandas as pd

realtime_bp = Blueprint('realtime', __name__)

class RealtimeDashboard:
    """Real-time dashboard manager with WebSocket support"""
    
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.market_analyzer = MarketAnalyzer()
        self.confluence_analyzer = AdvancedConfluenceAnalyzer()
        self.backtest_engine = BacktestingEngine()
        self.risk_analyzer = RiskAnalyzer()
        
        # Performance tracking
        self.metrics_cache = {}
        self.last_update = datetime.utcnow()
        
        logging.info("Real-time dashboard initialized")
    
    def start_realtime_updates(self):
        """Start real-time data updates via WebSocket"""
        
        @self.socketio.on('connect')
        def handle_connect():
            logging.info(f"Client connected to real-time dashboard")
            # Send initial data
            self.emit_initial_data()
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logging.info("Client disconnected from real-time dashboard")
        
        @self.socketio.on('request_market_data')
        def handle_market_request():
            market_data = self.get_realtime_market_data()
            emit('market_update', market_data)
        
        @self.socketio.on('request_performance')
        def handle_performance_request():
            performance_data = self.get_performance_metrics()
            emit('performance_update', performance_data)
        
        @self.socketio.on('request_signals')
        def handle_signals_request():
            signals_data = self.get_signal_analysis()
            emit('signals_update', signals_data)
    
    def emit_initial_data(self):
        """Send initial dashboard data to connected clients"""
        try:
            initial_data = {
                'market_data': self.get_realtime_market_data(),
                'performance': self.get_performance_metrics(),
                'signals': self.get_signal_analysis(),
                'positions': self.get_current_positions(),
                'system_status': self.get_system_status()
            }
            
            self.socketio.emit('initial_data', initial_data)
            logging.info("Initial dashboard data sent to clients")
            
        except Exception as e:
            logging.error(f"Error sending initial data: {e}")
    
    def broadcast_market_update(self, market_data: Dict[str, Any]):
        """Broadcast market data update to all connected clients"""
        try:
            enhanced_data = {
                'price': market_data.get('price', 0),
                'volume': market_data.get('volume', 0),
                'timestamp': market_data.get('timestamp', datetime.utcnow()).isoformat(),
                'change_24h': market_data.get('change_24h', 0),
                'volatility': self._calculate_volatility(),
                'trend': self._get_trend_indicator(),
                'signal_strength': self._get_current_signal_strength()
            }
            
            self.socketio.emit('market_update', enhanced_data)
            
        except Exception as e:
            logging.error(f"Error broadcasting market update: {e}")
    
    def broadcast_trade_update(self, trade_data: Dict[str, Any]):
        """Broadcast trade execution update"""
        try:
            self.socketio.emit('trade_update', trade_data)
            
            # Update performance metrics
            performance_update = self.get_performance_metrics()
            self.socketio.emit('performance_update', performance_update)
            
        except Exception as e:
            logging.error(f"Error broadcasting trade update: {e}")
    
    def broadcast_log_update(self, log_entry: Dict[str, Any]):
        """Broadcast real-time log update"""
        try:
            self.socketio.emit('log_update', log_entry)
            
        except Exception as e:
            logging.error(f"Error broadcasting log update: {e}")
    
    def get_realtime_market_data(self) -> Dict[str, Any]:
        """Get current market data with technical indicators"""
        try:
            # Get latest market analysis
            analysis = self.market_analyzer.analyze_market("BTC-USDT")
            
            if not analysis:
                return {'error': 'No market data available'}
            
            # Get confluence analysis
            candles = self.market_analyzer._get_candles("BTC-USDT", 100)
            if candles:
                confluence = self.confluence_analyzer.analyze_confluence(candles, analysis['current_price'])
                confluence_data = {
                    'signal': confluence.signal,
                    'strength': confluence.strength,
                    'confidence': confluence.confidence,
                    'risk_reward': confluence.risk_reward_ratio
                }
            else:
                confluence_data = {'signal': 'hold', 'strength': 0, 'confidence': 0, 'risk_reward': 0}
            
            return {
                'symbol': 'BTC-USDT',
                'price': analysis['current_price'],
                'volume': analysis.get('market_conditions', {}).get('volume_24h', 0),
                'indicators': analysis.get('indicators', {}),
                'market_conditions': analysis.get('market_conditions', {}),
                'confluence': confluence_data,
                'timestamp': datetime.utcnow().isoformat(),
                'latency_ms': 0  # Will be updated by WebSocket feed
            }
            
        except Exception as e:
            logging.error(f"Error getting market data: {e}")
            return {'error': str(e)}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get real-time performance metrics"""
        try:
            # Get trades from database
            recent_trades = Trade.query.order_by(Trade.timestamp.desc()).limit(100).all()
            
            if not recent_trades:
                return {
                    'total_trades': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'best_trade': 0,
                    'worst_trade': 0,
                    'avg_trade': 0
                }
            
            # Calculate metrics
            total_trades = len(recent_trades)
            winning_trades = sum(1 for trade in recent_trades if trade.pnl > 0)
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            total_pnl = sum(trade.pnl for trade in recent_trades)
            best_trade = max(trade.pnl for trade in recent_trades)
            worst_trade = min(trade.pnl for trade in recent_trades)
            avg_trade = total_pnl / total_trades if total_trades > 0 else 0
            
            # Daily performance
            today = datetime.utcnow().date()
            today_trades = [t for t in recent_trades if t.timestamp.date() == today]
            daily_pnl = sum(trade.pnl for trade in today_trades)
            
            # Risk metrics
            balance = float(BotConfig.get_value('current_balance', '10000'))
            max_drawdown = self._calculate_current_drawdown(recent_trades, balance)
            
            return {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'best_trade': best_trade,
                'worst_trade': worst_trade,
                'avg_trade': avg_trade,
                'max_drawdown': max_drawdown,
                'current_balance': balance,
                'roi': (total_pnl / balance) * 100 if balance > 0 else 0
            }
            
        except Exception as e:
            logging.error(f"Error calculating performance metrics: {e}")
            return {'error': str(e)}
    
    def get_signal_analysis(self) -> Dict[str, Any]:
        """Get current signal analysis with confluence"""
        try:
            # Get market data for analysis
            candles = self.market_analyzer._get_candles("BTC-USDT", 100)
            market_analysis = self.market_analyzer.analyze_market("BTC-USDT")
            
            if not candles or not market_analysis:
                return {'error': 'Insufficient data for signal analysis'}
            
            current_price = market_analysis['current_price']
            
            # Get confluence analysis
            confluence = self.confluence_analyzer.analyze_confluence(candles, current_price)
            
            # Get component signals
            indicators = market_analysis.get('indicators', {})
            
            return {
                'overall_signal': confluence.signal,
                'signal_strength': confluence.strength,
                'confidence': confluence.confidence,
                'risk_reward_ratio': confluence.risk_reward_ratio,
                'entry_price': confluence.entry_price,
                'stop_loss': confluence.stop_loss,
                'take_profit': confluence.take_profit,
                'components': confluence.components,
                'indicators': {
                    'rsi': indicators.get('rsi', 0),
                    'macd': indicators.get('macd', 0),
                    'ema_12': indicators.get('ema_12', 0),
                    'ema_26': indicators.get('ema_26', 0),
                    'atr': indicators.get('atr', 0)
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error in signal analysis: {e}")
            return {'error': str(e)}
    
    def get_current_positions(self) -> List[Dict[str, Any]]:
        """Get current open positions"""
        try:
            # Get open trades from database
            open_trades = Trade.query.filter_by(status='executed').all()
            
            positions = []
            for trade in open_trades:
                # Get current price for P&L calculation
                market_data = self.market_analyzer.analyze_market(trade.symbol)
                current_price = market_data['current_price'] if market_data else trade.price
                
                # Calculate unrealized P&L
                if trade.trade_type.value == 'buy':
                    unrealized_pnl = (current_price - trade.price) * trade.quantity
                else:
                    unrealized_pnl = (trade.price - current_price) * trade.quantity
                
                positions.append({
                    'id': trade.id,
                    'symbol': trade.symbol,
                    'side': trade.trade_type.value,
                    'quantity': trade.quantity,
                    'entry_price': trade.price,
                    'current_price': current_price,
                    'unrealized_pnl': unrealized_pnl,
                    'stop_loss': trade.stop_loss,
                    'take_profit': trade.take_profit,
                    'timestamp': trade.timestamp.isoformat()
                })
            
            return positions
            
        except Exception as e:
            logging.error(f"Error getting positions: {e}")
            return []
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system health and status"""
        try:
            # Get recent logs
            recent_logs = BotLog.query.order_by(BotLog.timestamp.desc()).limit(10).all()
            
            # Count error logs in last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            error_count = BotLog.query.filter(
                BotLog.timestamp >= one_hour_ago,
                BotLog.level == 'ERROR'
            ).count()
            
            # Check bot configuration
            trading_enabled = BotConfig.get_value('trading_enabled', 'false').lower() == 'true'
            dry_run = BotConfig.get_value('dry_run', 'true').lower() == 'true'
            
            # System status
            if error_count > 5:
                status = 'error'
                health = 'unhealthy'
            elif error_count > 2:
                status = 'warning'
                health = 'degraded'
            else:
                status = 'running'
                health = 'healthy'
            
            return {
                'status': status,
                'health': health,
                'trading_enabled': trading_enabled,
                'dry_run_mode': dry_run,
                'error_count_1h': error_count,
                'uptime': self._get_uptime(),
                'last_trade': self._get_last_trade_time(),
                'api_status': 'connected',  # Would check actual API status
                'websocket_status': 'connected',
                'database_status': 'connected'
            }
            
        except Exception as e:
            logging.error(f"Error getting system status: {e}")
            return {'status': 'error', 'health': 'unhealthy', 'error': str(e)}
    
    def run_backtest_analysis(self, days: int = 30) -> Dict[str, Any]:
        """Run backtest analysis for recent period"""
        try:
            # Get historical data (simulated for now)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Create sample historical data
            historical_data = self._generate_sample_historical_data(start_date, end_date)
            
            # Define strategy function
            def confluence_strategy(data):
                if len(data) < 50:
                    return None
                
                # Use confluence analyzer
                candles = [[row['open'], row['high'], row['low'], row['close'], row['volume']] 
                          for _, row in data.tail(100).iterrows()]
                
                confluence = self.confluence_analyzer.analyze_confluence(
                    candles, data.iloc[-1]['close']
                )
                
                if confluence.signal != 'hold':
                    return {
                        'action': confluence.signal,
                        'symbol': 'BTC-USDT',
                        'quantity': 0.01,
                        'stop_loss': confluence.stop_loss,
                        'take_profit': confluence.take_profit
                    }
                return None
            
            # Run backtest
            metrics = self.backtest_engine.run_backtest(
                historical_data, confluence_strategy, start_date, end_date
            )
            
            return {
                'period_days': days,
                'total_trades': metrics.total_trades,
                'win_rate': metrics.win_rate,
                'total_return': metrics.total_return,
                'max_drawdown': metrics.max_drawdown,
                'sharpe_ratio': metrics.sharpe_ratio,
                'profit_factor': metrics.profit_factor,
                'avg_win': metrics.avg_win,
                'avg_loss': metrics.avg_loss
            }
            
        except Exception as e:
            logging.error(f"Error running backtest: {e}")
            return {'error': str(e)}
    
    def _calculate_volatility(self) -> float:
        """Calculate current market volatility"""
        try:
            recent_data = MarketData.query.order_by(MarketData.timestamp.desc()).limit(24).all()
            if len(recent_data) < 2:
                return 0
            
            prices = [data.price for data in recent_data]
            returns = [(prices[i] - prices[i+1]) / prices[i+1] for i in range(len(prices)-1)]
            
            import numpy as np
            return float(np.std(returns)) if returns else 0
            
        except Exception as e:
            logging.error(f"Error calculating volatility: {e}")
            return 0
    
    def _get_trend_indicator(self) -> str:
        """Get simple trend indicator"""
        try:
            recent_data = MarketData.query.order_by(MarketData.timestamp.desc()).limit(10).all()
            if len(recent_data) < 2:
                return 'neutral'
            
            current_price = recent_data[0].price
            avg_price = sum(data.price for data in recent_data) / len(recent_data)
            
            if current_price > avg_price * 1.01:
                return 'bullish'
            elif current_price < avg_price * 0.99:
                return 'bearish'
            else:
                return 'neutral'
                
        except Exception as e:
            logging.error(f"Error getting trend: {e}")
            return 'neutral'
    
    def _get_current_signal_strength(self) -> float:
        """Get current signal strength"""
        try:
            signals = self.get_signal_analysis()
            return signals.get('signal_strength', 0)
        except:
            return 0
    
    def _calculate_current_drawdown(self, trades: List, balance: float) -> float:
        """Calculate current drawdown from trades"""
        try:
            if not trades:
                return 0
            
            # Calculate running P&L
            running_pnl = 0
            peak_balance = balance
            max_drawdown = 0
            
            for trade in reversed(trades):  # Oldest first
                running_pnl += trade.pnl
                current_balance = balance + running_pnl
                
                if current_balance > peak_balance:
                    peak_balance = current_balance
                
                drawdown = (peak_balance - current_balance) / peak_balance
                max_drawdown = max(max_drawdown, drawdown)
            
            return max_drawdown
            
        except Exception as e:
            logging.error(f"Error calculating drawdown: {e}")
            return 0
    
    def _get_uptime(self) -> str:
        """Get system uptime"""
        uptime_seconds = (datetime.utcnow() - self.last_update).total_seconds()
        
        if uptime_seconds < 60:
            return f"{int(uptime_seconds)}s"
        elif uptime_seconds < 3600:
            return f"{int(uptime_seconds/60)}m"
        else:
            return f"{int(uptime_seconds/3600)}h"
    
    def _get_last_trade_time(self) -> str:
        """Get time of last trade"""
        try:
            last_trade = Trade.query.order_by(Trade.timestamp.desc()).first()
            if last_trade:
                time_diff = datetime.utcnow() - last_trade.timestamp
                if time_diff.total_seconds() < 60:
                    return f"{int(time_diff.total_seconds())}s ago"
                elif time_diff.total_seconds() < 3600:
                    return f"{int(time_diff.total_seconds()/60)}m ago"
                else:
                    return f"{int(time_diff.total_seconds()/3600)}h ago"
            return "No trades yet"
        except:
            return "Unknown"
    
    def _generate_sample_historical_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Generate sample historical data for backtesting"""
        dates = pd.date_range(start=start_date, end=end_date, freq='1H')
        
        # Generate realistic price data
        import numpy as np
        np.random.seed(42)
        
        base_price = 45000  # Starting BTC price
        returns = np.random.normal(0, 0.02, len(dates))  # 2% hourly volatility
        
        prices = [base_price]
        for r in returns[1:]:
            prices.append(prices[-1] * (1 + r))
        
        data = pd.DataFrame({
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
            'close': prices,
            'volume': np.random.normal(1000, 200, len(dates))
        }, index=dates)
        
        return data


# Flask routes for dashboard
@realtime_bp.route('/dashboard')
def dashboard():
    """Main real-time dashboard page"""
    return render_template('realtime_dashboard.html')

@realtime_bp.route('/api/backtest', methods=['POST'])
def run_backtest():
    """API endpoint to run backtest"""
    try:
        data = request.get_json()
        days = data.get('days', 30)
        
        dashboard = current_app.dashboard_manager
        results = dashboard.run_backtest_analysis(days)
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500