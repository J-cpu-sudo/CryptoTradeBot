#!/usr/bin/env python3
"""
Execute Immediate Trade - Force trade execution to generate needed balance
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

class ImmediateTradeExecutor:
    """Execute immediate trades with maximum precision"""
    
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        logger.info("Immediate Trade Executor initialized")
    
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
            logger.error(f"Request failed: {e}")
            return None
    
    def get_balance(self):
        """Get current account balance"""
        response = self.api_request('GET', '/api/v5/account/balance')
        
        if response and response.status_code == 200:
            data = response.json()
            if data.get('code') == '0':
                for detail in data['data'][0]['details']:
                    if detail['ccy'] == 'USDT':
                        balance = float(detail['availBal'])
                        logger.info(f"Current USDT balance: ${balance:.8f}")
                        return balance
        return 0.0
    
    def find_tradeable_asset(self):
        """Find an asset we can trade with current balance"""
        balance = self.get_balance()
        logger.info(f"Searching for tradeable assets with ${balance:.8f}")
        
        # Test pairs with very low minimums
        test_pairs = [
            'MEME-USDT',
            'NEIRO-USDT', 
            'SATS-USDT',
            'RATS-USDT',
            'CAT-USDT',
            'PEPE-USDT'
        ]
        
        for symbol in test_pairs:
            try:
                # Get instrument info
                inst_response = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
                if not inst_response or inst_response.status_code != 200:
                    continue
                
                inst_data = inst_response.json()
                if not inst_data.get('data'):
                    continue
                
                instrument = inst_data['data'][0]
                min_size = float(instrument['minSz'])
                
                # Get current price
                ticker_response = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
                if not ticker_response or ticker_response.status_code != 200:
                    continue
                
                ticker_data = ticker_response.json()
                if not ticker_data.get('data'):
                    continue
                
                price = float(ticker_data['data'][0]['last'])
                min_order_value = min_size * price
                
                logger.info(f"{symbol}: Price ${price:.8f}, Min order ${min_order_value:.8f}")
                
                # Check if we can afford this
                if balance > min_order_value * 1.01:  # Small buffer for fees
                    logger.info(f"✓ {symbol} is tradeable with current balance")
                    return {
                        'symbol': symbol,
                        'price': price,
                        'min_size': min_size,
                        'min_order_value': min_order_value
                    }
                
            except Exception as e:
                logger.debug(f"Error checking {symbol}: {e}")
                continue
        
        return None
    
    def execute_buy_trade(self, asset_info):
        """Execute a buy trade for the specified asset"""
        symbol = asset_info['symbol']
        price = asset_info['price']
        min_size = asset_info['min_size']
        
        balance = self.get_balance()
        
        # Calculate quantity - use 98% of balance to leave room for fees
        usable_balance = balance * 0.98
        quantity = usable_balance / price
        
        # Ensure we meet minimum size
        if quantity < min_size:
            quantity = min_size
        
        logger.info(f"Executing BUY order:")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Quantity: {quantity:.8f}")
        logger.info(f"Estimated cost: ${quantity * price:.6f}")
        
        # Create market buy order
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
                logger.info(f"✓ BUY ORDER SUCCESSFUL - Order ID: {order_id}")
                
                # Wait a moment then sell to generate balance
                time.sleep(3)
                return self.execute_sell_trade(symbol, order_id)
            else:
                logger.error(f"Buy order failed: {result.get('msg')}")
                return False
        else:
            logger.error("Buy order request failed")
            return False
    
    def execute_sell_trade(self, symbol, buy_order_id):
        """Execute sell trade to convert back to USDT"""
        logger.info(f"Executing SELL order for {symbol}")
        
        # Get current holdings
        time.sleep(2)
        response = self.api_request('GET', '/api/v5/account/balance')
        
        if not response or response.status_code != 200:
            logger.error("Failed to get balance for sell")
            return False
        
        data = response.json()
        if data.get('code') != '0':
            logger.error("Balance API error")
            return False
        
        # Find the asset we just bought
        asset_balance = 0
        base_currency = symbol.split('-')[0]  # Get base currency (e.g., MEME from MEME-USDT)
        
        for detail in data['data'][0]['details']:
            if detail['ccy'] == base_currency:
                asset_balance = float(detail['availBal'])
                break
        
        if asset_balance <= 0:
            logger.error(f"No {base_currency} balance found to sell")
            return False
        
        logger.info(f"Selling {asset_balance:.8f} {base_currency}")
        
        # Create market sell order
        sell_order_data = {
            "instId": symbol,
            "tdMode": "cash", 
            "side": "sell",
            "ordType": "market",
            "sz": str(asset_balance)
        }
        
        sell_body = json.dumps(sell_order_data)
        sell_response = self.api_request('POST', '/api/v5/trade/order', sell_body)
        
        if sell_response and sell_response.status_code == 200:
            result = sell_response.json()
            if result.get('code') == '0':
                sell_order_id = result['data'][0]['ordId']
                logger.info(f"✓ SELL ORDER SUCCESSFUL - Order ID: {sell_order_id}")
                
                # Check final balance
                time.sleep(3)
                final_balance = self.get_balance()
                logger.info(f"Final balance: ${final_balance:.8f}")
                
                return final_balance > 1.20  # Check if we now have enough for autonomous trading
            else:
                logger.error(f"Sell order failed: {result.get('msg')}")
                return False
        else:
            logger.error("Sell order request failed")
            return False
    
    def execute_balance_generation_strategy(self):
        """Execute complete strategy to generate needed balance"""
        logger.info("EXECUTING BALANCE GENERATION STRATEGY")
        logger.info("=" * 50)
        
        # Find a tradeable asset
        asset_info = self.find_tradeable_asset()
        if not asset_info:
            logger.error("No tradeable assets found with current balance")
            return False
        
        logger.info(f"Selected asset: {asset_info['symbol']}")
        
        # Execute buy then sell to generate balance change
        success = self.execute_buy_trade(asset_info)
        
        if success:
            logger.info("✓ BALANCE GENERATION SUCCESSFUL")
            logger.info("🚀 AUTONOMOUS TRADING SYSTEM ACTIVATED")
            return True
        else:
            logger.error("❌ BALANCE GENERATION FAILED")
            return False

def main():
    """Execute immediate trade to generate balance"""
    executor = ImmediateTradeExecutor()
    success = executor.execute_balance_generation_strategy()
    
    if success:
        logger.info("Trade execution completed successfully")
    else:
        logger.info("Trade execution unsuccessful")

if __name__ == "__main__":
    main()