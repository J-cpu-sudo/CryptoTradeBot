#!/usr/bin/env python3
"""
Force Micro Trade - Aggressive micro trading to maximize available balance utilization
"""
import os
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone

def force_micro_trade():
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
    
    # Get balance
    headers = get_headers('GET', '/api/v5/account/balance')
    response = requests.get(base_url + '/api/v5/account/balance', headers=headers)
    
    if response.status_code != 200:
        print("Failed to get balance")
        return False
    
    data = response.json()
    if data.get('code') != '0':
        print(f"API Error: {data.get('msg')}")
        return False
    
    usdt_balance = 0.0
    for detail in data['data'][0]['details']:
        if detail['ccy'] == 'USDT':
            usdt_balance = float(detail['availBal'])
            break
    
    print(f"Current USDT balance: ${usdt_balance:.8f}")
    
    # Check minimum tradeable pairs with very low requirements
    micro_pairs = [
        'RATS-USDT',  # Often has very low minimum
        'ORDI-USDT',  # Bitcoin ecosystem token
        'SATS-USDT',  # Satoshi token
        'MEME-USDT',  # Meme token
        'TURBO-USDT', # Another meme token
        'PEPE-USDT',  # Popular meme
        'BABYDOGE-USDT', # Micro cap
        'X-USDT',     # Simple token
        'NEIRO-USDT', # AI token
        'WIF-USDT'    # Dogwifhat
    ]
    
    print("Scanning for micro trading opportunities...")
    
    for symbol in micro_pairs:
        try:
            # Get ticker
            response = requests.get(f"{base_url}/api/v5/market/ticker?instId={symbol}")
            if response.status_code != 200:
                continue
                
            ticker_data = response.json()
            if not ticker_data.get('data'):
                continue
            
            price = float(ticker_data['data'][0]['last'])
            
            # Get instrument info
            response = requests.get(f"{base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}")
            if response.status_code != 200:
                continue
                
            inst_data = response.json()
            if not inst_data.get('data'):
                continue
            
            min_size = float(inst_data['data'][0]['minSz'])
            min_usdt_required = min_size * price
            
            print(f"{symbol}: Price ${price:.8f}, Min ${min_usdt_required:.6f}")
            
            # If we can trade this pair
            if min_usdt_required <= usdt_balance * 0.98:  # Use 98% to account for fees
                print(f"EXECUTING MICRO TRADE: {symbol}")
                
                # Calculate exact quantity
                usable_amount = usdt_balance * 0.95  # Leave 5% buffer
                quantity = usable_amount / price
                quantity = max(quantity, min_size)
                
                # Round to proper precision
                quantity = round(quantity / min_size) * min_size
                
                print(f"Trade details:")
                print(f"  Symbol: {symbol}")
                print(f"  Quantity: {quantity:.8f}")
                print(f"  Price: ${price:.8f}")
                print(f"  Amount: ${quantity * price:.6f}")
                
                # Execute trade
                order_data = {
                    "instId": symbol,
                    "tdMode": "cash",
                    "side": "buy",
                    "ordType": "market",
                    "sz": str(quantity)
                }
                
                order_body = json.dumps(order_data)
                headers = get_headers('POST', '/api/v5/trade/order', order_body)
                response = requests.post(base_url + '/api/v5/trade/order', 
                                       headers=headers, data=order_body)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('code') == '0':
                        order_id = result['data'][0]['ordId']
                        print(f"TRADE SUCCESSFUL!")
                        print(f"Order ID: {order_id}")
                        return True
                    else:
                        print(f"Trade failed: {result.get('msg')}")
                else:
                    print(f"HTTP Error: {response.status_code}")
                
        except Exception as e:
            print(f"Error with {symbol}: {e}")
            continue
    
    print("No micro trading opportunities found")
    return False

if __name__ == "__main__":
    print("Force Micro Trading System")
    print("=" * 40)
    force_micro_trade()