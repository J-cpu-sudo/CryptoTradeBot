#!/usr/bin/env python3
"""
Corrected Trading Bot - Fixed API order format and execution
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
import numpy as np
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

class CorrectedTrader:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        self.active_positions = {}
        self.performance = {'total_trades': 0, 'profitable_trades': 0, 'total_pnl': 0.0}
    
    def get_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def create_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        message = timestamp + method + path + body
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(self, method: str, path: str, body: str = '') -> dict:
        timestamp = self.get_timestamp()
        signature = self.create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def api_request(self, method: str, endpoint: str, body: str = None):
        try:
            headers = self.get_headers(method, endpoint, body or '')
            url = self.base_url + endpoint
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data
            
            print(f"HTTP Error {response.status_code}: {response.text}")
            return None
        except Exception as e:
            print(f"Request error: {e}")
            return None
    
    def get_balance(self) -> float:
        data = self.api_request('GET', '/api/v5/account/balance')
        if data and data.get('code') == '0':
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    return float(detail['availBal'])
        return 0.0
    
    def get_instrument_info(self, symbol: str):
        data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if data and data.get('code') == '0' and data['data']:
            return data['data'][0]
        return None
    
    def get_ticker(self, symbol: str):
        data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if data and data.get('code') == '0' and data['data']:
            return data['data'][0]
        return None
    
    def format_quantity(self, quantity: float, lot_size: str) -> str:
        """Format quantity according to lot size precision"""
        lot_decimal = Decimal(lot_size)
        quantity_decimal = Decimal(str(quantity))
        
        # Round down to nearest lot size
        formatted = quantity_decimal.quantize(lot_decimal, rounding=ROUND_DOWN)
        
        # Remove trailing zeros and convert back to string
        return str(formatted.normalize())
    
    def execute_buy_order(self, symbol: str, usdt_amount: float):
        print(f"\nExecuting BUY order: {symbol} with ${usdt_amount:.2f}")
        
        # Get current price
        ticker = self.get_ticker(symbol)
        if not ticker:
            print(f"Failed to get ticker for {symbol}")
            return None
        
        price = float(ticker['last'])
        print(f"Current price: ${price}")
        
        # Get instrument info
        inst_info = self.get_instrument_info(symbol)
        if not inst_info:
            print(f"Failed to get instrument info for {symbol}")
            return None
        
        min_size = float(inst_info['minSz'])
        lot_size = inst_info['lotSz']
        
        print(f"Min size: {min_size}, Lot size: {lot_size}")
        
        # Calculate quantity
        raw_quantity = usdt_amount / price
        
        if raw_quantity < min_size:
            print(f"Quantity {raw_quantity:.8f} below minimum {min_size}")
            return None
        
        # Format quantity with proper precision
        formatted_quantity = self.format_quantity(raw_quantity, lot_size)
        
        print(f"Raw quantity: {raw_quantity:.8f}")
        print(f"Formatted quantity: {formatted_quantity}")
        
        # Create order with corrected format
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": formatted_quantity
        }
        
        order_body = json.dumps(order_data)
        print(f"Order payload: {order_body}")
        
        # Execute order
        result = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if result:
            print(f"API Response: {result}")
            
            if result.get('code') == '0' and result.get('data'):
                order_id = result['data'][0]['ordId']
                print(f"✓ ORDER SUCCESSFUL - ID: {order_id}")
                
                # Track position
                self.active_positions[symbol] = {
                    'quantity': float(formatted_quantity),
                    'entry_price': price,
                    'entry_time': time.time(),
                    'order_id': order_id,
                    'invested': usdt_amount
                }
                
                return order_id
            else:
                print(f"✗ ORDER FAILED - Code: {result.get('code')}, Message: {result.get('msg')}")
                if result.get('data'):
                    for item in result['data']:
                        print(f"Error details: {item}")
        else:
            print("✗ No response from API")
        
        return None
    
    def execute_sell_order(self, symbol: str, quantity: float):
        print(f"\nExecuting SELL order: {symbol} - {quantity}")
        
        # Get instrument info for formatting
        inst_info = self.get_instrument_info(symbol)
        if not inst_info:
            print(f"Failed to get instrument info for {symbol}")
            return None
        
        lot_size = inst_info['lotSz']
        formatted_quantity = self.format_quantity(quantity, lot_size)
        
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "sell",
            "ordType": "market",
            "sz": formatted_quantity
        }
        
        order_body = json.dumps(order_data)
        result = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if result and result.get('code') == '0' and result.get('data'):
            order_id = result['data'][0]['ordId']
            print(f"✓ SELL SUCCESSFUL - ID: {order_id}")
            
            # Remove from positions
            if symbol in self.active_positions:
                del self.active_positions[symbol]
            
            return order_id
        else:
            print(f"✗ SELL FAILED - {result.get('msg') if result else 'No response'}")
        
        return None
    
    def manage_positions(self):
        current_time = time.time()
        positions_to_close = []
        
        for symbol, position in self.active_positions.items():
            ticker = self.get_ticker(symbol)
            if not ticker:
                continue
            
            current_price = float(ticker['last'])
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
            hold_time = current_time - position['entry_time']
            
            should_close = False
            reason = ""
            
            # Profit target: 2%
            if pnl_pct >= 0.02:
                should_close = True
                reason = f"profit target {pnl_pct*100:.2f}%"
                self.performance['profitable_trades'] += 1
            
            # Stop loss: -2.5%
            elif pnl_pct <= -0.025:
                should_close = True
                reason = f"stop loss {pnl_pct*100:.2f}%"
            
            # Time limit: 4 minutes
            elif hold_time > 240:
                should_close = True
                reason = f"time limit {hold_time/60:.1f}min"
                if pnl_pct > 0:
                    self.performance['profitable_trades'] += 1
            
            if should_close:
                positions_to_close.append((symbol, position['quantity'], reason, pnl_pct))
                self.performance['total_trades'] += 1
                self.performance['total_pnl'] += pnl_pct * position['invested']
        
        # Execute closures
        for symbol, quantity, reason, pnl_pct in positions_to_close:
            print(f"Closing {symbol}: {reason} (P&L: {pnl_pct*100:.2f}%)")
            self.execute_sell_order(symbol, quantity)
    
    def test_trade_execution(self):
        print("CORRECTED TRADER - TESTING EXECUTION")
        print("=" * 50)
        
        balance = self.get_balance()
        print(f"Current balance: ${balance:.2f}")
        
        if balance < 5:
            print("Insufficient balance for testing")
            return
        
        # Test with smaller, safer amounts
        test_symbols = ['TRX-USDT', 'ADA-USDT', 'DOGE-USDT']
        test_amount = min(3.0, balance * 0.25)  # Use 25% or $3, whichever is smaller
        
        for symbol in test_symbols:
            print(f"\n{'='*60}")
            print(f"TESTING: {symbol} with ${test_amount:.2f}")
            print(f"{'='*60}")
            
            order_id = self.execute_buy_order(symbol, test_amount)
            
            if order_id:
                print(f"✓ Test trade successful for {symbol}")
                time.sleep(5)  # Wait 5 seconds then sell
                
                if symbol in self.active_positions:
                    quantity = self.active_positions[symbol]['quantity']
                    self.execute_sell_order(symbol, quantity)
                
                break  # Stop after first successful trade
            else:
                print(f"✗ Test trade failed for {symbol}")
        
        # Show final status
        print(f"\n{'='*50}")
        print("TEST COMPLETE")
        print(f"Balance: ${self.get_balance():.2f}")
        print(f"Active positions: {len(self.active_positions)}")
        
        if self.performance['total_trades'] > 0:
            win_rate = (self.performance['profitable_trades'] / self.performance['total_trades']) * 100
            print(f"Performance: {self.performance['total_trades']} trades, {win_rate:.1f}% win rate")

def main():
    trader = CorrectedTrader()
    trader.test_trade_execution()

if __name__ == "__main__":
    main()