#!/usr/bin/env python3
"""
Aggressive Micro Trader - Forces trades with minimal balance requirements
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

class AggressiveMicroTrader:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Micro trading parameters
        self.min_trade_size = 1.0  # Minimum $1 trades
        self.profit_target = 0.015  # 1.5% profit target
        self.stop_loss = -0.02      # 2% stop loss
        self.max_hold_time = 180    # 3 minutes max hold
        
        # Micro-cap trading pairs with lower minimums
        self.micro_pairs = [
            'DOGE-USDT', 'TRX-USDT', 'SHIB-USDT', 'PEPE-USDT',
            'FLOKI-USDT', 'BONK-USDT', 'WIF-USDT', 'MEME-USDT'
        ]
        
        self.active_positions = {}
        self.total_trades = 0
        self.profitable_trades = 0
    
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
                response = requests.get(url, headers=headers, timeout=8)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=8)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    return data
            
            return None
        except Exception:
            return None
    
    def get_balance(self) -> float:
        data = self.api_request('GET', '/api/v5/account/balance')
        if data:
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    return float(detail['availBal'])
        return 0.0
    
    def format_quantity(self, quantity: float, lot_size: str) -> str:
        lot_decimal = Decimal(lot_size)
        quantity_decimal = Decimal(str(quantity))
        formatted = quantity_decimal.quantize(lot_decimal, rounding=ROUND_DOWN)
        return str(formatted.normalize())
    
    def get_max_buy_amount(self, symbol: str) -> float:
        data = self.api_request('GET', f'/api/v5/account/max-size?instId={symbol}&tdMode=cash')
        if data and data['data']:
            return float(data['data'][0]['maxBuy'])
        return 0.0
    
    def calculate_micro_signal(self, symbol: str) -> float:
        # Get 1-minute candles for rapid micro signals
        candles = self.api_request('GET', f'/api/v5/market/candles?instId={symbol}&bar=1m&limit=20')
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        
        if not candles or not ticker:
            return 0.0
        
        candle_data = candles['data']
        if len(candle_data) < 10:
            return 0.0
        
        # Extract price data
        closes = np.array([float(c[4]) for c in candle_data])
        volumes = np.array([float(c[5]) for c in candle_data])
        
        signals = []
        
        # 1. Short-term momentum
        if len(closes) >= 5:
            momentum = (closes[-1] / closes[-5] - 1) * 100
            if momentum > 1:
                signals.append(0.4)
            elif momentum > 0.5:
                signals.append(0.25)
            elif momentum < -1:
                signals.append(-0.4)
            elif momentum < -0.5:
                signals.append(-0.25)
            else:
                signals.append(0)
        
        # 2. Volume spike
        if len(volumes) >= 5:
            avg_volume = np.mean(volumes[-5:])
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            if volume_ratio > 2:
                signals.append(0.3)
            elif volume_ratio > 1.5:
                signals.append(0.2)
            elif volume_ratio < 0.5:
                signals.append(-0.1)
            else:
                signals.append(0)
        
        # 3. Price volatility
        if len(closes) >= 10:
            returns = np.diff(closes) / closes[:-1]
            volatility = np.std(returns) * 100
            
            if 1 <= volatility <= 4:
                signals.append(0.2)
            elif volatility > 6:
                signals.append(-0.1)
            else:
                signals.append(0)
        
        # 4. Recent price action
        if len(closes) >= 3:
            recent_trend = (closes[-1] - closes[-3]) / closes[-3] * 100
            if recent_trend > 0.5:
                signals.append(0.15)
            elif recent_trend < -0.5:
                signals.append(-0.15)
            else:
                signals.append(0)
        
        final_signal = sum(signals)
        return max(-1, min(1, final_signal))
    
    def execute_micro_buy(self, symbol: str, usdt_amount: float):
        print(f"Executing micro buy: {symbol} with ${usdt_amount:.2f}")
        
        # Get current price
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker:
            return None
        
        price = float(ticker['data'][0]['last'])
        
        # Get instrument info
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data:
            return None
        
        inst_info = inst_data['data'][0]
        min_size = float(inst_info['minSz'])
        lot_size = inst_info['lotSz']
        
        # Calculate quantity
        raw_quantity = usdt_amount / price
        
        if raw_quantity < min_size:
            print(f"Quantity {raw_quantity:.8f} below minimum {min_size}")
            return None
        
        formatted_quantity = self.format_quantity(raw_quantity, lot_size)
        
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
            
            print(f"BUY SUCCESS: {symbol} - {formatted_quantity} @ ${price:.6f}")
            return order_id
        else:
            if result:
                print(f"BUY FAILED: {symbol} - {result.get('msg')}")
            return None
    
    def execute_micro_sell(self, symbol: str, quantity: float):
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data:
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
            
            print(f"SELL SUCCESS: {symbol} - {formatted_quantity}")
            return order_id
        
        return None
    
    def manage_micro_positions(self):
        current_time = time.time()
        positions_to_close = []
        
        for symbol, position in self.active_positions.items():
            ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
            if not ticker:
                continue
            
            current_price = float(ticker['data'][0]['last'])
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
            hold_time = current_time - position['entry_time']
            
            should_close = False
            reason = ""
            
            if pnl_pct >= self.profit_target:
                should_close = True
                reason = f"profit {pnl_pct*100:.2f}%"
                self.profitable_trades += 1
            
            elif pnl_pct <= self.stop_loss:
                should_close = True
                reason = f"stop loss {pnl_pct*100:.2f}%"
            
            elif hold_time > self.max_hold_time:
                should_close = True
                reason = f"time limit {hold_time/60:.1f}min"
                if pnl_pct > 0:
                    self.profitable_trades += 1
            
            if should_close:
                positions_to_close.append((symbol, position['quantity'], reason))
                self.total_trades += 1
        
        for symbol, quantity, reason in positions_to_close:
            print(f"Closing {symbol}: {reason}")
            self.execute_micro_sell(symbol, quantity)
    
    def run_micro_cycle(self):
        print(f"\n=== MICRO TRADING CYCLE - {datetime.now().strftime('%H:%M:%S')} ===")
        
        balance = self.get_balance()
        win_rate = (self.profitable_trades / max(self.total_trades, 1)) * 100
        
        print(f"Balance: ${balance:.2f} | Positions: {len(self.active_positions)}")
        print(f"Performance: {self.total_trades} trades, {win_rate:.1f}% win rate")
        
        # Position management
        self.manage_micro_positions()
        
        # Look for opportunities
        if balance >= self.min_trade_size and len(self.active_positions) < 3:
            best_signal = 0
            best_symbol = None
            
            for symbol in self.micro_pairs:
                if symbol in self.active_positions:
                    continue
                
                signal = self.calculate_micro_signal(symbol)
                
                if abs(signal) > abs(best_signal) and abs(signal) > 0.4:
                    best_signal = signal
                    best_symbol = symbol
            
            if best_symbol and best_signal > 0:  # Only long positions
                trade_amount = min(balance * 0.8, balance - 0.5)  # Use 80% or leave $0.5 buffer
                
                if trade_amount >= self.min_trade_size:
                    print(f"OPPORTUNITY: {best_symbol} - Signal: {best_signal:.3f}")
                    self.execute_micro_buy(best_symbol, trade_amount)
        
        elif len(self.active_positions) >= 3:
            print("Maximum micro positions reached")
        else:
            print(f"Insufficient balance: ${balance:.2f}")
    
    def run_aggressive_micro_trader(self):
        print("AGGRESSIVE MICRO TRADING SYSTEM")
        print("Minimum balance requirements • Rapid execution • Micro profits")
        print("=" * 60)
        
        while True:
            try:
                self.run_micro_cycle()
                
                # Fast micro trading cycles
                if len(self.active_positions) > 0:
                    wait_time = 10  # Very fast monitoring
                else:
                    wait_time = 20  # Quick opportunity scanning
                
                print(f"Next micro cycle in {wait_time} seconds...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("\nMicro trader stopped")
                break
            except Exception as e:
                print(f"Micro trader error: {e}")
                time.sleep(15)

def main():
    trader = AggressiveMicroTrader()
    trader.run_aggressive_micro_trader()

if __name__ == "__main__":
    main()