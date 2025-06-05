#!/usr/bin/env python3
"""
Ultra Micro Trader - Executes trades with ANY available balance
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

class UltraMicroTrader:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Ultra micro parameters
        self.min_signal = 0.1  # Accept weak signals
        self.profit_target = 0.008  # 0.8% profit
        self.stop_loss = -0.015     # 1.5% stop
        self.max_hold_time = 120    # 2 minutes
        
        # Known working pairs with proven execution
        self.working_pairs = ['TRX-USDT', 'DOGE-USDT', 'SHIB-USDT', 'PEPE-USDT']
        
        self.active_positions = {}
        self.trades_executed = 0
        
        print("ULTRA MICRO TRADER - MAXIMUM AGGRESSION")
    
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
                response = requests.get(url, headers=headers, timeout=5)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            
            return None
        except Exception:
            return None
    
    def get_balance(self) -> float:
        data = self.api_request('GET', '/api/v5/account/balance')
        if data and data.get('code') == '0':
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    return float(detail['availBal'])
        return 0.0
    
    def format_quantity(self, quantity: float, lot_size: str) -> str:
        lot_decimal = Decimal(lot_size)
        quantity_decimal = Decimal(str(quantity))
        formatted = quantity_decimal.quantize(lot_decimal, rounding=ROUND_DOWN)
        return str(formatted.normalize())
    
    def get_quick_signal(self, symbol: str) -> float:
        """Quick signal based on recent price movement"""
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker or ticker.get('code') != '0':
            return 0.0
        
        data = ticker['data'][0]
        current_price = float(data['last'])
        change_24h = float(data['sodUtc8'])
        
        # Simple momentum signal
        if change_24h > 1:
            return 0.6  # Strong positive
        elif change_24h > 0.5:
            return 0.4  # Moderate positive
        elif change_24h > 0:
            return 0.2  # Weak positive
        elif change_24h > -1:
            return 0.1  # Neutral/slight negative
        else:
            return 0.0  # Negative
    
    def execute_ultra_micro_buy(self, symbol: str, usdt_amount: float):
        print(f"ULTRA BUY: {symbol} with ${usdt_amount:.3f}")
        
        # Get current price
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker or ticker.get('code') != '0':
            print(f"Failed to get ticker for {symbol}")
            return None
        
        price = float(ticker['data'][0]['last'])
        
        # Get instrument specs
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data or inst_data.get('code') != '0':
            print(f"Failed to get instrument data for {symbol}")
            return None
        
        inst_info = inst_data['data'][0]
        min_size = float(inst_info['minSz'])
        lot_size = inst_info['lotSz']
        
        # Calculate quantity
        raw_quantity = usdt_amount / price
        
        if raw_quantity < min_size:
            print(f"Quantity {raw_quantity:.8f} below min {min_size} for {symbol}")
            return None
        
        formatted_quantity = self.format_quantity(raw_quantity, lot_size)
        
        # Execute order using proven format
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": formatted_quantity
        }
        
        order_body = json.dumps(order_data)
        result = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if result and result.get('code') == '0' and result.get('data'):
            order_id = result['data'][0]['ordId']
            
            self.active_positions[symbol] = {
                'quantity': float(formatted_quantity),
                'entry_price': price,
                'entry_time': time.time(),
                'order_id': order_id,
                'invested': usdt_amount
            }
            
            self.trades_executed += 1
            print(f"✓ BUY SUCCESS: {symbol} - {formatted_quantity} @ ${price:.6f} (Order: {order_id})")
            return order_id
        else:
            error_msg = result.get('msg', 'Unknown error') if result else 'Request failed'
            print(f"✗ BUY FAILED: {symbol} - {error_msg}")
            return None
    
    def execute_ultra_micro_sell(self, symbol: str, quantity: float):
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data or inst_data.get('code') != '0':
            return None
        
        lot_size = inst_data['data'][0]['lotSz']
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
            
            if symbol in self.active_positions:
                del self.active_positions[symbol]
            
            print(f"✓ SELL SUCCESS: {symbol} - {formatted_quantity} (Order: {order_id})")
            return order_id
        else:
            error_msg = result.get('msg', 'Unknown error') if result else 'Request failed'
            print(f"✗ SELL FAILED: {symbol} - {error_msg}")
            return None
    
    def manage_positions(self):
        current_time = time.time()
        positions_to_close = []
        
        for symbol, position in self.active_positions.items():
            ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
            if not ticker or ticker.get('code') != '0':
                continue
            
            current_price = float(ticker['data'][0]['last'])
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
            hold_time = current_time - position['entry_time']
            
            should_close = False
            reason = ""
            
            if pnl_pct >= self.profit_target:
                should_close = True
                reason = f"PROFIT {pnl_pct*100:.2f}%"
            elif pnl_pct <= self.stop_loss:
                should_close = True
                reason = f"STOP {pnl_pct*100:.2f}%"
            elif hold_time > self.max_hold_time:
                should_close = True
                reason = f"TIME {hold_time/60:.1f}min"
            
            if should_close:
                positions_to_close.append((symbol, position['quantity'], reason))
        
        for symbol, quantity, reason in positions_to_close:
            print(f"CLOSING {symbol}: {reason}")
            self.execute_ultra_micro_sell(symbol, quantity)
    
    def run_ultra_cycle(self):
        cycle_time = datetime.now().strftime('%H:%M:%S')
        print(f"\n=== ULTRA CYCLE - {cycle_time} ===")
        
        balance = self.get_balance()
        print(f"Balance: ${balance:.3f} | Positions: {len(self.active_positions)} | Trades: {self.trades_executed}")
        
        # Manage existing positions
        self.manage_positions()
        
        # Try to open new position if balance allows
        if balance >= 1.0 and len(self.active_positions) == 0:
            # Find best signal from working pairs
            best_signal = 0
            best_symbol = None
            
            for symbol in self.working_pairs:
                signal = self.get_quick_signal(symbol)
                if signal > best_signal and signal >= self.min_signal:
                    best_signal = signal
                    best_symbol = symbol
            
            if best_symbol:
                # Use most of available balance
                trade_amount = min(balance * 0.9, balance - 0.1)  # Leave small buffer
                print(f"SIGNAL: {best_symbol} - {best_signal:.2f} | Trading ${trade_amount:.3f}")
                self.execute_ultra_micro_buy(best_symbol, trade_amount)
            else:
                print("No qualifying signals found")
        elif balance < 1.0:
            print(f"Balance too low: ${balance:.3f}")
        else:
            print("Position already active")
    
    def run_ultra_trader(self):
        print("ULTRA MICRO AUTONOMOUS TRADER")
        print("Executes with any available balance • Maximum aggression")
        print("=" * 50)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                self.run_ultra_cycle()
                
                # Fast cycles for ultra trading
                wait_time = 8 if len(self.active_positions) > 0 else 15
                print(f"Next ultra cycle in {wait_time} seconds...\n")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("Ultra trader stopped")
                break
            except Exception as e:
                print(f"Ultra trader error: {e}")
                time.sleep(10)

def main():
    trader = UltraMicroTrader()
    trader.run_ultra_trader()

if __name__ == "__main__":
    main()