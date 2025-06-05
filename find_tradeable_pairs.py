#!/usr/bin/env python3
"""
Find Tradeable Pairs - Discover trading pairs that work with current balance
"""
import os
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone

def find_tradeable_pairs():
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
    
    # Get current balance
    headers = get_headers('GET', '/api/v5/account/balance')
    response = requests.get(base_url + '/api/v5/account/balance', headers=headers)
    
    usdt_balance = 0.0
    if response.status_code == 200:
        data = response.json()
        if data.get('code') == '0':
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    usdt_balance = float(detail['availBal'])
                    break
    
    print(f"Current USDT balance: ${usdt_balance:.8f}")
    
    # Get all USDT trading pairs
    response = requests.get(base_url + '/api/v5/public/instruments?instType=SPOT')
    if response.status_code != 200:
        print("Failed to get instruments")
        return
    
    instruments = response.json()['data']
    usdt_pairs = [inst for inst in instruments if inst['quoteCcy'] == 'USDT' and inst['state'] == 'live']
    
    print(f"Found {len(usdt_pairs)} active USDT trading pairs")
    print("\nScanning for tradeable pairs...")
    
    tradeable_pairs = []
    
    for inst in usdt_pairs:
        symbol = inst['instId']
        min_size = float(inst['minSz'])
        tick_size = float(inst['tickSz'])
        
        try:
            # Get current price
            response = requests.get(f"{base_url}/api/v5/market/ticker?instId={symbol}")
            if response.status_code == 200:
                ticker_data = response.json()
                if ticker_data.get('data'):
                    price = float(ticker_data['data'][0]['last'])
                    min_usdt = min_size * price
                    
                    if min_usdt <= usdt_balance * 0.95:  # 95% of balance to leave buffer
                        volume_24h = float(ticker_data['data'][0]['vol24h'])
                        change_24h = float(ticker_data['data'][0]['sodUtc8'])
                        
                        tradeable_pairs.append({
                            'symbol': symbol,
                            'price': price,
                            'min_size': min_size,
                            'min_usdt': min_usdt,
                            'volume_24h': volume_24h,
                            'change_24h': change_24h
                        })
        except:
            continue
    
    if tradeable_pairs:
        print(f"\nFound {len(tradeable_pairs)} tradeable pairs:")
        print("=" * 80)
        
        # Sort by minimum USDT requirement (ascending)
        tradeable_pairs.sort(key=lambda x: x['min_usdt'])
        
        for pair in tradeable_pairs[:20]:  # Show top 20
            print(f"{pair['symbol']:15} | Price: ${pair['price']:.8f} | "
                  f"Min: ${pair['min_usdt']:.6f} | "
                  f"Volume: {pair['volume_24h']:>12,.0f} | "
                  f"Change: {pair['change_24h']:+6.2f}%")
    else:
        print("\nNo tradeable pairs found with current balance")
    
    return tradeable_pairs

if __name__ == "__main__":
    find_tradeable_pairs()