#!/usr/bin/env python3
"""
Force execute micro trade with available USDT using smallest possible amounts
"""
import os
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime

def force_micro_trade():
    """Execute smallest possible trade with available USDT"""
    
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

    # Try micro amounts for cheapest tokens
    micro_trades = [
        {"pair": "PEPE-USDT", "usdt_amount": "0.5"},
        {"pair": "SHIB-USDT", "usdt_amount": "0.5"},
        {"pair": "FLOKI-USDT", "usdt_amount": "0.4"},
        {"pair": "DOGE-USDT", "usdt_amount": "0.3"},
        {"pair": "TRX-USDT", "usdt_amount": "0.2"},
    ]
    
    for trade in micro_trades:
        try:
            print(f"Attempting {trade['pair']} with ${trade['usdt_amount']} USDT...")
            
            # Get current price
            price_response = requests.get(f'{base_url}/api/v5/market/ticker?instId={trade["pair"]}')
            if price_response.status_code == 200:
                price_data = price_response.json()
                if price_data.get('data'):
                    current_price = float(price_data['data'][0]['last'])
                    
                    # Calculate quantity to buy
                    usdt_amount = float(trade['usdt_amount'])
                    quantity = usdt_amount / current_price
                    
                    # Get instrument info for minimum size
                    instrument_response = requests.get(f'{base_url}/api/v5/public/instruments?instType=SPOT&instId={trade["pair"]}')
                    if instrument_response.status_code == 200:
                        instrument_data = instrument_response.json()
                        if instrument_data.get('data'):
                            instrument = instrument_data['data'][0]
                            min_size = float(instrument.get('minSz', '0'))
                            lot_size = float(instrument.get('lotSz', '0'))
                            
                            # Round quantity to lot size
                            if lot_size > 0:
                                quantity = round(quantity / lot_size) * lot_size
                            
                            # Ensure minimum size
                            if quantity >= min_size:
                                print(f"  Price: ${current_price:.8f}")
                                print(f"  Quantity: {quantity}")
                                print(f"  Min size: {min_size}")
                                
                                # Place order by quantity (not USDT amount)
                                order_data = {
                                    "instId": trade["pair"],
                                    "tdMode": "cash",
                                    "side": "buy",
                                    "ordType": "market",
                                    "sz": str(quantity)
                                }
                                
                                path = '/api/v5/trade/order'
                                body = json.dumps(order_data)
                                headers = get_headers('POST', path, body)
                                
                                response = requests.post(base_url + path, headers=headers, data=body)
                                result = response.json()
                                
                                if result.get('code') == '0':
                                    order_id = result['data'][0]['ordId']
                                    print(f"SUCCESS: FIRST LIVE TRADE EXECUTED!")
                                    print(f"Order ID: {order_id}")
                                    print(f"Pair: {trade['pair']}")
                                    print(f"Side: BUY")
                                    print(f"Quantity: {quantity}")
                                    print(f"Estimated Cost: ${quantity * current_price:.4f}")
                                    
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
                                print(f"  Insufficient quantity: {quantity} < {min_size}")
        except Exception as e:
            print(f"  Error: {e}")
    
    print("All micro trade attempts completed")
    return False

if __name__ == "__main__":
    print("Forcing micro trade execution with available USDT...")
    print("=" * 50)
    
    success = force_micro_trade()
    
    if success:
        print("\nAUTONOMOUS TRADING INITIATED!")
        print("First live trade successfully executed")
        print("System now operational for continuous trading")
    else:
        print("\nMicro trade attempts complete")
        print("System continues advanced market monitoring")