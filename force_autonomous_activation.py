#!/usr/bin/env python3
"""
Force Autonomous Trading Activation - Execute immediate trade to activate the autonomous system
"""
import os
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone

def force_autonomous_trade():
    """Force an immediate autonomous trade to activate the system"""
    api_key = os.environ.get('OKX_API_KEY')
    secret_key = os.environ.get('OKX_SECRET_KEY')
    passphrase = os.environ.get('OKX_PASSPHRASE')
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
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        signature = generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': passphrase,
            'Content-Type': 'application/json'
        }
    
    print("🚀 FORCING AUTONOMOUS TRADE ACTIVATION")
    print("=" * 50)
    
    # Get current balance
    try:
        path = '/api/v5/account/balance'
        headers = get_headers('GET', path)
        response = requests.get(base_url + path, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == '0':
                usdt_balance = 0.0
                for detail in data['data'][0]['details']:
                    if detail['ccy'] == 'USDT':
                        usdt_balance = float(detail['availBal'])
                        break
                
                print(f"Current USDT Balance: ${usdt_balance:.2f}")
                
                if usdt_balance >= 1.0:
                    # Force trade with DOGE-USDT (lowest minimum requirements)
                    symbol = 'DOGE-USDT'
                    
                    # Get current DOGE price
                    price_response = requests.get(f'{base_url}/api/v5/market/ticker?instId={symbol}', timeout=10)
                    if price_response.status_code == 200:
                        price_data = price_response.json()
                        if price_data.get('data'):
                            current_price = float(price_data['data'][0]['last'])
                            print(f"Current {symbol} Price: ${current_price:.6f}")
                            
                            # Calculate maximum possible trade
                            trade_amount = min(usdt_balance * 0.9, 5.0)  # Use 90% or max $5
                            quantity = trade_amount / current_price
                            
                            # Get instrument specs to adjust quantity
                            inst_response = requests.get(f'{base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}', timeout=10)
                            if inst_response.status_code == 200:
                                inst_data = inst_response.json()
                                if inst_data.get('data'):
                                    instrument = inst_data['data'][0]
                                    min_size = float(instrument.get('minSz', '0'))
                                    lot_size = float(instrument.get('lotSz', '0'))
                                    
                                    if lot_size > 0:
                                        quantity = int(quantity / lot_size) * lot_size
                                    
                                    print(f"Calculated Quantity: {quantity:.2f} DOGE")
                                    print(f"Minimum Required: {min_size:.2f} DOGE")
                                    print(f"Trade Value: ${quantity * current_price:.2f}")
                                    
                                    if quantity >= min_size:
                                        # Execute the trade
                                        order_data = {
                                            "instId": symbol,
                                            "tdMode": "cash",
                                            "side": "buy",
                                            "ordType": "market",
                                            "sz": str(quantity)
                                        }
                                        
                                        path = '/api/v5/trade/order'
                                        body = json.dumps(order_data)
                                        headers = get_headers('POST', path, body)
                                        
                                        print("\n🔥 EXECUTING FORCED AUTONOMOUS TRADE...")
                                        trade_response = requests.post(base_url + path, headers=headers, data=body, timeout=10)
                                        
                                        if trade_response.status_code == 200:
                                            result = trade_response.json()
                                            if result.get('code') == '0':
                                                order_id = result['data'][0]['ordId']
                                                print("\n" + "=" * 60)
                                                print("✅ AUTONOMOUS TRADE SUCCESSFULLY EXECUTED!")
                                                print(f"Order ID: {order_id}")
                                                print(f"Symbol: {symbol}")
                                                print(f"Quantity: {quantity:.2f} DOGE")
                                                print(f"Price: ${current_price:.6f}")
                                                print(f"Total Value: ${quantity * current_price:.2f}")
                                                print(f"Execution Time: {datetime.now().strftime('%H:%M:%S UTC')}")
                                                print("🔄 AUTONOMOUS SYSTEM NOW ACTIVATED!")
                                                print("=" * 60)
                                                return True
                                            else:
                                                print(f"❌ Trade Failed: {result.get('msg', 'Unknown error')}")
                                                print(f"Error Code: {result.get('code')}")
                                        else:
                                            print(f"❌ HTTP Error: {trade_response.status_code}")
                                            try:
                                                error_data = trade_response.json()
                                                print(f"Error Details: {error_data}")
                                            except:
                                                print(f"Raw Response: {trade_response.text}")
                                    else:
                                        print(f"❌ Insufficient quantity. Need at least {min_size:.2f} DOGE")
                                        print(f"Current calculation: {quantity:.2f} DOGE")
                else:
                    print(f"❌ Insufficient balance. Need at least $1.00 USDT")
                    print(f"Current balance: ${usdt_balance:.2f}")
            else:
                print(f"❌ API Error: {data.get('msg', 'Unknown error')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Execution Error: {e}")
    
    return False

if __name__ == "__main__":
    force_autonomous_trade()