#!/usr/bin/env python3
"""
Start Autonomous Trading - Activate the 24/7 autonomous trading system
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutonomousTradingSystem:
    """Complete autonomous trading system with 24/7 operation"""
    
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        self.running = False
        self.cycle_count = 0
        self.successful_trades = 0
        self.total_profit = 0.0
        
        # Trading pairs prioritized by liquidity and minimum requirements
        self.trading_pairs = [
            'MEME-USDT',
            'NEIRO-USDT', 
            'SATS-USDT',
            'PEPE-USDT',
            'SHIB-USDT',
            'FLOKI-USDT'
        ]
        
        logger.info("Autonomous Trading System initialized for 24/7 operation")
    
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
    
    def api_request(self, method: str, endpoint: str, body: str = None):
        url = self.base_url + endpoint
        headers = self.get_headers(method, endpoint, body or '')
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=15)
            
            return response
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return None
    
    def get_portfolio_balance(self):
        """Get comprehensive portfolio balance including positions"""
        response = self.api_request('GET', '/api/v5/account/balance')
        
        if response and response.status_code == 200:
            data = response.json()
            if data.get('code') == '0':
                portfolio = {}
                total_usd_value = 0.0
                
                for detail in data['data'][0]['details']:
                    currency = detail['ccy']
                    balance = float(detail['availBal'])
                    if balance > 0:
                        portfolio[currency] = balance
                        
                        # Convert to USD value for total calculation
                        if currency == 'USDT':
                            total_usd_value += balance
                        else:
                            # Get USD value for other currencies
                            try:
                                ticker_symbol = f"{currency}-USDT"
                                ticker_response = self.api_request('GET', f'/api/v5/market/ticker?instId={ticker_symbol}')
                                if ticker_response and ticker_response.status_code == 200:
                                    ticker_data = ticker_response.json()
                                    if ticker_data.get('data'):
                                        price = float(ticker_data['data'][0]['last'])
                                        total_usd_value += balance * price
                            except:
                                pass
                
                return portfolio, total_usd_value
        
        return {}, 0.0
    
    def analyze_market_opportunity(self, symbol: str):
        """Analyze market for trading opportunities"""
        try:
            # Get market data
            ticker_response = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
            if not ticker_response or ticker_response.status_code != 200:
                return None
            
            ticker_data = ticker_response.json()
            if not ticker_data.get('data'):
                return None
            
            ticker = ticker_data['data'][0]
            current_price = float(ticker['last'])
            volume_24h = float(ticker['vol24h'])
            price_change_24h = float(ticker['sodUtc8'])
            
            # Get historical data for trend analysis
            candles_response = self.api_request('GET', f'/api/v5/market/candles?instId={symbol}&bar=5m&limit=20')
            if candles_response and candles_response.status_code == 200:
                candles_data = candles_response.json()
                if candles_data.get('data'):
                    candles = candles_data['data']
                    
                    # Calculate simple trend
                    prices = [float(candle[4]) for candle in candles]  # Close prices
                    recent_avg = sum(prices[:5]) / 5  # Last 5 periods
                    older_avg = sum(prices[10:15]) / 5  # Earlier 5 periods
                    
                    trend_direction = "up" if recent_avg > older_avg else "down"
                    trend_strength = abs(recent_avg - older_avg) / older_avg
                    
                    return {
                        'symbol': symbol,
                        'price': current_price,
                        'volume_24h': volume_24h,
                        'price_change_24h': price_change_24h,
                        'trend_direction': trend_direction,
                        'trend_strength': trend_strength,
                        'volatility': abs(price_change_24h),
                        'score': self.calculate_opportunity_score(volume_24h, price_change_24h, trend_strength)
                    }
        except Exception as e:
            logger.debug(f"Analysis failed for {symbol}: {e}")
            return None
    
    def calculate_opportunity_score(self, volume_24h: float, price_change_24h: float, trend_strength: float) -> float:
        """Calculate trading opportunity score"""
        volume_score = min(volume_24h / 1000000, 1.0)  # Normalize volume
        volatility_score = min(abs(price_change_24h) / 10, 1.0)  # Normalize volatility
        trend_score = min(trend_strength * 10, 1.0)  # Normalize trend strength
        
        # Weighted composite score
        total_score = (volume_score * 0.4) + (volatility_score * 0.3) + (trend_score * 0.3)
        return total_score
    
    def execute_autonomous_trade(self, opportunity: dict, available_balance: float):
        """Execute autonomous trade based on opportunity analysis"""
        symbol = opportunity['symbol']
        price = opportunity['price']
        trend_direction = opportunity['trend_direction']
        
        # Determine trade size (use 10-20% of available USDT balance)
        trade_amount = min(available_balance * 0.15, 50.0)  # Max $50 per trade
        
        if trade_amount < 1.0:  # Minimum trade size
            logger.info(f"Trade amount too small: ${trade_amount:.4f}")
            return False
        
        # Calculate quantity
        quantity = trade_amount / price
        
        # Get minimum size requirements
        inst_response = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if inst_response and inst_response.status_code == 200:
            inst_data = inst_response.json()
            if inst_data.get('data'):
                min_size = float(inst_data['data'][0]['minSz'])
                if quantity < min_size:
                    quantity = min_size
        
        logger.info(f"Executing autonomous trade: {symbol}")
        logger.info(f"Direction: {trend_direction}, Amount: ${trade_amount:.4f}, Quantity: {quantity:.8f}")
        
        # Execute buy order
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        response = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if response and response.status_code == 200:
            result = response.json()
            if result.get('code') == '0':
                order_id = result['data'][0]['ordId']
                logger.info(f"✓ Trade executed successfully: {order_id}")
                self.successful_trades += 1
                return True
            else:
                logger.warning(f"Trade failed: {result.get('msg')}")
        
        return False
    
    def autonomous_trading_cycle(self):
        """Execute one complete autonomous trading cycle"""
        self.cycle_count += 1
        logger.info(f"Autonomous Trading Cycle #{self.cycle_count}")
        
        # Get current portfolio
        portfolio, total_value = self.get_portfolio_balance()
        usdt_balance = portfolio.get('USDT', 0.0)
        
        logger.info(f"Portfolio Value: ${total_value:.4f}, USDT: ${usdt_balance:.4f}")
        
        # Only trade if we have sufficient USDT balance
        if usdt_balance < 1.0:
            logger.info("Insufficient USDT balance for trading")
            return
        
        # Analyze all trading pairs
        opportunities = []
        for symbol in self.trading_pairs:
            opportunity = self.analyze_market_opportunity(symbol)
            if opportunity:
                opportunities.append(opportunity)
        
        if not opportunities:
            logger.info("No trading opportunities found")
            return
        
        # Sort by opportunity score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        best_opportunity = opportunities[0]
        
        logger.info(f"Best opportunity: {best_opportunity['symbol']} (score: {best_opportunity['score']:.4f})")
        
        # Execute trade if score is above threshold
        if best_opportunity['score'] > 0.3:
            success = self.execute_autonomous_trade(best_opportunity, usdt_balance)
            if success:
                logger.info(f"Successful trades: {self.successful_trades}")
        else:
            logger.info("No opportunities meet trading threshold")
    
    def start_autonomous_operation(self):
        """Start continuous autonomous trading operation"""
        self.running = True
        logger.info("🚀 AUTONOMOUS TRADING SYSTEM ACTIVATED")
        logger.info("Operating 24/7 with 5-minute intervals")
        
        while self.running:
            try:
                self.autonomous_trading_cycle()
                
                # Wait 5 minutes between cycles
                for i in range(300):  # 5 minutes = 300 seconds
                    if not self.running:
                        break
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                time.sleep(60)  # Wait 1 minute on error
        
        logger.info("Autonomous trading system stopped")
    
    def stop_autonomous_operation(self):
        """Stop autonomous trading"""
        self.running = False
        logger.info("Stopping autonomous trading system...")

def main():
    """Start autonomous trading system"""
    system = AutonomousTradingSystem()
    
    try:
        # Start autonomous operation
        system.start_autonomous_operation()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
        system.stop_autonomous_operation()

if __name__ == "__main__":
    main()