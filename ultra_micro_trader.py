#!/usr/bin/env python3
"""
Ultra Micro Trading System - Executes trades with minimal balance constraints
Designed for maximum capital efficiency with micro-position management
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [MICRO] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class UltraMicroTrader:
    """Ultra-precise micro trading system for minimal balance execution"""
    
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Ultra-micro trading parameters
        self.min_usdt_amount = 0.055  # Slightly above current balance
        self.trade_percentage = 0.95  # Use 95% of available balance
        self.buffer_amount = 0.005   # Leave small buffer for fees
        
        logger.info("Ultra Micro Trading System initialized")
        logger.info(f"Minimum trade amount: ${self.min_usdt_amount}")
        logger.info(f"Trade percentage: {self.trade_percentage*100}%")
    
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
    
    def safe_request(self, method: str, endpoint: str, body: str = None, max_retries: int = 3):
        """Make API request with retry logic"""
        url = self.base_url + endpoint
        
        for attempt in range(max_retries):
            try:
                headers = self.get_headers(method, endpoint, body or '')
                
                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=15)
                else:
                    response = requests.post(url, headers=headers, data=body, timeout=15)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('code') == '0':
                        return result
                    else:
                        logger.warning(f"API error: {result.get('msg', 'Unknown')}")
                        return None
                elif response.status_code == 401:
                    logger.warning(f"Auth error on attempt {attempt + 1}")
                    time.sleep(2)
                    continue
                else:
                    logger.warning(f"HTTP {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        return None
    
    def get_precise_balance(self) -> float:
        """Get exact USDT balance with precision"""
        response = self.safe_request('GET', '/api/v5/account/balance')
        
        if response and response.get('data'):
            for detail in response['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    balance = float(detail['availBal'])
                    logger.info(f"Exact USDT balance: ${balance:.8f}")
                    return balance
        
        logger.warning("Could not retrieve balance")
        return 0.0
    
    def get_optimal_micro_pair(self) -> dict:
        """Find optimal trading pair for micro amounts"""
        pairs = ['MEME-USDT', 'NEIRO-USDT', 'SATS-USDT', 'PEPE-USDT', 'SHIB-USDT']
        best_opportunity = None
        best_score = 0
        
        logger.info("Analyzing micro trading opportunities...")
        
        for symbol in pairs:
            try:
                # Get current price
                ticker_response = self.safe_request('GET', f'/api/v5/market/ticker?instId={symbol}')
                if not ticker_response or not ticker_response.get('data'):
                    continue
                
                ticker = ticker_response['data'][0]
                price = float(ticker['last'])
                volume_24h = float(ticker['vol24h'])
                change_24h = float(ticker['sodUtc8'])
                
                # Get instrument info for minimum sizes
                inst_response = self.safe_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
                if not inst_response or not inst_response.get('data'):
                    continue
                
                min_size = float(inst_response['data'][0]['minSz'])
                tick_size = float(inst_response['data'][0]['tickSz'])
                
                # Calculate if we can trade with current balance
                min_usdt_required = min_size * price
                
                # Score based on tradability and market conditions
                volume_score = min(volume_24h / 1000000, 1.0)
                price_score = 1.0 if price > 0.00001 else 0.5  # Prefer higher priced tokens
                change_score = 0.5 + (abs(change_24h) / 100)  # Prefer some volatility
                tradability_score = 1.0 if min_usdt_required < 0.055 else 0.1
                
                total_score = (volume_score * 0.3 + price_score * 0.2 + 
                             change_score * 0.2 + tradability_score * 0.3)
                
                logger.info(f"{symbol}: Price ${price:.6f}, Min ${min_usdt_required:.6f}, "
                          f"Score {total_score:.4f}, Change {change_24h:+.2f}%")
                
                if total_score > best_score and min_usdt_required < 0.055:
                    best_score = total_score
                    best_opportunity = {
                        'symbol': symbol,
                        'price': price,
                        'min_size': min_size,
                        'min_usdt': min_usdt_required,
                        'volume_24h': volume_24h,
                        'change_24h': change_24h,
                        'score': total_score
                    }
                    
            except Exception as e:
                logger.debug(f"Analysis failed for {symbol}: {e}")
                continue
        
        if best_opportunity:
            logger.info(f"Best micro opportunity: {best_opportunity['symbol']} "
                       f"(score: {best_opportunity['score']:.4f})")
        
        return best_opportunity
    
    def execute_micro_trade(self, opportunity: dict, available_usdt: float) -> bool:
        """Execute ultra-precise micro trade"""
        symbol = opportunity['symbol']
        price = opportunity['price']
        min_size = opportunity['min_size']
        
        # Calculate maximum tradable amount
        usable_amount = available_usdt - self.buffer_amount
        trade_amount = min(usable_amount * self.trade_percentage, usable_amount)
        
        if trade_amount < opportunity['min_usdt']:
            logger.warning(f"Trade amount ${trade_amount:.6f} below minimum ${opportunity['min_usdt']:.6f}")
            return False
        
        # Calculate exact quantity
        quantity = trade_amount / price
        quantity = max(quantity, min_size)
        
        # Ensure quantity precision
        quantity = round(quantity / min_size) * min_size
        actual_amount = quantity * price
        
        logger.info(f"EXECUTING MICRO TRADE:")
        logger.info(f"  Symbol: {symbol}")
        logger.info(f"  Quantity: {quantity:.8f}")
        logger.info(f"  Amount: ${actual_amount:.6f}")
        logger.info(f"  Price: ${price:.6f}")
        logger.info(f"  Available: ${available_usdt:.6f}")
        logger.info(f"  Buffer: ${self.buffer_amount:.6f}")
        
        # Execute trade
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        response = self.safe_request('POST', '/api/v5/trade/order', order_body)
        
        if response and response.get('data'):
            order_id = response['data'][0]['ordId']
            logger.info(f"MICRO TRADE SUCCESSFUL!")
            logger.info(f"  Order ID: {order_id}")
            logger.info(f"  Symbol: {symbol}")
            logger.info(f"  Quantity: {quantity:.8f}")
            return True
        else:
            error_msg = response.get('msg', 'Unknown error') if response else 'Request failed'
            logger.error(f"Micro trade failed: {error_msg}")
            return False
    
    def run_micro_trading_cycle(self) -> bool:
        """Execute one complete micro trading cycle"""
        logger.info("=== MICRO TRADING CYCLE START ===")
        
        # Get exact balance
        balance = self.get_precise_balance()
        if balance < self.min_usdt_amount:
            logger.info(f"Balance ${balance:.6f} below micro threshold ${self.min_usdt_amount}")
            return False
        
        # Find optimal opportunity
        opportunity = self.get_optimal_micro_pair()
        if not opportunity:
            logger.warning("No micro trading opportunities found")
            return False
        
        # Execute trade
        success = self.execute_micro_trade(opportunity, balance)
        
        if success:
            logger.info("MICRO TRADING CYCLE COMPLETED SUCCESSFULLY")
        else:
            logger.info("MICRO TRADING CYCLE FAILED")
        
        logger.info("=== MICRO TRADING CYCLE END ===")
        return success

def main():
    """Execute micro trading operation"""
    trader = UltraMicroTrader()
    
    logger.info("Starting Ultra Micro Trading Operation...")
    
    # Execute trading cycle
    success = trader.run_micro_trading_cycle()
    
    if success:
        logger.info("Ultra Micro Trading completed successfully")
    else:
        logger.info("Ultra Micro Trading cycle failed")

if __name__ == "__main__":
    main()