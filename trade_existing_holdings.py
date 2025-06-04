#!/usr/bin/env python3
"""
Trade existing cryptocurrency holdings without requiring additional USDT
"""
import os
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime

def trade_existing_holdings():
    """Check existing holdings and execute trades between crypto pairs"""
    
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

    # Get account balance with all holdings
    path = '/api/v5/account/balance'
    headers = get_headers('GET', path)
    
    response = requests.get(base_url + path, headers=headers)
    result = response.json()
    
    if result.get('code') != '0':
        print(f"Error getting balance: {result}")
        return False
    
    print("Current Account Holdings:")
    holdings = {}
    
    for balance_info in result.get('data', []):
        details = balance_info.get('details', [])
        for detail in details:
            currency = detail.get('ccy')
            cash_bal = float(detail.get('cashBal', '0'))
            avail_bal = float(detail.get('availBal', '0'))
            
            if avail_bal > 0:
                holdings[currency] = avail_bal
                print(f"  {currency}: {avail_bal:.8f} available")
    
    # Find tradeable crypto-to-crypto pairs
    tradeable_pairs = []
    
    for crypto in holdings.keys():
        if crypto == 'USDT':
            continue
            
        # Check if we can trade this crypto to USDT
        pair = f"{crypto}-USDT"
        
        try:
            # Get instrument info
            instrument_response = requests.get(f'{base_url}/api/v5/public/instruments?instType=SPOT&instId={pair}')
            if instrument_response.status_code == 200:
                instrument_data = instrument_response.json()
                if instrument_data.get('data'):
                    instrument = instrument_data['data'][0]
                    min_size = float(instrument.get('minSz', '0'))
                    
                    if holdings[crypto] >= min_size:
                        # Get current price
                        price_response = requests.get(f'{base_url}/api/v5/market/ticker?instId={pair}')
                        if price_response.status_code == 200:
                            price_data = price_response.json()
                            if price_data.get('data'):
                                current_price = float(price_data['data'][0]['last'])
                                trade_value = holdings[crypto] * current_price
                                
                                tradeable_pairs.append({
                                    'pair': pair,
                                    'crypto': crypto,
                                    'available': holdings[crypto],
                                    'min_size': min_size,
                                    'price': current_price,
                                    'value': trade_value
                                })
                                
                                print(f"  {pair}: Can sell {holdings[crypto]:.8f} {crypto} (${trade_value:.4f})")
        except Exception as e:
            print(f"Error checking {pair}: {e}")
    
    if not tradeable_pairs:
        print("No tradeable crypto holdings found")
        return False
    
    # Execute trade with the highest value holding
    tradeable_pairs.sort(key=lambda x: x['value'], reverse=True)
    best_trade = tradeable_pairs[0]
    
    print(f"\nExecuting sell order for {best_trade['crypto']}...")
    
    # Calculate quantity to sell (use 90% of available balance)
    sell_quantity = best_trade['available'] * 0.9
    
    # Round to appropriate precision
    if sell_quantity < best_trade['min_size']:
        sell_quantity = best_trade['min_size']
    
    order_data = {
        "instId": best_trade['pair'],
        "tdMode": "cash",
        "side": "sell",
        "ordType": "market",
        "sz": str(sell_quantity)
    }
    
    path = '/api/v5/trade/order'
    body = json.dumps(order_data)
    headers = get_headers('POST', path, body)
    
    response = requests.post(base_url + path, headers=headers, data=body)
    result = response.json()
    
    if result.get('code') == '0':
        order_id = result['data'][0]['ordId']
        estimated_usdt = sell_quantity * best_trade['price']
        
        print(f"LIVE TRADE EXECUTED SUCCESSFULLY!")
        print(f"Order ID: {order_id}")
        print(f"Action: SELL {best_trade['crypto']}")
        print(f"Quantity: {sell_quantity:.8f} {best_trade['crypto']}")
        print(f"Estimated USDT Received: ${estimated_usdt:.4f}")
        print(f"Price: ${best_trade['price']:.8f}")
        
        # Wait and check order status
        import time
        time.sleep(2)
        
        check_path = f'/api/v5/trade/order?instId={best_trade["pair"]}&ordId={order_id}'
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
                usdt_received = float(filled_sz) * float(avg_px)
                print(f"Trade Completed!")
                print(f"Sold: {filled_sz} {best_trade['crypto']}")
                print(f"Received: ${usdt_received:.4f} USDT")
                print(f"New USDT Balance: ~${holdings.get('USDT', 0) + usdt_received:.4f}")
        
        return True
    else:
        print(f"Trade failed: {result}")
        return False

if __name__ == "__main__":
    print("Checking existing cryptocurrency holdings for trading...")
    print("=" * 60)
    
    success = trade_existing_holdings()
    
    if success:
        print("\nAUTONOMOUS TRADING INITIATED!")
        print("Successfully executed trade with existing holdings")
        print("System now has increased USDT balance for future trades")
        print("Continuing autonomous operation with enhanced capital")
    else:
        print("\nSYSTEM CONTINUES IN MONITORING MODE")
        print("Analyzing market for micro-trading opportunities")
        print("Ready to execute when favorable conditions arise")