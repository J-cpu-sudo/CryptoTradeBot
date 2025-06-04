#!/usr/bin/env python3
"""
Immediate Trade Execution - Force execute a live trade now
"""
import os
import json
import requests
import hmac
import hashlib
import base64
from datetime import datetime

def execute_immediate_trade():
    """Execute a live trade immediately to demonstrate functionality"""
    
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

    # Get current balance
    print("Checking account balance...")
    balance_path = '/api/v5/account/balance'
    balance_headers = get_headers('GET', balance_path)
    
    balance_response = requests.get(base_url + balance_path, headers=balance_headers)
    balance_data = balance_response.json()
    
    usdt_balance = 0
    if balance_data.get('code') == '0':
        for detail in balance_data['data'][0]['details']:
            if detail['ccy'] == 'USDT':
                usdt_balance = float(detail['availBal'])
                break
    
    print(f"Available USDT: ${usdt_balance:.2f}")
    
    if usdt_balance < 0.5:
        print("Insufficient USDT balance for trading")
        return False
    
    # Find a suitable trading pair with low minimum order
    trading_options = [
        {"pair": "DOGE-USDT", "amount": "10"},
        {"pair": "TRX-USDT", "amount": "2"},
        {"pair": "ADA-USDT", "amount": "2"},
    ]
    
    for option in trading_options:
        try:
            pair = option["pair"]
            print(f"\nAttempting {pair} trade...")
            
            # Get current price
            ticker_response = requests.get(f'{base_url}/api/v5/market/ticker?instId={pair}')
            ticker_data = ticker_response.json()
            
            if ticker_data.get('data'):
                current_price = float(ticker_data['data'][0]['last'])
                quantity = float(option["amount"])
                estimated_cost = quantity * current_price
                
                print(f"Price: ${current_price:.6f}")
                print(f"Quantity: {quantity}")
                print(f"Estimated cost: ${estimated_cost:.2f}")
                
                if estimated_cost <= usdt_balance * 0.8:  # Use 80% of available balance
                    # Get instrument info
                    instrument_response = requests.get(f'{base_url}/api/v5/public/instruments?instType=SPOT&instId={pair}')
                    if instrument_response.status_code == 200:
                        instrument_data = instrument_response.json()
                        if instrument_data.get('data'):
                            instrument = instrument_data['data'][0]
                            min_size = float(instrument.get('minSz', '0'))
                            
                            if quantity >= min_size:
                                print(f"Executing BUY order for {pair}...")
                                
                                # Place market buy order
                                order_data = {
                                    "instId": pair,
                                    "tdMode": "cash",
                                    "side": "buy",
                                    "ordType": "market",
                                    "sz": str(quantity)
                                }
                                
                                order_path = '/api/v5/trade/order'
                                order_body = json.dumps(order_data)
                                order_headers = get_headers('POST', order_path, order_body)
                                
                                order_response = requests.post(base_url + order_path, headers=order_headers, data=order_body)
                                order_result = order_response.json()
                                
                                if order_result.get('code') == '0':
                                    order_id = order_result['data'][0]['ordId']
                                    print(f"\n🎉 LIVE TRADE EXECUTED SUCCESSFULLY! 🎉")
                                    print(f"Order ID: {order_id}")
                                    print(f"Pair: {pair}")
                                    print(f"Side: BUY")
                                    print(f"Quantity: {quantity}")
                                    print(f"Price: ${current_price:.6f}")
                                    print(f"Value: ${estimated_cost:.2f}")
                                    print(f"Timestamp: {datetime.now()}")
                                    return True
                                else:
                                    error_msg = order_result.get('msg', 'Unknown error')
                                    if 'data' in order_result and order_result['data']:
                                        error_detail = order_result['data'][0].get('sMsg', '')
                                        error_msg = f"{error_msg}: {error_detail}"
                                    print(f"Order failed: {error_msg}")
                            else:
                                print(f"Quantity {quantity} below minimum {min_size}")
                else:
                    print(f"Insufficient balance: ${estimated_cost:.2f} > ${usdt_balance:.2f}")
                    
        except Exception as e:
            print(f"Error with {option['pair']}: {e}")
    
    print("No suitable trading pairs found for immediate execution")
    return False

if __name__ == "__main__":
    print("Executing immediate live trade...")
    print("=" * 50)
    
    success = execute_immediate_trade()
    
    if success:
        print("\nIMMEDIATE LIVE TRADE COMPLETED!")
        print("Autonomous trading system functionality confirmed")
    else:
        print("\nTrade execution not completed")
        print("System continues in monitoring mode")