#!/usr/bin/env python3
"""
Find cryptocurrency pairs with minimum order requirements that match available balance
"""
import os
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime

def find_suitable_pairs():
    """Find trading pairs with low minimum order requirements"""
    
    api_key = os.getenv('OKX_API_KEY')
    secret_key = os.getenv('OKX_SECRET_KEY') 
    passphrase = os.getenv('OKX_PASSPHRASE')
    base_url = 'https://www.okx.com'
    
    def generate_signature(timestamp, method, request_path, body=''):
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()

    def get_headers(method, request_path, body=''):
        timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
        signature = generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': passphrase,
            'Content-Type': 'application/json'
        }

    # Check small-cap cryptocurrencies with lower minimum requirements
    test_pairs = [
        "SHIB-USDT",  # Shiba Inu - very small units
        "PEPE-USDT",  # PEPE - micro pricing
        "FLOKI-USDT", # Floki - small minimum
        "BONK-USDT",  # Bonk - micro cap
        "DOGE-USDT",  # Dogecoin
        "XRP-USDT",   # Ripple
        "TRX-USDT",   # Tron
    ]
    
    suitable_pairs = []
    
    for pair in test_pairs:
        try:
            # Get instrument info
            instrument_response = requests.get(f'{base_url}/api/v5/public/instruments?instType=SPOT&instId={pair}')
            if instrument_response.status_code != 200:
                continue
                
            instrument_data = instrument_response.json()
            if not instrument_data.get('data'):
                continue
                
            instrument = instrument_data['data'][0]
            min_size = float(instrument.get('minSz', '0'))
            
            # Get current price
            price_response = requests.get(f'{base_url}/api/v5/market/ticker?instId={pair}')
            if price_response.status_code != 200:
                continue
                
            price_data = price_response.json()
            if not price_data.get('data'):
                continue
                
            current_price = float(price_data['data'][0]['last'])
            min_order_value = min_size * current_price
            
            print(f"{pair}:")
            print(f"  Current Price: ${current_price:.8f}")
            print(f"  Minimum Size: {min_size}")
            print(f"  Minimum Order Value: ${min_order_value:.4f}")
            
            # Check if we can afford this pair
            if min_order_value <= 0.5:  # Within our available balance
                suitable_pairs.append({
                    'pair': pair,
                    'price': current_price,
                    'min_size': min_size,
                    'min_value': min_order_value
                })
                print(f"  ✓ TRADEABLE with available balance")
            else:
                print(f"  ✗ Requires ${min_order_value:.4f} minimum")
            print()
            
        except Exception as e:
            print(f"Error checking {pair}: {e}")
    
    return suitable_pairs

def execute_micro_trade(pair_info):
    """Execute a micro trade with the most suitable pair"""
    
    api_key = os.getenv('OKX_API_KEY')
    secret_key = os.getenv('OKX_SECRET_KEY') 
    passphrase = os.getenv('OKX_PASSPHRASE')
    base_url = 'https://www.okx.com'
    
    def generate_signature(timestamp, method, request_path, body=''):
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()

    def get_headers(method, request_path, body=''):
        timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
        signature = generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': passphrase,
            'Content-Type': 'application/json'
        }
    
    print(f"Executing live trade for {pair_info['pair']}...")
    
    # Use minimum size for the trade
    order_data = {
        "instId": pair_info['pair'],
        "tdMode": "cash",
        "side": "buy",
        "ordType": "market",
        "sz": str(pair_info['min_size'])
    }
    
    path = '/api/v5/trade/order'
    body = json.dumps(order_data)
    headers = get_headers('POST', path, body)
    
    response = requests.post(base_url + path, headers=headers, data=body)
    result = response.json()
    
    if result.get('code') == '0':
        order_id = result['data'][0]['ordId']
        print(f"FIRST LIVE TRADE EXECUTED SUCCESSFULLY!")
        print(f"Order ID: {order_id}")
        print(f"Symbol: {pair_info['pair']}")
        print(f"Quantity: {pair_info['min_size']}")
        print(f"Estimated Value: ${pair_info['min_value']:.4f}")
        print(f"Price: ${pair_info['price']:.8f}")
        return True
    else:
        print(f"Trade failed: {result}")
        return False

if __name__ == "__main__":
    print("Scanning for tradeable cryptocurrency pairs...")
    print("=" * 50)
    
    suitable_pairs = find_suitable_pairs()
    
    if suitable_pairs:
        print(f"Found {len(suitable_pairs)} suitable pairs for trading:")
        
        # Sort by minimum order value (cheapest first)
        suitable_pairs.sort(key=lambda x: x['min_value'])
        
        for pair in suitable_pairs:
            print(f"  {pair['pair']}: ${pair['min_value']:.4f} minimum")
        
        print("\nAttempting live trade with most affordable pair...")
        best_pair = suitable_pairs[0]
        
        success = execute_micro_trade(best_pair)
        
        if success:
            print("\nAUTONOMOUS TRADING SUCCESSFULLY INITIATED!")
            print("First live trade completed - system now operational")
        else:
            print("\nContinuing in monitoring mode")
            print("System ready for trades when market conditions allow")
    else:
        print("No suitable pairs found within current balance limits")
        print("System continues in advanced monitoring mode")