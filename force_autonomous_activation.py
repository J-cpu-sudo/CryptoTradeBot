#!/usr/bin/env python3
"""
Force Autonomous Activation - Immediate trade execution with aggressive parameters
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime, timezone

def force_immediate_execution():
    print("FORCING IMMEDIATE AUTONOMOUS EXECUTION")
    print("=" * 50)
    
    api_key = str(os.environ.get('OKX_API_KEY', ''))
    secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
    passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
    base_url = 'https://www.okx.com'
    
    def get_timestamp():
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def create_signature(timestamp, method, path, body=''):
        message = timestamp + method + path + body
        signature = hmac.new(
            secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(method, path, body=''):
        timestamp = get_timestamp()
        signature = create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': passphrase,
            'Content-Type': 'application/json'
        }
    
    def api_request(method, endpoint, body=None):
        try:
            headers = get_headers(method, endpoint, body or '')
            url = base_url + endpoint
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    return data
            
            return None
        except Exception as e:
            print(f"API Error: {e}")
            return None
    
    def get_balance():
        data = api_request('GET', '/api/v5/account/balance')
        if data:
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    return float(detail['availBal'])
        return 0
    
    def execute_aggressive_trade(symbol, amount):
        # Get current price
        ticker_data = api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker_data:
            return None
        
        price = float(ticker_data['data'][0]['last'])
        
        # Get instrument info
        inst_data = api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data:
            return None
        
        min_size = float(inst_data['data'][0]['minSz'])
        quantity = amount / price
        
        if quantity < min_size:
            return None
        
        # Round to proper precision
        quantity = round(quantity / min_size) * min_size
        
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        result = api_request('POST', '/api/v5/trade/order', order_body)
        
        if result:
            order_id = result['data'][0]['ordId']
            print(f"TRADE EXECUTED: {symbol}")
            print(f"  Quantity: {quantity}")
            print(f"  Price: ${price}")
            print(f"  Amount: ${amount}")
            print(f"  Order ID: {order_id}")
            return order_id
        
        return None
    
    # Get current balance
    balance = get_balance()
    print(f"Current USDT Balance: ${balance:.2f}")
    
    if balance < 1:
        print("Insufficient balance for trading")
        return
    
    # Aggressive trading symbols for immediate execution
    aggressive_symbols = [
        'PEPE-USDT',   # High volatility meme coin
        'DOGE-USDT',   # Popular with good liquidity
        'SHIB-USDT',   # High volume meme coin
        'TRX-USDT',    # Good for quick trades
        'ADA-USDT',    # Reliable altcoin
        'XRP-USDT'     # High liquidity
    ]
    
    trades_executed = 0
    max_trades = 3  # Execute multiple trades for full automation
    
    for symbol in aggressive_symbols:
        if balance < 1.5:
            break
        
        if trades_executed >= max_trades:
            break
        
        # Use 25-30% of available balance per trade
        trade_amount = min(balance * 0.28, balance - 1)  # Keep $1 buffer
        
        if trade_amount >= 1:
            print(f"\nExecuting aggressive trade: {symbol}")
            order_id = execute_aggressive_trade(symbol, trade_amount)
            
            if order_id:
                trades_executed += 1
                balance -= trade_amount
                print(f"SUCCESS - Remaining balance: ${balance:.2f}")
                time.sleep(2)  # Brief pause between trades
            else:
                print(f"FAILED - Trying next symbol")
    
    print(f"\nAGGRESSIVE EXECUTION COMPLETE")
    print(f"Trades executed: {trades_executed}")
    print(f"Remaining balance: ${balance:.2f}")
    
    if trades_executed > 0:
        print("AUTONOMOUS TRADING NOW FULLY ACTIVE")
    else:
        print("NO TRADES EXECUTED - INVESTIGATING ISSUES")

if __name__ == "__main__":
    force_immediate_execution()