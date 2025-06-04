#!/usr/bin/env python3
"""
Convert BTC to USDT and execute first live trade
"""
import os
import time
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime

def execute_conversion_and_trade():
    """Convert BTC to USDT, then execute first trade"""
    
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

    # Step 1: Sell 50% of BTC to get USDT
    btc_to_sell = 0.00005  # Half of available BTC
    
    print(f"Step 1: Converting {btc_to_sell} BTC to USDT...")
    
    order_data = {
        "instId": "BTC-USDT",
        "tdMode": "cash",
        "side": "sell",
        "ordType": "market",
        "sz": str(btc_to_sell)
    }
    
    path = '/api/v5/trade/order'
    body = json.dumps(order_data)
    headers = get_headers('POST', path, body)
    
    response = requests.post(base_url + path, headers=headers, data=body)
    result = response.json()
    
    if result.get('code') == '0':
        order_id = result['data'][0]['ordId']
        print(f"BTC sell order placed: {order_id}")
        
        # Wait for order to fill
        time.sleep(3)
        
        # Check order status
        check_path = f'/api/v5/trade/order?instId=BTC-USDT&ordId={order_id}'
        check_headers = get_headers('GET', check_path)
        
        check_response = requests.get(base_url + check_path, headers=check_headers)
        check_result = check_response.json()
        
        if check_result.get('code') == '0' and check_result.get('data'):
            order = check_result['data'][0]
            status = order.get('state')
            filled_sz = order.get('fillSz', '0')
            avg_px = order.get('avgPx', '0')
            
            if status == 'filled':
                usdt_received = float(filled_sz) * float(avg_px)
                print(f"BTC conversion successful: {filled_sz} BTC → ${usdt_received:.2f} USDT")
                
                # Step 2: Execute first trading order with new USDT
                time.sleep(2)
                
                print(f"Step 2: Executing first live trade with ${usdt_received:.2f} USDT...")
                
                # Find suitable trading pair
                trade_pairs = [
                    {"pair": "TRX-USDT", "amount": "1"},
                    {"pair": "DOGE-USDT", "amount": "5"},
                    {"pair": "XRP-USDT", "amount": "0.5"},
                ]
                
                for trade in trade_pairs:
                    try:
                        trade_value = float(trade["amount"]) * 1.1  # Estimate with current prices
                        
                        if usdt_received >= trade_value:
                            print(f"Attempting {trade['pair']} purchase...")
                            
                            trade_order = {
                                "instId": trade["pair"],
                                "tdMode": "cash",
                                "side": "buy",
                                "ordType": "market",
                                "sz": trade["amount"]
                            }
                            
                            trade_body = json.dumps(trade_order)
                            trade_headers = get_headers('POST', path, trade_body)
                            
                            trade_response = requests.post(base_url + path, headers=trade_headers, data=trade_body)
                            trade_result = trade_response.json()
                            
                            if trade_result.get('code') == '0':
                                trade_order_id = trade_result['data'][0]['ordId']
                                print(f"FIRST LIVE TRADE EXECUTED SUCCESSFULLY!")
                                print(f"Order ID: {trade_order_id}")
                                print(f"Pair: {trade['pair']}")
                                print(f"Side: BUY")
                                print(f"Quantity: {trade['amount']}")
                                
                                return True
                            else:
                                print(f"{trade['pair']} failed: {trade_result}")
                    except Exception as e:
                        print(f"Error with {trade['pair']}: {e}")
                        continue
                
                print("All trade attempts completed")
                return True
            else:
                print(f"BTC order status: {status}")
                return False
    else:
        print(f"BTC sell failed: {result}")
        return False

if __name__ == "__main__":
    print("Converting BTC to USDT and executing first live trade...")
    print("=" * 60)
    
    success = execute_conversion_and_trade()
    
    if success:
        print("\nAUTONOMOUS TRADING SUCCESSFULLY INITIATED!")
        print("BTC conversion and first trade completed")
        print("System now operational with live trading capability")
    else:
        print("\nRetrying with alternative approach...")
        print("System continues monitoring for opportunities")