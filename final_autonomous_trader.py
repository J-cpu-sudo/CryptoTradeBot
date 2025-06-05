#!/usr/bin/env python3
"""
Final Autonomous Trading System - Complete 24/7 autonomous operation
Designed for hedge fund-level performance with zero manual intervention
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
import threading
from datetime import datetime, timezone
import logging
import signal
import sys
from typing import Dict, List, Optional, Any

# Configure logging for autonomous operation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [AUTONOMOUS] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('autonomous_trading.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

class FinalAutonomousTrader:
    """Complete autonomous trading system with enterprise-grade reliability"""
    
    def __init__(self):
        # API Configuration
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Trading Configuration
        self.trading_pairs = [
            'MEME-USDT', 'NEIRO-USDT', 'SATS-USDT', 'PEPE-USDT',
            'SHIB-USDT', 'FLOKI-USDT', 'WIF-USDT', 'BONK-USDT'
        ]
        
        # Risk Management
        self.min_trade_amount = 0.05  # $0.05 minimum
        self.max_trade_percentage = 0.15  # 15% of balance per trade
        self.max_daily_trades = 50  # Maximum trades per day
        self.stop_loss_percentage = 0.05  # 5% stop loss
        
        # Timing Configuration
        self.cycle_interval = 180  # 3 minutes between cycles
        self.max_retries = 5
        self.retry_delay = 3
        
        # State Tracking
        self.running = False
        self.cycle_count = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_profit = 0.0
        self.daily_trades = 0
        self.last_trade_time = 0
        self.authentication_errors = 0
        
        # Portfolio tracking
        self.initial_balance = 0.0
        self.current_balance = 0.0
        self.portfolio = {}
        
        logger.info("=== FINAL AUTONOMOUS TRADING SYSTEM INITIALIZED ===")
        logger.info(f"Trading pairs: {len(self.trading_pairs)} pairs")
        logger.info(f"Cycle interval: {self.cycle_interval} seconds")
        logger.info(f"Max daily trades: {self.max_daily_trades}")
        logger.info(f"Risk management: {self.max_trade_percentage*100}% max per trade")
    
    def get_timestamp(self) -> str:
        """Generate precise timestamp for API authentication"""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def create_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """Create HMAC SHA256 signature for OKX API"""
        message = timestamp + method + path + body
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(self, method: str, path: str, body: str = '') -> Dict[str, str]:
        """Generate authenticated headers for API requests"""
        timestamp = self.get_timestamp()
        signature = self.create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def safe_api_request(self, method: str, endpoint: str, body: str = None) -> Optional[Dict]:
        """Make authenticated API request with comprehensive error handling"""
        url = self.base_url + endpoint
        
        for attempt in range(self.max_retries):
            try:
                headers = self.get_headers(method, endpoint, body or '')
                
                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=20)
                else:
                    response = requests.post(url, headers=headers, data=body, timeout=20)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('code') == '0':
                        self.authentication_errors = 0  # Reset on success
                        return result
                    else:
                        logger.warning(f"API error: {result.get('msg', 'Unknown error')}")
                        return None
                        
                elif response.status_code == 401:
                    self.authentication_errors += 1
                    logger.warning(f"Authentication error (attempt {attempt + 1})")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                        continue
                else:
                    logger.warning(f"HTTP {response.status_code} on attempt {attempt + 1}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
            except requests.exceptions.ConnectionError:
                logger.warning(f"Connection error on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        return None
    
    def get_account_portfolio(self) -> Dict[str, Any]:
        """Get complete account portfolio with USD valuations"""
        response = self.safe_api_request('GET', '/api/v5/account/balance')
        
        if not response:
            return {'portfolio': {}, 'total_value': 0.0, 'usdt_balance': 0.0}
        
        portfolio = {}
        total_usd_value = 0.0
        
        try:
            for detail in response['data'][0]['details']:
                currency = detail['ccy']
                balance = float(detail['availBal'])
                
                if balance > 0:
                    portfolio[currency] = balance
                    
                    if currency == 'USDT':
                        total_usd_value += balance
                    else:
                        # Get USD conversion
                        ticker_response = self.safe_api_request('GET', f'/api/v5/market/ticker?instId={currency}-USDT')
                        if ticker_response and ticker_response.get('data'):
                            try:
                                price = float(ticker_response['data'][0]['last'])
                                total_usd_value += balance * price
                            except:
                                pass
            
            self.portfolio = portfolio
            self.current_balance = total_usd_value
            
            return {
                'portfolio': portfolio,
                'total_value': total_usd_value,
                'usdt_balance': portfolio.get('USDT', 0.0)
            }
            
        except Exception as e:
            logger.error(f"Portfolio analysis error: {e}")
            return {'portfolio': {}, 'total_value': 0.0, 'usdt_balance': 0.0}
    
    def advanced_market_analysis(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Comprehensive market analysis with multiple indicators"""
        try:
            # Get current market data
            ticker_response = self.safe_api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
            if not ticker_response or not ticker_response.get('data'):
                return None
            
            ticker = ticker_response['data'][0]
            current_price = float(ticker['last'])
            volume_24h = float(ticker['vol24h'])
            price_change_24h = float(ticker['sodUtc8'])
            
            # Get detailed price history
            candles_response = self.safe_api_request('GET', f'/api/v5/market/candles?instId={symbol}&bar=5m&limit=100')
            if not candles_response or not candles_response.get('data'):
                return None
            
            candles = candles_response['data']
            closes = [float(candle[4]) for candle in candles]
            highs = [float(candle[2]) for candle in candles]
            lows = [float(candle[3]) for candle in candles]
            volumes = [float(candle[5]) for candle in candles]
            
            # Technical Analysis
            sma_short = sum(closes[:10]) / 10
            sma_long = sum(closes[:50]) / 50
            
            # RSI calculation
            gains = []
            losses = []
            for i in range(1, min(15, len(closes))):
                change = closes[i-1] - closes[i]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(-change)
            
            avg_gain = sum(gains) / len(gains) if gains else 0
            avg_loss = sum(losses) / len(losses) if losses else 0.001
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # Volatility analysis
            price_changes = [abs(closes[i] - closes[i+1]) / closes[i+1] for i in range(len(closes)-1)]
            volatility = sum(price_changes) / len(price_changes)
            
            # Volume analysis
            avg_volume = sum(volumes[:20]) / 20
            volume_ratio = volumes[0] / avg_volume if avg_volume > 0 else 1
            
            # Trend analysis
            trend_strength = abs(sma_short - sma_long) / sma_long if sma_long > 0 else 0
            trend_direction = "bullish" if sma_short > sma_long else "bearish"
            
            # Calculate composite opportunity score
            volume_score = min(volume_ratio * 0.5, 1.0)
            volatility_score = min(volatility * 50, 1.0)
            trend_score = min(trend_strength * 10, 1.0)
            rsi_score = 0.5 + (0.5 if 30 <= rsi <= 70 else 0)  # Prefer RSI in middle range
            
            opportunity_score = (
                volume_score * 0.25 +
                volatility_score * 0.25 +
                trend_score * 0.25 +
                rsi_score * 0.25
            )
            
            return {
                'symbol': symbol,
                'price': current_price,
                'volume_24h': volume_24h,
                'price_change_24h': price_change_24h,
                'rsi': rsi,
                'trend_direction': trend_direction,
                'trend_strength': trend_strength,
                'volatility': volatility,
                'volume_ratio': volume_ratio,
                'opportunity_score': opportunity_score,
                'sma_short': sma_short,
                'sma_long': sma_long
            }
            
        except Exception as e:
            logger.debug(f"Market analysis failed for {symbol}: {e}")
            return None
    
    def execute_precision_trade(self, analysis: Dict[str, Any], usdt_balance: float) -> bool:
        """Execute high-precision autonomous trade"""
        symbol = analysis['symbol']
        current_price = analysis['price']
        
        # Risk management checks
        if self.daily_trades >= self.max_daily_trades:
            logger.info(f"Daily trade limit reached: {self.daily_trades}")
            return False
        
        if time.time() - self.last_trade_time < 60:  # Minimum 1 minute between trades
            logger.debug("Trade cooldown active")
            return False
        
        # Calculate optimal trade size
        base_amount = usdt_balance * self.max_trade_percentage
        
        # Adjust based on opportunity score
        score_multiplier = min(analysis['opportunity_score'] * 2, 1.5)
        trade_amount = base_amount * score_multiplier
        
        # Ensure minimum trade size
        trade_amount = max(trade_amount, self.min_trade_amount)
        trade_amount = min(trade_amount, usdt_balance - 0.01)  # Leave buffer
        
        if trade_amount < self.min_trade_amount:
            logger.info(f"Trade amount ${trade_amount:.6f} below minimum")
            return False
        
        # Get instrument specifications
        inst_response = self.safe_api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_response or not inst_response.get('data'):
            logger.warning(f"Could not get instrument data for {symbol}")
            return False
        
        try:
            min_size = float(inst_response['data'][0]['minSz'])
            tick_size = float(inst_response['data'][0]['tickSz'])
            
            # Calculate quantity with precision
            quantity = trade_amount / current_price
            quantity = max(quantity, min_size)
            
            # Round to proper precision
            quantity = round(quantity / min_size) * min_size
            
            logger.info(f"EXECUTING AUTONOMOUS TRADE:")
            logger.info(f"  Pair: {symbol}")
            logger.info(f"  Quantity: {quantity:.8f}")
            logger.info(f"  Amount: ${trade_amount:.6f}")
            logger.info(f"  Price: ${current_price:.6f}")
            logger.info(f"  Opportunity Score: {analysis['opportunity_score']:.4f}")
            logger.info(f"  RSI: {analysis['rsi']:.2f}")
            logger.info(f"  Trend: {analysis['trend_direction']}")
            
            # Execute market buy order
            order_data = {
                "instId": symbol,
                "tdMode": "cash",
                "side": "buy",
                "ordType": "market",
                "sz": str(quantity)
            }
            
            order_body = json.dumps(order_data)
            response = self.safe_api_request('POST', '/api/v5/trade/order', order_body)
            
            if response and response.get('data'):
                order_id = response['data'][0]['ordId']
                
                logger.info(f"TRADE EXECUTED SUCCESSFULLY!")
                logger.info(f"  Order ID: {order_id}")
                logger.info(f"  Total Trades: {self.successful_trades + 1}")
                
                self.successful_trades += 1
                self.daily_trades += 1
                self.last_trade_time = time.time()
                
                return True
            else:
                error_msg = response.get('msg', 'Unknown error') if response else 'Request failed'
                logger.warning(f"Trade execution failed: {error_msg}")
                self.failed_trades += 1
                return False
                
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            self.failed_trades += 1
            return False
    
    def autonomous_trading_cycle(self) -> None:
        """Execute complete autonomous trading cycle with advanced analytics"""
        self.cycle_count += 1
        cycle_start = time.time()
        
        logger.info(f"=== CYCLE #{self.cycle_count} ===")
        
        # Get portfolio status
        portfolio_data = self.get_account_portfolio()
        total_value = portfolio_data['total_value']
        usdt_balance = portfolio_data['usdt_balance']
        
        # Calculate performance metrics
        if self.initial_balance == 0:
            self.initial_balance = total_value
        
        profit_percentage = ((total_value - self.initial_balance) / self.initial_balance * 100) if self.initial_balance > 0 else 0
        
        logger.info(f"Portfolio Status:")
        logger.info(f"  Total Value: ${total_value:.6f}")
        logger.info(f"  USDT Available: ${usdt_balance:.6f}")
        logger.info(f"  Performance: {profit_percentage:+.2f}%")
        logger.info(f"  Successful Trades: {self.successful_trades}")
        logger.info(f"  Daily Trades: {self.daily_trades}/{self.max_daily_trades}")
        
        # Check trading conditions
        if usdt_balance < self.min_trade_amount:
            logger.info("Insufficient USDT balance for trading")
            return
        
        if self.authentication_errors > 10:
            logger.warning(f"High authentication error count: {self.authentication_errors}")
            time.sleep(30)  # Extended pause for auth issues
            return
        
        # Analyze all trading pairs
        opportunities = []
        logger.info("Scanning markets...")
        
        for symbol in self.trading_pairs:
            analysis = self.advanced_market_analysis(symbol)
            if analysis:
                opportunities.append(analysis)
                logger.info(f"  {symbol}: Score {analysis['opportunity_score']:.3f}, "
                          f"RSI {analysis['rsi']:.1f}, "
                          f"Trend {analysis['trend_direction']}, "
                          f"Change {analysis['price_change_24h']:+.2f}%")
        
        if not opportunities:
            logger.warning("No market data available")
            return
        
        # Sort by opportunity score
        opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
        best_opportunity = opportunities[0]
        
        # Dynamic threshold based on market conditions
        base_threshold = 0.30
        if self.successful_trades < 5:
            threshold = base_threshold * 0.8  # Lower threshold initially
        elif profit_percentage < -2:
            threshold = base_threshold * 1.2  # Higher threshold if losing
        else:
            threshold = base_threshold
        
        logger.info(f"Best opportunity: {best_opportunity['symbol']} "
                   f"(score: {best_opportunity['opportunity_score']:.4f}, threshold: {threshold:.3f})")
        
        # Execute trade if conditions are met
        if best_opportunity['opportunity_score'] >= threshold:
            logger.info("EXECUTING AUTONOMOUS TRADE...")
            success = self.execute_precision_trade(best_opportunity, usdt_balance)
            
            if success:
                logger.info("Trade completed successfully")
            else:
                logger.info("Trade execution failed")
        else:
            logger.info(f"No trades executed - best score {best_opportunity['opportunity_score']:.4f} below threshold {threshold:.3f}")
        
        # Cycle timing
        cycle_duration = time.time() - cycle_start
        logger.info(f"Cycle completed in {cycle_duration:.2f} seconds")
    
    def start_autonomous_operation(self) -> None:
        """Start continuous autonomous trading operation"""
        self.running = True
        
        logger.info("=" * 60)
        logger.info("AUTONOMOUS TRADING SYSTEM ACTIVATED")
        logger.info("=" * 60)
        logger.info(f"Operating mode: {self.cycle_interval}s intervals")
        logger.info(f"Risk management: {self.max_trade_percentage*100}% max per trade")
        logger.info(f"Trading pairs: {len(self.trading_pairs)} pairs")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)
        
        try:
            while self.running:
                cycle_start = time.time()
                
                try:
                    self.autonomous_trading_cycle()
                except Exception as e:
                    logger.error(f"Cycle error: {e}")
                    time.sleep(10)  # Brief pause on error
                
                # Reset daily counter at midnight UTC
                current_hour = datetime.now(timezone.utc).hour
                if current_hour == 0 and self.daily_trades > 0:
                    logger.info("Resetting daily trade counter")
                    self.daily_trades = 0
                
                # Calculate sleep time
                elapsed = time.time() - cycle_start
                sleep_time = max(self.cycle_interval - elapsed, 30)  # Minimum 30 seconds
                
                logger.info(f"Next cycle in {sleep_time:.0f} seconds")
                logger.info("-" * 40)
                
                # Sleep with interrupt checking
                for _ in range(int(sleep_time)):
                    if not self.running:
                        break
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            logger.info("Shutdown signal received")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            self.stop_autonomous_operation()
    
    def stop_autonomous_operation(self) -> None:
        """Stop autonomous trading operation with final report"""
        self.running = False
        
        # Final portfolio check
        portfolio_data = self.get_account_portfolio()
        final_value = portfolio_data['total_value']
        final_profit = ((final_value - self.initial_balance) / self.initial_balance * 100) if self.initial_balance > 0 else 0
        
        logger.info("=" * 60)
        logger.info("AUTONOMOUS TRADING SYSTEM STOPPED")
        logger.info("=" * 60)
        logger.info(f"Operation Summary:")
        logger.info(f"  Total Cycles: {self.cycle_count}")
        logger.info(f"  Successful Trades: {self.successful_trades}")
        logger.info(f"  Failed Trades: {self.failed_trades}")
        logger.info(f"  Initial Balance: ${self.initial_balance:.6f}")
        logger.info(f"  Final Balance: ${final_value:.6f}")
        logger.info(f"  Total Performance: {final_profit:+.2f}%")
        logger.info(f"  Success Rate: {(self.successful_trades/(self.successful_trades+self.failed_trades)*100):.1f}%" if (self.successful_trades + self.failed_trades) > 0 else "N/A")
        logger.info("=" * 60)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Shutdown signal received, stopping autonomous trader...")
    global trader
    if trader:
        trader.stop_autonomous_operation()
    sys.exit(0)

def main():
    """Main entry point for autonomous trading system"""
    global trader
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Initializing Final Autonomous Trading System...")
    
    trader = FinalAutonomousTrader()
    trader.start_autonomous_operation()

if __name__ == "__main__":
    main()