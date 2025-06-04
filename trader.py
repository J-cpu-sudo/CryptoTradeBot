import os
import requests
import time
import hashlib
import hmac
import base64
import json
from datetime import datetime
from typing import Optional, Dict, Any
import logging

class Trader:
    def __init__(self):
        self.api_key = os.getenv("OKX_API_KEY")
        self.secret_key = os.getenv("OKX_SECRET_KEY")
        self.passphrase = os.getenv("OKX_PASSPHRASE")
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self.base_url = "https://www.okx.com"
        
        # Validate API credentials
        if not all([self.api_key, self.secret_key, self.passphrase]):
            logging.warning("OKX API credentials not fully configured")
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """Generate signature for OKX API authentication"""
        if not self.secret_key:
            return ""
        
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    def _get_headers(self, method: str, request_path: str, body: str = "") -> Dict[str, str]:
        """Get headers for OKX API request"""
        timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
        
        headers = {
            'Content-Type': 'application/json',
            'OK-ACCESS-KEY': self.api_key or "",
            'OK-ACCESS-SIGN': self._generate_signature(timestamp, method, request_path, body),
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase or "",
        }
        
        return headers
    
    def get_account_balance(self) -> Optional[Dict[str, Any]]:
        """Get account balance"""
        if self.dry_run or not self.api_key:
            return {
                'totalEq': '10000.0',
                'availEq': '9500.0',
                'details': [
                    {'ccy': 'USDT', 'bal': '9500.0', 'frozenBal': '500.0'}
                ]
            }
        
        try:
            request_path = '/api/v5/account/balance'
            headers = self._get_headers('GET', request_path)
            
            response = requests.get(
                f"{self.base_url}{request_path}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    return data.get('data', [{}])[0]
            
            logging.error(f"Failed to get account balance: {response.text}")
            return None
            
        except Exception as e:
            logging.error(f"Error getting account balance: {e}")
            return None
    
    def get_ticker(self, symbol: str = "BTC-USDT") -> Optional[Dict[str, Any]]:
        """Get ticker information for a symbol"""
        if self.dry_run:
            # Return mock data for dry run
            import random
            base_price = 45000 if symbol == "BTC-USDT" else 3000
            return {
                'instId': symbol,
                'last': str(base_price + random.uniform(-1000, 1000)),
                'lastSz': '0.1',
                'askPx': str(base_price + random.uniform(0, 50)),
                'bidPx': str(base_price - random.uniform(0, 50)),
                'vol24h': str(random.uniform(1000, 5000))
            }
        
        try:
            request_path = f'/api/v5/market/ticker?instId={symbol}'
            
            response = requests.get(
                f"{self.base_url}{request_path}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0' and data.get('data'):
                    return data['data'][0]
            
            logging.error(f"Failed to get ticker for {symbol}: {response.text}")
            return None
            
        except Exception as e:
            logging.error(f"Error getting ticker for {symbol}: {e}")
            return None
    
    def place_order(self, side: str, symbol: str, size: str, price: str = None, order_type: str = "market") -> Optional[Dict[str, Any]]:
        """Place a trading order"""
        if self.dry_run:
            # Simulate order placement
            order_id = f"dry_run_{int(time.time())}"
            logging.info(f"DRY RUN: {side.upper()} order for {size} {symbol} at {price or 'market price'}")
            return {
                'ordId': order_id,
                'clOrdId': '',
                'tag': '',
                'sCode': '0',
                'sMsg': 'Order placed successfully (dry run)'
            }
        
        if not self.api_key:
            logging.error("Cannot place real order: API credentials not configured")
            return None
        
        try:
            request_path = '/api/v5/trade/order'
            
            order_data = {
                'instId': symbol,
                'tdMode': 'cash',
                'side': side,
                'ordType': order_type,
                'sz': size
            }
            
            if price and order_type == 'limit':
                order_data['px'] = price
            
            body = json.dumps(order_data)
            headers = self._get_headers('POST', request_path, body)
            
            response = requests.post(
                f"{self.base_url}{request_path}",
                headers=headers,
                data=body,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0' and data.get('data'):
                    return data['data'][0]
            
            logging.error(f"Failed to place order: {response.text}")
            return None
            
        except Exception as e:
            logging.error(f"Error placing order: {e}")
            return None
    
    def buy(self, symbol: str = "BTC-USDT", size: str = "0.001", price: str = None) -> Optional[Dict[str, Any]]:
        """Place a buy order"""
        return self.place_order('buy', symbol, size, price)
    
    def sell(self, symbol: str = "BTC-USDT", size: str = "0.001", price: str = None) -> Optional[Dict[str, Any]]:
        """Place a sell order"""
        return self.place_order('sell', symbol, size, price)
    
    def get_order_status(self, order_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get order status"""
        if self.dry_run:
            return {
                'ordId': order_id,
                'state': 'filled',
                'fillSz': '0.001',
                'avgPx': '45000.0'
            }
        
        if not self.api_key:
            return None
        
        try:
            request_path = f'/api/v5/trade/order?ordId={order_id}&instId={symbol}'
            headers = self._get_headers('GET', request_path)
            
            response = requests.get(
                f"{self.base_url}{request_path}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0' and data.get('data'):
                    return data['data'][0]
            
            return None
            
        except Exception as e:
            logging.error(f"Error getting order status: {e}")
            return None
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        if self.dry_run:
            logging.info(f"DRY RUN: Cancel order {order_id}")
            return True
        
        if not self.api_key:
            return False
        
        try:
            request_path = '/api/v5/trade/cancel-order'
            
            cancel_data = {
                'instId': symbol,
                'ordId': order_id
            }
            
            body = json.dumps(cancel_data)
            headers = self._get_headers('POST', request_path, body)
            
            response = requests.post(
                f"{self.base_url}{request_path}",
                headers=headers,
                data=body,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('code') == '0'
            
            return False
            
        except Exception as e:
            logging.error(f"Error canceling order: {e}")
            return False
