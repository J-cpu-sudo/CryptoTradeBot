#!/usr/bin/env python3
"""
Live Autonomous Trading Bot - Actually executes trades
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

class LiveTrader:
    def __init__(self):
        self.api_key = os.environ.get('OKX_API_KEY')
        self.secret_key = os.environ.get('OKX_SECRET_KEY')
        self.passphrase = os.environ.get('OKX_PASSPHRASE')
        
        # Trading configuration
        self.profit_target = 0.008  # 0.8% profit target
        self.stop_loss = -0.012     # 1.2% stop loss
        self.max_hold_time = 120    # 2 minutes max hold
        
        self.symbols = ['TRX-USDT', 'DOGE-USDT', 'SHIB-USDT']
        self.position = None
        self.trades_count = 0
        self.profit_count = 0
        self.total_pnl = 0.0
        
        print("LIVE TRADER STARTING")
        print(f"Target: {self.profit_target*100:.1f}% | Stop: {self.stop_loss*100:.1f}%")
    
    def timestamp(self):
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def sign(self, timestamp, method, path, body=''):
        message = timestamp + method + path + body
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode()
    
    def request(self, method, endpoint, body=None):
        ts = self.timestamp()
        signature = self.sign(ts, method, endpoint, body or '')
        
        headers = {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': ts,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
        
        url = f'https://www.okx.com{endpoint}'
        
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, timeout=10)
            else:
                resp = requests.post(url, headers=headers, data=body, timeout=10)
                
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == '0':
                    return data
            return None
        except:
            return None
    
    def get_usdt_balance(self):
        data = self.request('GET', '/api/v5/account/balance')
        if data:
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    return float(detail['availBal'])
        return 0.0
    
    def get_price(self, symbol):
        data = self.request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if data:
            return float(data['data'][0]['last'])
        return None
    
    def format_size(self, quantity, lot_size):
        lot_decimal = Decimal(lot_size)
        qty_decimal = Decimal(str(quantity))
        return str(qty_decimal.quantize(lot_decimal, rounding=ROUND_DOWN))
    
    def calculate_signal_strength(self, symbol):
        # Get 1-minute candles for quick analysis
        candles = self.request('GET', f'/api/v5/market/candles?instId={symbol}&bar=1m&limit=20')
        ticker = self.request('GET', f'/api/v5/market/ticker?instId={symbol}')
        
        if not candles or not ticker:
            return 0.0
        
        # Extract data
        price_data = candles['data']
        if len(price_data) < 15:
            return 0.0
        
        closes = np.array([float(c[4]) for c in price_data])
        volumes = np.array([float(c[5]) for c in price_data])
        
        signal_components = []
        
        # 1. Short-term momentum (last 5 minutes vs previous 10)
        recent_avg = np.mean(closes[-5:])
        previous_avg = np.mean(closes[-15:-5])
        momentum = (recent_avg - previous_avg) / previous_avg
        
        if momentum > 0.002:  # 0.2% upward momentum
            signal_components.append(0.4)
        elif momentum > 0.001:
            signal_components.append(0.2)
        elif momentum < -0.002:
            signal_components.append(-0.3)
        else:
            signal_components.append(0)
        
        # 2. Volume confirmation
        recent_vol = np.mean(volumes[-5:])
        avg_vol = np.mean(volumes[:-5])
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
        
        if vol_ratio > 1.3:  # Higher volume
            signal_components.append(0.3)
        elif vol_ratio > 1.1:
            signal_components.append(0.15)
        else:
            signal_components.append(0)
        
        # 3. Price position relative to recent range
        high_5min = np.max(closes[-5:])
        low_5min = np.min(closes[-5:])
        current = closes[-1]
        
        if low_5min != high_5min:
            position = (current - low_5min) / (high_5min - low_5min)
            if position > 0.8:  # Near top of range
                signal_components.append(0.2)
            elif position < 0.2:  # Near bottom of range
                signal_components.append(0.3)
            else:
                signal_components.append(0)
        
        # 4. 24h change consideration
        change_24h = float(ticker['data'][0]['sodUtc8'])
        if change_24h > 1:  # Positive 24h trend
            signal_components.append(0.2)
        elif change_24h < -2:
            signal_components.append(-0.2)
        else:
            signal_components.append(0)
        
        return sum(signal_components)
    
    def execute_buy_order(self, symbol, usdt_amount):
        price = self.get_price(symbol)
        if not price:
            return None
        
        # Get instrument specifications
        inst = self.request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst:
            return None
        
        min_size = float(inst['data'][0]['minSz'])
        lot_size = inst['data'][0]['lotSz']
        
        raw_qty = usdt_amount / price
        if raw_qty < min_size:
            return None
        
        formatted_qty = self.format_size(raw_qty, lot_size)
        
        order_payload = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": formatted_qty
        }
        
        result = self.request('POST', '/api/v5/trade/order', json.dumps(order_payload))
        
        if result and result.get('data'):
            order_id = result['data'][0]['ordId']
            
            self.position = {
                'symbol': symbol,
                'quantity': float(formatted_qty),
                'entry_price': price,
                'entry_time': time.time(),
                'order_id': order_id,
                'amount_invested': usdt_amount
            }
            
            print(f"BUY EXECUTED: {symbol}")
            print(f"Quantity: {formatted_qty} @ ${price:.6f}")
            print(f"Investment: ${usdt_amount:.2f} | Order: {order_id}")
            return order_id
        
        return None
    
    def execute_sell_order(self):
        if not self.position:
            return None
        
        symbol = self.position['symbol']
        quantity = self.position['quantity']
        
        # Get lot size for formatting
        inst = self.request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst:
            return None
        
        lot_size = inst['data'][0]['lotSz']
        formatted_qty = self.format_size(quantity, lot_size)
        
        order_payload = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "sell",
            "ordType": "market",
            "sz": formatted_qty
        }
        
        result = self.request('POST', '/api/v5/trade/order', json.dumps(order_payload))
        
        if result and result.get('data'):
            order_id = result['data'][0]['ordId']
            
            # Calculate P&L
            current_price = self.get_price(symbol)
            if current_price:
                pnl_pct = (current_price - self.position['entry_price']) / self.position['entry_price']
                pnl_usd = pnl_pct * self.position['amount_invested']
                
                self.total_pnl += pnl_usd
                self.trades_count += 1
                
                if pnl_pct > 0:
                    self.profit_count += 1
                
                print(f"SELL EXECUTED: {symbol}")
                print(f"P&L: {pnl_pct*100:.2f}% (${pnl_usd:.3f})")
                print(f"Exit Price: ${current_price:.6f} | Order: {order_id}")
            
            self.position = None
            return order_id
        
        return None
    
    def monitor_position(self):
        if not self.position:
            return
        
        symbol = self.position['symbol']
        current_price = self.get_price(symbol)
        
        if not current_price:
            return
        
        # Calculate current P&L
        pnl_pct = (current_price - self.position['entry_price']) / self.position['entry_price']
        hold_time = time.time() - self.position['entry_time']
        
        should_sell = False
        reason = ""
        
        # Check exit conditions
        if pnl_pct >= self.profit_target:
            should_sell = True
            reason = f"PROFIT TARGET {pnl_pct*100:.2f}%"
        elif pnl_pct <= self.stop_loss:
            should_sell = True
            reason = f"STOP LOSS {pnl_pct*100:.2f}%"
        elif hold_time > self.max_hold_time:
            should_sell = True
            reason = f"TIME LIMIT {hold_time/60:.1f}min"
        
        if should_sell:
            print(f"CLOSING: {reason}")
            self.execute_sell_order()
    
    def trading_cycle(self):
        cycle_time = datetime.now().strftime('%H:%M:%S')
        print(f"\n=== TRADING CYCLE {cycle_time} ===")
        
        usdt_balance = self.get_usdt_balance()
        win_rate = (self.profit_count / max(self.trades_count, 1)) * 100
        
        print(f"USDT: ${usdt_balance:.2f} | Trades: {self.trades_count}")
        print(f"Win Rate: {win_rate:.1f}% | Total P&L: ${self.total_pnl:.3f}")
        
        # Monitor existing position
        self.monitor_position()
        
        # Look for new trading opportunities
        if not self.position and usdt_balance >= 2.0:
            best_signal = 0
            best_symbol = None
            
            print("Scanning markets...")
            for symbol in self.symbols:
                signal = self.calculate_signal_strength(symbol)
                print(f"{symbol}: {signal:.3f}")
                
                if signal > best_signal and signal > 0.5:  # Strong signal threshold
                    best_signal = signal
                    best_symbol = symbol
            
            if best_symbol:
                # Use 80% of available balance
                trade_amount = min(usdt_balance * 0.8, usdt_balance - 1.0)
                
                if trade_amount >= 2.0:
                    print(f"TRADE SIGNAL: {best_symbol} ({best_signal:.3f})")
                    self.execute_buy_order(best_symbol, trade_amount)
                else:
                    print("Trade amount insufficient")
            else:
                print("No strong signals detected")
        elif self.position:
            symbol = self.position['symbol']
            hold_time = (time.time() - self.position['entry_time']) / 60
            current_price = self.get_price(symbol)
            if current_price:
                pnl = (current_price - self.position['entry_price']) / self.position['entry_price'] * 100
                print(f"Holding {symbol}: {pnl:+.2f}% | {hold_time:.1f}min")
        else:
            print(f"Insufficient balance: ${usdt_balance:.2f}")
    
    def run(self):
        print("AUTONOMOUS LIVE TRADER - STARTING EXECUTION")
        print("Real-time market analysis • Live trade execution • Profit optimization")
        print("=" * 65)
        
        while True:
            try:
                self.trading_cycle()
                
                # Adaptive wait time
                if self.position:
                    wait_time = 10  # Monitor positions closely
                else:
                    wait_time = 25  # Market scanning interval
                
                print(f"Next cycle: {wait_time}s")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("\nTrader stopped")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(30)

if __name__ == "__main__":
    trader = LiveTrader()
    trader.run()