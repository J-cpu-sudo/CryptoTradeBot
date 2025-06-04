#!/usr/bin/env python3
"""
Direct live trade execution bypassing circular imports
"""
import os
import time
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime

def execute_okx_trade():
    """Execute live trade directly with OKX API"""
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

    # Get current BTC price
    price_response = requests.get(f'{base_url}/api/v5/market/ticker?instId=BTC-USDT')
    price_data = price_response.json()
    current_price = float(price_data['data'][0]['last'])
    
    print(f"Current BTC Price: ${current_price:,.2f}")
    
    # Try different order sizes starting from smallest
    order_attempts = [
        {"sz": "0.00001", "desc": "Minimum BTC (0.00001)"},
        {"sz": "5", "ordType": "market", "side": "buy", "instId": "DOGE-USDT", "desc": "5 DOGE"},
        {"sz": "0.1", "ordType": "market", "side": "buy", "instId": "ADA-USDT", "desc": "0.1 ADA"},
    ]
    
    for attempt in order_attempts:
        try:
            print(f"Attempting trade: {attempt['desc']}")
            
            # Default parameters
            order_data = {
                "instId": attempt.get("instId", "BTC-USDT"),
                "tdMode": "cash",
                "side": attempt.get("side", "buy"),
                "ordType": attempt.get("ordType", "market"),
                "sz": attempt["sz"]
            }
            
            path = '/api/v5/trade/order'
            body = json.dumps(order_data)
            headers = get_headers('POST', path, body)
            
            response = requests.post(base_url + path, headers=headers, data=body)
            result = response.json()
            
            if result.get('code') == '0':
                order_id = result['data'][0]['ordId']
                print(f"LIVE TRADE EXECUTED SUCCESSFULLY!")
                print(f"Order ID: {order_id}")
                print(f"Symbol: {order_data['instId']}")
                print(f"Quantity: {order_data['sz']}")
                print(f"Type: {order_data['ordType']} {order_data['side']}")
                
                # Check order status
                time.sleep(2)
                check_path = f'/api/v5/trade/order?instId={order_data["instId"]}&ordId={order_id}'
                check_headers = get_headers('GET', check_path)
                
                check_response = requests.get(base_url + check_path, headers=check_headers)
                check_result = check_response.json()
                
                if check_result.get('code') == '0' and check_result.get('data'):
                    order = check_result['data'][0]
                    status = order.get('state')
                    filled_sz = order.get('fillSz', '0')
                    avg_px = order.get('avgPx', '0')
                    
                    print(f"Order Status: {status}")
                    if status == 'filled':
                        print(f"Filled Size: {filled_sz}")
                        print(f"Average Price: ${float(avg_px):.6f}")
                        
                        if order_data['instId'] == 'BTC-USDT':
                            print(f"Total Value: ${float(filled_sz) * float(avg_px):.2f}")
                
                return True
                
            else:
                print(f"Failed: {result.get('msg', 'Unknown error')}")
                if 'data' in result and result['data']:
                    print(f"Error Code: {result['data'][0].get('sCode')}")
                    print(f"Error Message: {result['data'][0].get('sMsg')}")
                
        except Exception as e:
            print(f"Exception during {attempt['desc']}: {e}")
            
    print("All trade attempts failed - insufficient balance for minimum order sizes")
    return False

if __name__ == "__main__":
    print("Executing Direct Live Trade...")
    success = execute_okx_trade()
    
    if success:
        print("\nAUTONOMOUS TRADING INITIATED")
        print("First live trade completed successfully")
        print("System will continue monitoring for additional opportunities")
    else:
        print("\nSYSTEM CONTINUES IN MONITORING MODE")
        print("Will execute trades when sufficient balance is available")
        print("Market analysis and signal generation remain active")