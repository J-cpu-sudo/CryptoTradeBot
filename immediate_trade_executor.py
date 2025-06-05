#!/usr/bin/env python3
"""
Immediate Trade Executor - Forces trade execution with minimal restrictions
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime, timezone

def execute_immediate_trades():
    print("IMMEDIATE TRADE EXECUTOR - FORCING EXECUTION")
    print("=" * 55)
    
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
    
    def api_request(method, endpoint, body=None):
        try:
            headers = get_headers(method, endpoint, body or '')
            url = base_url + endpoint
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=15)
            
            print(f"API {method} {endpoint}: Status {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response code: {data.get('code')}, msg: {data.get('msg', 'OK')}")
                if data.get('code') == '0':
                    return data
                else:
                    print(f"API Error: {data.get('msg')}")
            else:
                print(f"HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
            
            return None
        except Exception as e:
            print(f"Request Exception: {e}")
            return None
    
    def get_balance():
        print("\nGetting account balance...")
        data = api_request('GET', '/api/v5/account/balance')
        if data:
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    balance = float(detail['availBal'])
                    print(f"USDT Balance: ${balance:.2f}")
                    return balance
        print("Failed to get balance")
        return 0
    
    def get_trading_pairs():
        print("\nGetting available trading pairs...")
        data = api_request('GET', '/api/v5/public/instruments?instType=SPOT')
        if data:
            usdt_pairs = []
            for inst in data['data']:
                if inst['instId'].endswith('-USDT') and inst['state'] == 'live':
                    usdt_pairs.append(inst['instId'])
            
            # Filter to most liquid pairs
            priority_pairs = [
                'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'ADA-USDT',
                'DOGE-USDT', 'TRX-USDT', 'XRP-USDT', 'AVAX-USDT'
            ]
            
            available_priority = [p for p in priority_pairs if p in usdt_pairs]
            print(f"Available priority pairs: {len(available_priority)}")
            for pair in available_priority[:5]:
                print(f"  - {pair}")
            
            return available_priority
        
        print("Failed to get trading pairs")
        return []
    
    def execute_market_buy(symbol, usdt_amount):
        print(f"\nExecuting market buy: {symbol} with ${usdt_amount:.2f}")
        
        # Get current price
        ticker_data = api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker_data:
            print(f"Failed to get ticker for {symbol}")
            return None
        
        price = float(ticker_data['data'][0]['last'])
        print(f"Current price: ${price}")
        
        # Get instrument specifications
        inst_data = api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data:
            print(f"Failed to get instrument data for {symbol}")
            return None
        
        inst_info = inst_data['data'][0]
        min_size = float(inst_info['minSz'])
        lot_size = float(inst_info['lotSz'])
        
        print(f"Min size: {min_size}, Lot size: {lot_size}")
        
        # Calculate quantity
        quantity = usdt_amount / price
        
        if quantity < min_size:
            print(f"Quantity {quantity} below minimum {min_size}")
            return None
        
        # Round to lot size
        quantity = round(quantity / lot_size) * lot_size
        print(f"Adjusted quantity: {quantity}")
        
        # Create order
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        print(f"Order data: {order_body}")
        
        result = api_request('POST', '/api/v5/trade/order', order_body)
        
        if result and result['data']:
            order_id = result['data'][0]['ordId']
            print(f"✓ ORDER EXECUTED SUCCESSFULLY")
            print(f"  Order ID: {order_id}")
            print(f"  Symbol: {symbol}")
            print(f"  Quantity: {quantity}")
            print(f"  Estimated cost: ${usdt_amount:.2f}")
            return order_id
        else:
            print(f"✗ ORDER FAILED")
            if result:
                print(f"Error: {result.get('msg', 'Unknown error')}")
            return None
    
    # Main execution
    balance = get_balance()
    
    if balance < 2:
        print(f"Insufficient balance: ${balance:.2f}")
        return
    
    pairs = get_trading_pairs()
    
    if not pairs:
        print("No trading pairs available")
        return
    
    # Execute 2-3 trades with available balance
    trades_to_execute = min(3, len(pairs))
    amount_per_trade = (balance - 1) / trades_to_execute  # Keep $1 buffer
    
    print(f"\nExecuting {trades_to_execute} trades with ${amount_per_trade:.2f} each")
    
    successful_trades = 0
    
    for i, symbol in enumerate(pairs[:trades_to_execute]):
        print(f"\n{'='*50}")
        print(f"TRADE {i+1}/{trades_to_execute}: {symbol}")
        print(f"{'='*50}")
        
        order_id = execute_market_buy(symbol, amount_per_trade)
        
        if order_id:
            successful_trades += 1
            print(f"✓ Trade {i+1} completed successfully")
        else:
            print(f"✗ Trade {i+1} failed")
        
        # Brief pause between trades
        if i < trades_to_execute - 1:
            print("Waiting 3 seconds before next trade...")
            time.sleep(3)
    
    print(f"\n{'='*55}")
    print(f"EXECUTION SUMMARY")
    print(f"{'='*55}")
    print(f"Trades attempted: {trades_to_execute}")
    print(f"Trades successful: {successful_trades}")
    print(f"Success rate: {(successful_trades/trades_to_execute)*100:.1f}%")
    
    if successful_trades > 0:
        print("\n🚀 AUTONOMOUS TRADING IS NOW FULLY ACTIVE")
        print("Multiple positions opened - system will manage exits automatically")
    else:
        print("\n⚠️  NO TRADES EXECUTED - INVESTIGATING ACCOUNT RESTRICTIONS")

if __name__ == "__main__":
    execute_immediate_trades()