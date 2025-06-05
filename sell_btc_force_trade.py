#!/usr/bin/env python3
"""
Sell BTC for USDT to increase trading balance
"""
import os
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone

def sell_btc_for_usdt():
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
    
    print("Checking current portfolio...")
    
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
    
    portfolio = {}
    for detail in data['data'][0]['details']:
        if float(detail['availBal']) > 0:
            portfolio[detail['ccy']] = float(detail['availBal'])
    
    print("Current portfolio:")
    for currency, balance in portfolio.items():
        print(f"  {currency}: {balance:.8f}")
    
    # Check if we have BTC to sell
    btc_balance = portfolio.get('BTC', 0)
    if btc_balance > 0.00001:  # Minimum BTC to sell
        print(f"\nSelling {btc_balance:.8f} BTC for USDT...")
        
        # Get BTC-USDT instrument info
        response = requests.get(f"{base_url}/api/v5/public/instruments?instType=SPOT&instId=BTC-USDT")
        if response.status_code == 200:
            inst_data = response.json()
            if inst_data.get('data'):
                min_size = float(inst_data['data'][0]['minSz'])
                
                if btc_balance >= min_size:
                    # Sell all BTC
                    order_data = {
                        "instId": "BTC-USDT",
                        "tdMode": "cash",
                        "side": "sell",
                        "ordType": "market",
                        "sz": str(btc_balance)
                    }
                    
                    order_body = json.dumps(order_data)
                    headers = get_headers('POST', '/api/v5/trade/order', order_body)
                    response = requests.post(base_url + '/api/v5/trade/order', 
                                           headers=headers, data=order_body)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get('code') == '0':
                            order_id = result['data'][0]['ordId']
                            print(f"BTC SELL ORDER SUCCESSFUL!")
                            print(f"Order ID: {order_id}")
                            return True
                        else:
                            print(f"Sell order failed: {result.get('msg')}")
                    else:
                        print(f"HTTP Error: {response.status_code}")
                else:
                    print(f"BTC balance {btc_balance:.8f} below minimum {min_size}")
    
    # Check for other tokens to sell
    for currency, balance in portfolio.items():
        if currency not in ['USDT', 'BTC'] and balance > 0:
            symbol = f"{currency}-USDT"
            print(f"\nTrying to sell {currency}...")
            
            try:
                # Get instrument info
                response = requests.get(f"{base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}")
                if response.status_code == 200:
                    inst_data = response.json()
                    if inst_data.get('data'):
                        min_size = float(inst_data['data'][0]['minSz'])
                        
                        if balance >= min_size:
                            # Sell the token
                            order_data = {
                                "instId": symbol,
                                "tdMode": "cash",
                                "side": "sell",
                                "ordType": "market",
                                "sz": str(balance)
                            }
                            
                            order_body = json.dumps(order_data)
                            headers = get_headers('POST', '/api/v5/trade/order', order_body)
                            response = requests.post(base_url + '/api/v5/trade/order', 
                                                   headers=headers, data=order_body)
                            
                            if response.status_code == 200:
                                result = response.json()
                                if result.get('code') == '0':
                                    order_id = result['data'][0]['ordId']
                                    print(f"{currency} SELL ORDER SUCCESSFUL!")
                                    print(f"Order ID: {order_id}")
                                    return True
                                else:
                                    print(f"Sell order failed: {result.get('msg')}")
                        else:
                            print(f"{currency} balance {balance:.8f} below minimum {min_size}")
            except:
                continue
    
    print("No sellable assets found")
    return False

if __name__ == "__main__":
    print("Converting assets to USDT for trading...")
    print("=" * 50)
    sell_btc_for_usdt()