#!/usr/bin/env python3
"""
Fractional Trader - Ultra-minimal trading with exact balance utilization
Uses innovative fractional trading strategies to execute with current balance
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FractionalTrader:
    """Fractional trading with exact balance calculations"""
    
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Micro-pairs with potential for fractional trading
        self.micro_pairs = [
            'RATS-USDT',     # Bitcoin ordinals with ultra-low minimums
            'SATS-USDT',     # Alternative ordinals token
            'ORDI-USDT',     # Original ordinals token
            'MEME-USDT',     # Meme token with potential micro trading
            'NEIRO-USDT',    # Previously viable option
            'CAT-USDT',      # Alternative micro token
            'TURBO-USDT'     # Experimental micro token
        ]
        
        logger.info("Fractional Trader initialized for micro-balance execution")
    
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
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def get_exact_balance(self) -> float:
        response = self.api_request('GET', '/api/v5/account/balance')
        
        if response and response.get('code') == '0':
            for detail in response['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    balance = float(detail['availBal'])
                    logger.info(f"Exact balance: ${balance:.10f}")
                    return balance
        return 0.0
    
    def scan_micro_opportunities(self):
        """Scan for ultra-low minimum order opportunities"""
        logger.info("Scanning for micro trading opportunities...")
        
        viable_options = []
        
        for symbol in self.micro_pairs:
            try:
                # Get instrument data
                inst_response = requests.get(
                    f"{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}",
                    timeout=10
                )
                
                if inst_response.status_code == 200:
                    data = inst_response.json()
                    if data.get('data'):
                        instrument = data['data'][0]
                        min_size = float(instrument.get('minSz', '0'))
                        
                        # Get current price
                        ticker_response = requests.get(
                            f"{self.base_url}/api/v5/market/ticker?instId={symbol}",
                            timeout=10
                        )
                        
                        if ticker_response.status_code == 200:
                            ticker_data = ticker_response.json()
                            if ticker_data.get('data'):
                                price = float(ticker_data['data'][0]['last'])
                                min_order_value = min_size * price
                                
                                viable_options.append({
                                    'symbol': symbol,
                                    'min_size': min_size,
                                    'price': price,
                                    'min_order_value': min_order_value
                                })
                                
                                logger.info(f"{symbol}: Min order ${min_order_value:.8f}")
            except Exception as e:
                logger.debug(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by minimum order value
        viable_options.sort(key=lambda x: x['min_order_value'])
        return viable_options
    
    def attempt_fractional_execution(self, option: dict, balance: float) -> bool:
        """Attempt execution with fractional precision"""
        symbol = option['symbol']
        min_size = option['min_size']
        price = option['price']
        min_order_value = option['min_order_value']
        
        # Ultra-precise calculation
        available_for_trade = balance * 0.999  # Keep tiny buffer
        
        if available_for_trade < min_order_value:
            logger.info(f"{symbol}: ${available_for_trade:.8f} < ${min_order_value:.8f}")
            return False
        
        # Calculate exact quantity
        quantity = available_for_trade / price
        
        # Ensure we meet minimum size
        if quantity < min_size:
            quantity = min_size
        
        # Final cost check
        final_cost = quantity * price
        if final_cost > balance:
            logger.info(f"{symbol}: Final cost ${final_cost:.8f} exceeds balance")
            return False
        
        logger.info(f"Attempting fractional execution: {symbol}")
        logger.info(f"Quantity: {quantity:.10f}")
        logger.info(f"Cost: ${final_cost:.8f}")
        
        # Execute order
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        response = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if response and response.get('code') == '0':
            order_id = response['data'][0]['ordId']
            logger.info(f"FRACTIONAL EXECUTION SUCCESS: {order_id}")
            return True
        else:
            error_msg = response.get('msg', 'Unknown') if response else 'Failed'
            logger.warning(f"Fractional execution failed: {error_msg}")
            return False
    
    def execute_fractional_strategy(self) -> bool:
        """Execute fractional trading strategy"""
        logger.info("EXECUTING FRACTIONAL TRADING STRATEGY")
        
        balance = self.get_exact_balance()
        if balance < 0.1:
            logger.error(f"Balance too low: ${balance:.8f}")
            return False
        
        opportunities = self.scan_micro_opportunities()
        if not opportunities:
            logger.error("No micro opportunities found")
            return False
        
        logger.info(f"Found {len(opportunities)} micro opportunities")
        
        for option in opportunities:
            success = self.attempt_fractional_execution(option, balance)
            if success:
                logger.info(f"SUCCESS: Fractional trade executed on {option['symbol']}")
                return True
        
        logger.warning("All fractional attempts failed")
        return False

def main():
    trader = FractionalTrader()
    success = trader.execute_fractional_strategy()
    
    if success:
        logger.info("Fractional trading successful - autonomous system activated")
    else:
        logger.info("Fractional trading unsuccessful - balance requirements not met")

if __name__ == "__main__":
    main()