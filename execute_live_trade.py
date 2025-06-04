#!/usr/bin/env python3
"""
Execute first live trade to demonstrate system capability
"""

import os
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime

def get_server_time():
    """Get current timestamp in milliseconds"""
    import time
    return str(int(time.time() * 1000))

def sign_request(timestamp, method, request_path, body=''):
    """Sign OKX API request"""
    secret_key = os.environ.get('OKX_SECRET_KEY')
    if not secret_key:
        raise ValueError("OKX_SECRET_KEY not found")
    
    message = timestamp + method + request_path + body
    mac = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        digestmod=hashlib.sha256
    )
    return base64.b64encode(mac.digest()).decode('utf-8')

def place_market_order():
    """Place a small BTC market buy order"""
    
    # API credentials
    api_key = os.environ.get('OKX_API_KEY')
    passphrase = os.environ.get('OKX_PASSPHRASE')
    secret_key = os.environ.get('OKX_SECRET_KEY')
    
    if not all([api_key, passphrase, secret_key]):
        print("Missing OKX API credentials")
        return None
    
    # Get timestamp
    timestamp = get_server_time()
    
    # Order parameters - small test order
    order_data = {
        "instId": "BTC-USDT",
        "tdMode": "cash",  # Cash trading
        "side": "buy",
        "ordType": "market",
        "sz": "15",  # $15 USD worth
        "tgtCcy": "quote_ccy"  # Order size in quote currency (USD)
    }
    
    body = json.dumps(order_data)
    method = 'POST'
    request_path = '/api/v5/trade/order'
    
    # Sign request
    signature = sign_request(timestamp, method, request_path, body)
    
    # Headers
    headers = {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }
    
    # Execute order
    url = f'https://www.okx.com{request_path}'
    
    print(f"Placing live market order: $15 USD worth of BTC")
    print(f"Current BTC price: ~$104,846")
    
    try:
        response = requests.post(url, headers=headers, data=body)
        result = response.json()
        
        print(f"Response: {result}")
        
        if result.get('code') == '0':
            order_id = result['data'][0]['ordId']
            print(f"✅ LIVE TRADE EXECUTED!")
            print(f"Order ID: {order_id}")
            print(f"Side: BUY")
            print(f"Amount: $15 USD worth of BTC")
            print(f"Status: Order placed successfully")
            return result
        else:
            print(f"❌ Order failed: {result.get('msg', 'Unknown error')}")
            return result
            
    except Exception as e:
        print(f"Error placing order: {e}")
        return None

if __name__ == "__main__":
    place_market_order()