#!/usr/bin/env python3
"""
Force sell all available BTC to generate USDT for live trading
"""
import os
import time
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime

def force_sell_btc():
    """Sell all available BTC to generate USDT for trading"""
    
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

    print("Force selling all BTC to generate USDT...")
    
    # Check current BTC price
    price_response = requests.get(f'{base_url}/api/v5/market/ticker?instId=BTC-USDT')
    price_data = price_response.json()
    current_price = float(price_data['data'][0]['last'])
    
    # Calculate expected USDT from BTC sale
    btc_amount = 0.00010743
    expected_usdt = btc_amount * current_price
    
    print(f"BTC Price: ${current_price:,.2f}")
    print(f"BTC Amount: {btc_amount}")
    print(f"Expected USDT: ${expected_usdt:.2f}")
    
    # Try selling with smaller precision
    btc_amounts = [
        str(btc_amount),           # Full amount
        "0.0001",                  # Rounded to 4 decimals
        str(int(btc_amount * 100000) / 100000),  # 5 decimal precision
    ]
    
    for amount in btc_amounts:
        try:
            print(f"Attempting to sell {amount} BTC...")
            
            order_data = {
                "instId": "BTC-USDT",
                "tdMode": "cash",
                "side": "sell",
                "ordType": "market",
                "sz": amount
            }
            
            path = '/api/v5/trade/order'
            body = json.dumps(order_data)
            headers = get_headers('POST', path, body)
            
            response = requests.post(base_url + path, headers=headers, data=body)
            result = response.json()
            
            if result.get('code') == '0':
                order_id = result['data'][0]['ordId']
                print(f"BTC SELL ORDER PLACED SUCCESSFULLY!")
                print(f"Order ID: {order_id}")
                print(f"Amount: {amount} BTC")
                
                # Wait for order completion
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
                        print(f"BTC CONVERSION SUCCESSFUL!")
                        print(f"Sold: {filled_sz} BTC")
                        print(f"Price: ${float(avg_px):,.2f}")
                        print(f"USDT Received: ${usdt_received:.2f}")
                        
                        # Now execute a trade with the new USDT
                        time.sleep(2)
                        return execute_trade_with_usdt(usdt_received)
                    else:
                        print(f"Order status: {status}")
                        continue
            else:
                error_msg = result.get('msg', 'Unknown error')
                if 'data' in result and result['data']:
                    error_code = result['data'][0].get('sCode')
                    error_detail = result['data'][0].get('sMsg')
                    print(f"Failed: {error_code} - {error_detail}")
                else:
                    print(f"Failed: {error_msg}")
                    
        except Exception as e:
            print(f"Error with {amount}: {e}")
    
    return False

def execute_trade_with_usdt(usdt_amount):
    """Execute a trade with the received USDT"""
    
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
    
    print(f"Executing live trade with ${usdt_amount:.2f} USDT...")
    
    # Try different trading pairs in order of feasibility
    trade_options = [
        {"pair": "TRX-USDT", "quantity": "3"},
        {"pair": "DOGE-USDT", "quantity": "15"},
        {"pair": "XRP-USDT", "quantity": "2"},
        {"pair": "ADA-USDT", "quantity": "5"},
    ]
    
    for trade in trade_options:
        try:
            # Get current price
            price_response = requests.get(f'{base_url}/api/v5/market/ticker?instId={trade["pair"]}')
            if price_response.status_code == 200:
                price_data = price_response.json()
                if price_data.get('data'):
                    current_price = float(price_data['data'][0]['last'])
                    quantity = float(trade["quantity"])
                    cost = quantity * current_price
                    
                    print(f"Checking {trade['pair']}:")
                    print(f"  Price: ${current_price:.6f}")
                    print(f"  Quantity: {quantity}")
                    print(f"  Cost: ${cost:.2f}")
                    
                    if cost <= usdt_amount * 0.95:  # Use 95% to account for fees
                        print(f"Executing {trade['pair']} purchase...")
                        
                        order_data = {
                            "instId": trade["pair"],
                            "tdMode": "cash",
                            "side": "buy",
                            "ordType": "market",
                            "sz": trade["quantity"]
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
                            print(f"Pair: {trade['pair']}")
                            print(f"Side: BUY")
                            print(f"Quantity: {trade['quantity']}")
                            print(f"Estimated Cost: ${cost:.2f}")
                            
                            return True
                        else:
                            error_msg = result.get('msg', 'Unknown error')
                            if 'data' in result and result['data']:
                                error_code = result['data'][0].get('sCode')
                                error_detail = result['data'][0].get('sMsg')
                                print(f"  Failed: {error_code} - {error_detail}")
                            else:
                                print(f"  Failed: {error_msg}")
                    else:
                        print(f"  Insufficient USDT: ${cost:.2f} > ${usdt_amount:.2f}")
                        
        except Exception as e:
            print(f"Error with {trade['pair']}: {e}")
    
    return False

if __name__ == "__main__":
    print("Converting BTC to USDT and executing first live trade...")
    print("=" * 60)
    
    success = force_sell_btc()
    
    if success:
        print("\nAUTONOMOUS TRADING SUCCESSFULLY INITIATED!")
        print("BTC converted to USDT and first trade executed")
        print("System now operational with live trading capability")
        print("Continuing autonomous 24/7 operation")
    else:
        print("\nConversion attempts completed")
        print("System continues in monitoring mode")