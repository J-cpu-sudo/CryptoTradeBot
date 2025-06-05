#!/usr/bin/env python3
"""
Aggressive Balance Maximizer - Forces trades to maximize balance utilization
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime, timezone

def maximize_balance():
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
    
    def execute_trade(symbol, side, amount_or_quantity):
        if side == 'buy':
            # Buy with USDT amount
            price_resp = requests.get(f"{base_url}/api/v5/market/ticker?instId={symbol}")
            if price_resp.status_code != 200:
                return None
            
            price_data = price_resp.json()
            if not price_data.get('data'):
                return None
            
            price = float(price_data['data'][0]['last'])
            
            # Get min size
            inst_resp = requests.get(f"{base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}")
            if inst_resp.status_code != 200:
                return None
            
            inst_data = inst_resp.json()
            if not inst_data.get('data'):
                return None
            
            min_size = float(inst_data['data'][0]['minSz'])
            quantity = amount_or_quantity / price
            
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
        else:
            # Sell with token quantity
            order_data = {
                "instId": symbol,
                "tdMode": "cash",
                "side": "sell",
                "ordType": "market",
                "sz": str(amount_or_quantity)
            }
        
        order_body = json.dumps(order_data)
        headers = get_headers('POST', '/api/v5/trade/order', order_body)
        response = requests.post(base_url + '/api/v5/trade/order', headers=headers, data=order_body)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == '0':
                return result['data'][0]['ordId']
        return None
    
    print("AGGRESSIVE BALANCE MAXIMIZER")
    print("Forcing trades to maximize capital utilization")
    print("=" * 55)
    
    # Most liquid trading pairs for guaranteed execution
    priority_pairs = [
        'PEPE-USDT',   # High volume meme coin
        'DOGE-USDT',   # Established altcoin
        'ADA-USDT',    # Major cryptocurrency
        'TRX-USDT',    # TRON ecosystem
        'XRP-USDT',    # Ripple network
    ]
    
    cycle = 0
    
    while True:
        cycle += 1
        print(f"\n--- Aggressive Cycle #{cycle} at {datetime.now().strftime('%H:%M:%S')} ---")
        
        portfolio = get_balance()
        usdt_balance = portfolio.get('USDT', 0)
        
        print(f"Current Portfolio:")
        for currency, balance in portfolio.items():
            if balance > 0:
                print(f"  {currency}: {balance:.8f}")
        
        # Sell all holdings immediately
        sold_anything = False
        for currency, balance in portfolio.items():
            if currency != 'USDT' and balance > 0:
                symbol = f"{currency}-USDT"
                print(f"FORCE SELLING {currency}: {balance:.6f}")
                order_id = execute_trade(symbol, 'sell', balance)
                if order_id:
                    print(f"  ✓ Sell Order: {order_id}")
                    sold_anything = True
                    time.sleep(1)
        
        if sold_anything:
            print("Waiting for sells to settle...")
            time.sleep(5)
            portfolio = get_balance()
            usdt_balance = portfolio.get('USDT', 0)
            print(f"Updated USDT Balance: ${usdt_balance:.4f}")
        
        # Force buy with all available USDT
        if usdt_balance >= 0.5:  # Minimum $0.50 threshold
            
            # Choose pair with highest recent volume
            best_pair = priority_pairs[cycle % len(priority_pairs)]
            trade_amount = usdt_balance * 0.98  # Use 98% to account for fees
            
            print(f"FORCE BUYING {best_pair} with ${trade_amount:.4f}")
            order_id = execute_trade(best_pair, 'buy', trade_amount)
            
            if order_id:
                print(f"  ✓ Buy Order: {order_id}")
            else:
                print(f"  ✗ Buy failed, trying next pair")
                # Try alternative pairs
                for alt_pair in priority_pairs:
                    if alt_pair != best_pair:
                        print(f"Trying alternative: {alt_pair}")
                        order_id = execute_trade(alt_pair, 'buy', trade_amount)
                        if order_id:
                            print(f"  ✓ Alternative Buy: {order_id}")
                            break
        else:
            print(f"Insufficient balance: ${usdt_balance:.4f}")
        
        # Short cycle time for maximum turnover
        wait_time = 30
        print(f"Next cycle in {wait_time} seconds...")
        time.sleep(wait_time)

if __name__ == "__main__":
    maximize_balance()