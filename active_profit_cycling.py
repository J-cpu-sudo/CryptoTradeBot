#!/usr/bin/env python3
"""
Active Profit Cycling - Rapid buy/sell cycles to maximize balance growth
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime, timezone

def execute_profit_cycle():
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
    
    def get_balance():
        headers = get_headers('GET', '/api/v5/account/balance')
        response = requests.get(base_url + '/api/v5/account/balance', headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == '0':
                portfolio = {}
                for detail in data['data'][0]['details']:
                    if float(detail['availBal']) > 0:
                        portfolio[detail['ccy']] = float(detail['availBal'])
                return portfolio
        return {}
    
    def get_price(symbol):
        response = requests.get(f"{base_url}/api/v5/market/ticker?instId={symbol}")
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                return float(data['data'][0]['last'])
        return None
    
    def get_min_size(symbol):
        response = requests.get(f"{base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}")
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                return float(data['data'][0]['minSz'])
        return None
    
    def buy_token(symbol, usdt_amount):
        price = get_price(symbol)
        min_size = get_min_size(symbol)
        
        if not price or not min_size:
            return None
        
        quantity = usdt_amount / price
        if quantity < min_size:
            return None
        
        quantity = round(quantity / min_size) * min_size
        
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        headers = get_headers('POST', '/api/v5/trade/order', order_body)
        response = requests.post(base_url + '/api/v5/trade/order', headers=headers, data=order_body)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == '0':
                return result['data'][0]['ordId']
        return None
    
    def sell_token(symbol, quantity):
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "sell",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        headers = get_headers('POST', '/api/v5/trade/order', order_body)
        response = requests.post(base_url + '/api/v5/trade/order', headers=headers, data=order_body)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == '0':
                return result['data'][0]['ordId']
        return None
    
    print("Active Profit Cycling - Maximizing Balance Growth")
    print("=" * 55)
    
    # High-frequency trading pairs for quick profits
    active_pairs = [
        'PEPE-USDT',   # High volatility meme coin
        'NEIRO-USDT',  # AI token with movement
        'WIF-USDT',    # Dogwifhat - active trading
        'MEME-USDT',   # Already proven profitable
        'TURBO-USDT',  # Another volatile option
        'RATS-USDT'    # Bitcoin ecosystem token
    ]
    
    cycle_count = 0
    
    while True:
        cycle_count += 1
        print(f"\n--- Cycle #{cycle_count} at {datetime.now().strftime('%H:%M:%S')} ---")
        
        # Get current portfolio
        portfolio = get_balance()
        usdt_balance = portfolio.get('USDT', 0)
        
        print(f"USDT Balance: ${usdt_balance:.4f}")
        
        # Sell any existing holdings for profit
        for currency, balance in portfolio.items():
            if currency != 'USDT' and balance > 0:
                symbol = f"{currency}-USDT"
                current_price = get_price(symbol)
                
                if current_price:
                    value = balance * current_price
                    print(f"Selling {currency}: {balance:.6f} tokens (${value:.4f})")
                    sell_order = sell_token(symbol, balance)
                    if sell_order:
                        print(f"  ✓ Sell Order: {sell_order}")
                        time.sleep(2)  # Brief pause between operations
        
        # Wait for sells to complete and refresh balance
        time.sleep(5)
        portfolio = get_balance()
        usdt_balance = portfolio.get('USDT', 0)
        
        print(f"Updated USDT Balance: ${usdt_balance:.4f}")
        
        # Buy new position if sufficient balance
        if usdt_balance >= 1.0:  # Minimum $1 to trade
            
            # Find best opportunity
            best_pair = None
            best_volatility = 0
            
            for symbol in active_pairs:
                try:
                    # Get recent price data for volatility check
                    response = requests.get(f"{base_url}/api/v5/market/candles?instId={symbol}&bar=1m&limit=10")
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('data'):
                            candles = data['data']
                            prices = [float(candle[4]) for candle in candles]
                            
                            if len(prices) >= 5:
                                high_price = max(prices[-5:])
                                low_price = min(prices[-5:])
                                volatility = (high_price - low_price) / low_price * 100
                                
                                if volatility > best_volatility:
                                    best_volatility = volatility
                                    best_pair = symbol
                except:
                    continue
            
            if best_pair:
                trade_amount = usdt_balance * 0.95  # Use 95% of balance
                print(f"Buying {best_pair} with ${trade_amount:.4f} (volatility: {best_volatility:.2f}%)")
                
                buy_order = buy_token(best_pair, trade_amount)
                if buy_order:
                    print(f"  ✓ Buy Order: {buy_order}")
                else:
                    print("  ✗ Buy order failed")
            else:
                print("No suitable trading opportunities")
        else:
            print("Insufficient balance for new trades")
        
        # Wait before next cycle
        wait_time = 45  # 45 seconds between cycles for rapid trading
        print(f"Waiting {wait_time} seconds...")
        time.sleep(wait_time)

if __name__ == "__main__":
    execute_profit_cycle()