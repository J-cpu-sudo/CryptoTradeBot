#!/usr/bin/env python3
"""
Working Autonomous Trader - Complete 24/7 autonomous trading system
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [AUTONOMOUS] - %(message)s')
logger = logging.getLogger(__name__)

class WorkingAutonomousTrader:
    """Complete autonomous trading system with robust authentication and error handling"""
    
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        self.running = False
        self.cycle_count = 0
        self.successful_trades = 0
        self.failed_requests = 0
        
        # Trading configuration
        self.trading_pairs = ['MEME-USDT', 'NEIRO-USDT', 'SATS-USDT', 'PEPE-USDT']
        self.min_trade_amount = 0.05  # Minimum $0.05 per trade
        self.max_trade_percentage = 0.20  # Use max 20% of balance per trade
        self.cycle_interval = 300  # 5 minutes between cycles
        
        logger.info("Working Autonomous Trader initialized")
        logger.info(f"Trading pairs: {', '.join(self.trading_pairs)}")
        logger.info(f"Cycle interval: {self.cycle_interval} seconds")
    
    def get_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def create_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        message = timestamp + method + path + body
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(self, method: str, path: str, body: str = '') -> dict:
        timestamp = self.get_timestamp()
        signature = self.create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def make_api_request(self, method: str, endpoint: str, body: str = None, max_retries: int = 3):
        """Make API request with retry logic and error handling"""
        url = self.base_url + endpoint
        
        for attempt in range(max_retries):
            try:
                headers = self.get_headers(method, endpoint, body or '')
                
                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=15)
                else:
                    response = requests.post(url, headers=headers, data=body, timeout=15)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    logger.warning(f"Authentication error on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait before retry
                        continue
                else:
                    logger.warning(f"HTTP {response.status_code} on attempt {attempt + 1}")
                    
            except Exception as e:
                logger.error(f"Request failed on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
        
        self.failed_requests += 1
        return None
    
    def get_account_balance(self):
        """Get current account balance with all currencies"""
        response = self.make_api_request('GET', '/api/v5/account/balance')
        
        if response and response.get('code') == '0':
            portfolio = {}
            total_usd_value = 0.0
            
            for detail in response['data'][0]['details']:
                currency = detail['ccy']
                balance = float(detail['availBal'])
                if balance > 0:
                    portfolio[currency] = balance
                    
                    # Add to total USD value
                    if currency == 'USDT':
                        total_usd_value += balance
                    else:
                        # Get USD conversion for other currencies
                        try:
                            ticker_response = self.make_api_request('GET', f'/api/v5/market/ticker?instId={currency}-USDT')
                            if ticker_response and ticker_response.get('data'):
                                price = float(ticker_response['data'][0]['last'])
                                total_usd_value += balance * price
                        except:
                            pass
            
            return portfolio, total_usd_value
        
        return {}, 0.0
    
    def analyze_trading_opportunity(self, symbol: str):
        """Analyze market conditions for trading opportunity"""
        try:
            # Get current market data
            ticker_response = self.make_api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
            if not ticker_response or not ticker_response.get('data'):
                return None
            
            ticker = ticker_response['data'][0]
            current_price = float(ticker['last'])
            volume_24h = float(ticker['vol24h'])
            price_change_24h = float(ticker['sodUtc8'])
            
            # Get recent price history
            candles_response = self.make_api_request('GET', f'/api/v5/market/candles?instId={symbol}&bar=5m&limit=20')
            if not candles_response or not candles_response.get('data'):
                return None
            
            candles = candles_response['data']
            prices = [float(candle[4]) for candle in candles]  # Close prices
            
            # Calculate technical indicators
            recent_avg = sum(prices[:5]) / 5
            older_avg = sum(prices[10:15]) / 5
            trend_direction = "bullish" if recent_avg > older_avg else "bearish"
            trend_strength = abs(recent_avg - older_avg) / older_avg
            
            # Calculate volatility
            price_changes = [abs(prices[i] - prices[i+1]) / prices[i+1] for i in range(len(prices)-1)]
            volatility = sum(price_changes) / len(price_changes)
            
            # Calculate opportunity score
            volume_score = min(volume_24h / 1000000, 1.0)  # Normalize by 1M
            volatility_score = min(volatility * 100, 1.0)  # Scale volatility
            trend_score = min(trend_strength * 20, 1.0)  # Scale trend strength
            
            opportunity_score = (volume_score * 0.4) + (volatility_score * 0.3) + (trend_score * 0.3)
            
            return {
                'symbol': symbol,
                'price': current_price,
                'trend_direction': trend_direction,
                'trend_strength': trend_strength,
                'volatility': volatility,
                'volume_24h': volume_24h,
                'price_change_24h': price_change_24h,
                'opportunity_score': opportunity_score
            }
            
        except Exception as e:
            logger.debug(f"Analysis failed for {symbol}: {e}")
            return None
    
    def execute_autonomous_trade(self, opportunity: dict, available_usdt: float):
        """Execute autonomous trade based on opportunity analysis"""
        symbol = opportunity['symbol']
        current_price = opportunity['price']
        
        # Calculate trade amount
        trade_amount = min(
            available_usdt * self.max_trade_percentage,
            available_usdt - 0.01  # Leave small buffer
        )
        
        if trade_amount < self.min_trade_amount:
            logger.info(f"Trade amount ${trade_amount:.6f} below minimum ${self.min_trade_amount}")
            return False
        
        # Calculate quantity
        quantity = trade_amount / current_price
        
        # Get instrument specifications
        inst_response = self.make_api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if inst_response and inst_response.get('data'):
            min_size = float(inst_response['data'][0]['minSz'])
            if quantity < min_size:
                quantity = min_size
                trade_amount = quantity * current_price
        
        logger.info(f"Executing trade: {symbol}")
        logger.info(f"Quantity: {quantity:.8f}, Amount: ${trade_amount:.6f}")
        logger.info(f"Trend: {opportunity['trend_direction']}, Score: {opportunity['opportunity_score']:.4f}")
        
        # Execute market buy order
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        response = self.make_api_request('POST', '/api/v5/trade/order', order_body)
        
        if response and response.get('code') == '0':
            order_id = response['data'][0]['ordId']
            logger.info(f"Trade executed successfully - Order ID: {order_id}")
            self.successful_trades += 1
            return True
        else:
            error_msg = response.get('msg', 'Unknown error') if response else 'Request failed'
            logger.warning(f"Trade execution failed: {error_msg}")
            return False
    
    def autonomous_trading_cycle(self):
        """Execute one complete autonomous trading cycle"""
        self.cycle_count += 1
        cycle_start_time = datetime.now()
        
        logger.info(f"Cycle #{self.cycle_count} - {cycle_start_time.strftime('%H:%M:%S')}")
        
        # Get current portfolio
        portfolio, total_value = self.get_account_balance()
        usdt_balance = portfolio.get('USDT', 0.0)
        
        logger.info(f"Portfolio: ${total_value:.6f} total, ${usdt_balance:.6f} USDT")
        logger.info(f"Success rate: {self.successful_trades} trades, {self.failed_requests} failed requests")
        
        # Check if we have sufficient balance for trading
        if usdt_balance < self.min_trade_amount:
            logger.info("Insufficient USDT balance for trading")
            return
        
        # Analyze all trading pairs
        opportunities = []
        for symbol in self.trading_pairs:
            opportunity = self.analyze_trading_opportunity(symbol)
            if opportunity:
                opportunities.append(opportunity)
                logger.info(f"{symbol}: Score {opportunity['opportunity_score']:.4f}, "
                          f"Trend {opportunity['trend_direction']}, "
                          f"Change {opportunity['price_change_24h']:.2f}%")
        
        if not opportunities:
            logger.info("No trading opportunities found")
            return
        
        # Sort by opportunity score
        opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
        best_opportunity = opportunities[0]
        
        # Execute trade if opportunity score meets threshold
        score_threshold = 0.25  # Lowered threshold for more trading activity
        if best_opportunity['opportunity_score'] >= score_threshold:
            logger.info(f"Trading opportunity identified: {best_opportunity['symbol']} "
                       f"(score: {best_opportunity['opportunity_score']:.4f})")
            
            success = self.execute_autonomous_trade(best_opportunity, usdt_balance)
            if success:
                logger.info(f"Successful autonomous trade executed")
            else:
                logger.info(f"Trade execution unsuccessful")
        else:
            logger.info(f"Best opportunity score {best_opportunity['opportunity_score']:.4f} "
                       f"below threshold {score_threshold}")
    
    def start_autonomous_operation(self):
        """Start continuous autonomous trading operation"""
        self.running = True
        
        logger.info("AUTONOMOUS TRADING SYSTEM ACTIVATED")
        logger.info(f"Operating with {self.cycle_interval} second intervals")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while self.running:
                cycle_start = time.time()
                
                try:
                    self.autonomous_trading_cycle()
                except Exception as e:
                    logger.error(f"Cycle error: {e}")
                
                # Wait for next cycle
                elapsed = time.time() - cycle_start
                sleep_time = max(self.cycle_interval - elapsed, 10)  # Minimum 10 seconds
                
                logger.info(f"Next cycle in {sleep_time:.0f} seconds")
                
                for i in range(int(sleep_time)):
                    if not self.running:
                        break
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            logger.info("Shutdown signal received")
        finally:
            self.stop_autonomous_operation()
    
    def stop_autonomous_operation(self):
        """Stop autonomous trading operation"""
        self.running = False
        logger.info("Autonomous trading system stopped")
        logger.info(f"Final stats: {self.successful_trades} successful trades, "
                   f"{self.cycle_count} total cycles")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Shutdown signal received, stopping autonomous trader...")
    global trader
    if trader:
        trader.stop_autonomous_operation()
    sys.exit(0)

def main():
    """Main entry point"""
    global trader
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    trader = WorkingAutonomousTrader()
    trader.start_autonomous_operation()

if __name__ == "__main__":
    main()