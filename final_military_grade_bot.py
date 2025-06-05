#!/usr/bin/env python3
"""
Final Military Grade Trading Bot - Fully Autonomous with Corrected Execution
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
import numpy as np
import threading
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from concurrent.futures import ThreadPoolExecutor, as_completed

class FinalMilitaryBot:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Military-grade trading parameters
        self.max_positions = 6
        self.profit_target = 0.018  # 1.8% profit target
        self.stop_loss = -0.025     # 2.5% stop loss
        self.max_hold_time = 240    # 4 minutes max hold
        self.position_size_pct = 0.28  # 28% per position
        self.signal_threshold = 0.6    # High-quality signals only
        
        # Validated trading pairs (corrected from previous failures)
        self.tier1_pairs = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT']
        self.tier2_pairs = ['ADA-USDT', 'XRP-USDT', 'DOGE-USDT', 'TRX-USDT']
        self.tier3_pairs = ['AVAX-USDT', 'DOT-USDT', 'LINK-USDT']
        
        self.active_positions = {}
        self.performance = {
            'total_trades': 0,
            'profitable_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'best_trade': 0.0,
            'consecutive_wins': 0,
            'max_consecutive_wins': 0
        }
        
        self.lock = threading.Lock()
        
        print("MILITARY GRADE BOT INITIALIZED")
        print("Advanced algorithms, precision execution, profit optimization")
    
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
    
    def api_request(self, method: str, endpoint: str, body: str = None, retries: int = 2):
        for attempt in range(retries):
            try:
                headers = self.get_headers(method, endpoint, body or '')
                url = self.base_url + endpoint
                
                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=10)
                else:
                    response = requests.post(url, headers=headers, data=body, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('code') == '0':
                        return data
                
                time.sleep(1)
            except Exception:
                time.sleep(1)
        
        return None
    
    def get_balance(self) -> float:
        data = self.api_request('GET', '/api/v5/account/balance')
        if data:
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    return float(detail['availBal'])
        return 0.0
    
    def format_quantity(self, quantity: float, lot_size: str) -> str:
        """Format quantity with proper precision for OKX API"""
        lot_decimal = Decimal(lot_size)
        quantity_decimal = Decimal(str(quantity))
        formatted = quantity_decimal.quantize(lot_decimal, rounding=ROUND_DOWN)
        return str(formatted.normalize())
    
    def get_market_data(self, symbol: str):
        # Get 1-minute candles for rapid analysis
        candles = self.api_request('GET', f'/api/v5/market/candles?instId={symbol}&bar=1m&limit=30')
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        
        if not candles or not ticker:
            return None
        
        return {
            'candles': candles['data'],
            'ticker': ticker['data'][0],
            'symbol': symbol
        }
    
    def calculate_signal_strength(self, market_data: dict) -> float:
        """Advanced signal calculation with multiple indicators"""
        candles = market_data['candles']
        
        if len(candles) < 20:
            return 0.0
        
        # Extract price and volume data
        closes = np.array([float(c[4]) for c in candles])
        volumes = np.array([float(c[5]) for c in candles])
        highs = np.array([float(c[2]) for c in candles])
        lows = np.array([float(c[3]) for c in candles])
        
        signals = []
        
        # 1. RSI Analysis
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 0
        avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 0.001
        
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))
        
        if rsi < 25:
            signals.append(0.5)  # Strong oversold signal
        elif rsi < 35:
            signals.append(0.3)  # Oversold signal
        elif rsi > 75:
            signals.append(-0.5)  # Strong overbought signal
        elif rsi > 65:
            signals.append(-0.3)  # Overbought signal
        else:
            signals.append(0)
        
        # 2. Momentum Analysis
        if len(closes) >= 10:
            momentum_5 = (closes[-1] / closes[-6] - 1) * 100
            momentum_10 = (closes[-1] / closes[-11] - 1) * 100
            
            if momentum_5 > 2 and momentum_10 > 1:
                signals.append(0.4)  # Strong upward momentum
            elif momentum_5 > 1:
                signals.append(0.25)  # Moderate momentum
            elif momentum_5 < -2 and momentum_10 < -1:
                signals.append(-0.4)  # Strong downward momentum
            elif momentum_5 < -1:
                signals.append(-0.25)  # Moderate decline
            else:
                signals.append(0)
        
        # 3. Volume Confirmation
        if len(volumes) >= 10:
            avg_volume = np.mean(volumes[-10:])
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            if volume_ratio > 2:
                signals.append(0.3)  # High volume confirmation
            elif volume_ratio > 1.5:
                signals.append(0.2)  # Good volume
            elif volume_ratio < 0.7:
                signals.append(-0.1)  # Low volume warning
            else:
                signals.append(0)
        
        # 4. Price Action Quality
        if len(closes) >= 15:
            recent_high = np.max(highs[-10:])
            recent_low = np.min(lows[-10:])
            current_price = closes[-1]
            
            price_position = (current_price - recent_low) / (recent_high - recent_low) if recent_high != recent_low else 0.5
            
            if price_position < 0.2:
                signals.append(0.2)  # Near support
            elif price_position > 0.8:
                signals.append(-0.2)  # Near resistance
            else:
                signals.append(0)
        
        # 5. Volatility Check
        if len(closes) >= 15:
            returns = np.diff(closes) / closes[:-1]
            volatility = np.std(returns) * 100
            
            if 1 <= volatility <= 5:
                signals.append(0.15)  # Good volatility
            elif volatility > 8:
                signals.append(-0.2)  # Too volatile
            else:
                signals.append(0)
        
        # Calculate final signal
        final_signal = sum(signals)
        
        # Apply market cap weighting
        ticker = market_data['ticker']
        volume_24h = float(ticker['vol24h'])
        
        if volume_24h > 1000000:  # High liquidity bonus
            final_signal *= 1.1
        elif volume_24h < 100000:  # Low liquidity penalty
            final_signal *= 0.8
        
        return max(-1, min(1, final_signal))
    
    def execute_buy_order(self, symbol: str, usdt_amount: float):
        ticker_data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker_data:
            return None
        
        price = float(ticker_data['data'][0]['last'])
        
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data:
            return None
        
        inst_info = inst_data['data'][0]
        min_size = float(inst_info['minSz'])
        lot_size = inst_info['lotSz']
        
        raw_quantity = usdt_amount / price
        
        if raw_quantity < min_size:
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
            
            with self.lock:
                self.active_positions[symbol] = {
                    'quantity': float(formatted_quantity),
                    'entry_price': price,
                    'entry_time': time.time(),
                    'order_id': order_id,
                    'invested': usdt_amount
                }
            
            print(f"BUY: {symbol} - {formatted_quantity} @ ${price:.6f} = ${usdt_amount:.2f}")
            return order_id
        
        return None
    
    def execute_sell_order(self, symbol: str, quantity: float):
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
            
            with self.lock:
                if symbol in self.active_positions:
                    del self.active_positions[symbol]
            
            print(f"SELL: {symbol} - {formatted_quantity}")
            return order_id
        
        return None
    
    def manage_positions(self):
        current_time = time.time()
        positions_to_close = []
        
        with self.lock:
            for symbol, position in self.active_positions.items():
                ticker_data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
                
                if ticker_data:
                    current_price = float(ticker_data['data'][0]['last'])
                    pnl_pct = (current_price - position['entry_price']) / position['entry_price']
                    hold_time = current_time - position['entry_time']
                    
                    should_close = False
                    reason = ""
                    
                    if pnl_pct >= self.profit_target:
                        should_close = True
                        reason = f"profit target {pnl_pct*100:.2f}%"
                        self.performance['profitable_trades'] += 1
                        self.performance['consecutive_wins'] += 1
                        self.performance['max_consecutive_wins'] = max(
                            self.performance['max_consecutive_wins'],
                            self.performance['consecutive_wins']
                        )
                        if pnl_pct > self.performance['best_trade']:
                            self.performance['best_trade'] = pnl_pct
                    
                    elif pnl_pct <= self.stop_loss:
                        should_close = True
                        reason = f"stop loss {pnl_pct*100:.2f}%"
                        self.performance['consecutive_wins'] = 0
                    
                    elif hold_time > self.max_hold_time:
                        should_close = True
                        reason = f"time limit {hold_time/60:.1f}min"
                        if pnl_pct > 0:
                            self.performance['profitable_trades'] += 1
                            self.performance['consecutive_wins'] += 1
                        else:
                            self.performance['consecutive_wins'] = 0
                    
                    if should_close:
                        positions_to_close.append((symbol, position['quantity'], reason, pnl_pct))
                        self.performance['total_trades'] += 1
                        self.performance['total_pnl'] += pnl_pct * position['invested']
        
        # Execute closures
        for symbol, quantity, reason, pnl_pct in positions_to_close:
            self.execute_sell_order(symbol, quantity)
            print(f"CLOSED: {symbol} - {reason} (P&L: {pnl_pct*100:.2f}%)")
    
    def scan_opportunities(self, balance: float):
        all_pairs = self.tier1_pairs + self.tier2_pairs + self.tier3_pairs
        opportunities = []
        
        def analyze_symbol(symbol):
            if symbol in self.active_positions:
                return None
            
            market_data = self.get_market_data(symbol)
            if not market_data:
                return None
            
            signal = self.calculate_signal_strength(market_data)
            
            if abs(signal) >= self.signal_threshold:
                return (symbol, signal)
            
            return None
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(analyze_symbol, symbol): symbol for symbol in all_pairs}
            
            for future in as_completed(futures, timeout=15):
                try:
                    result = future.result()
                    if result:
                        opportunities.append(result)
                except Exception:
                    continue
        
        opportunities.sort(key=lambda x: abs(x[1]), reverse=True)
        return opportunities[:3]
    
    def execute_trading_cycle(self):
        cycle_time = datetime.now().strftime('%H:%M:%S')
        print(f"\n=== MILITARY CYCLE - {cycle_time} ===")
        
        balance = self.get_balance()
        
        # Update performance metrics
        if self.performance['total_trades'] > 0:
            win_rate = (self.performance['profitable_trades'] / self.performance['total_trades']) * 100
        else:
            win_rate = 0
        
        print(f"Balance: ${balance:.2f} | Positions: {len(self.active_positions)}")
        print(f"Performance: {self.performance['total_trades']} trades, {win_rate:.1f}% win rate")
        print(f"Total P&L: ${self.performance['total_pnl']:.2f} | Best: {self.performance['best_trade']*100:.1f}%")
        print(f"Win streak: {self.performance['consecutive_wins']} | Max: {self.performance['max_consecutive_wins']}")
        
        # Position management
        self.manage_positions()
        
        # Brief pause after position management
        if len(self.active_positions) != len(self.active_positions):
            time.sleep(2)
            balance = self.get_balance()
        
        # Opportunity scanning and execution
        if balance >= 2 and len(self.active_positions) < self.max_positions:
            opportunities = self.scan_opportunities(balance)
            
            for symbol, signal in opportunities:
                if balance < 2:
                    break
                
                position_amount = min(
                    balance * self.position_size_pct,
                    balance * 0.35  # Max 35% per position
                )
                
                if position_amount >= 2:
                    if signal > 0:  # Only long positions for safety
                        print(f"OPPORTUNITY: {symbol} - Signal: {signal:.3f}")
                        order_id = self.execute_buy_order(symbol, position_amount)
                        
                        if order_id:
                            balance -= position_amount
                            time.sleep(1)
        
        elif len(self.active_positions) >= self.max_positions:
            print("Maximum positions reached - monitoring for exits")
        else:
            print(f"Insufficient balance: ${balance:.2f}")
    
    def run_autonomous_bot(self):
        print("\n" + "=" * 80)
        print("MILITARY GRADE AUTONOMOUS TRADING BOT - FULLY OPERATIONAL")
        print("Advanced algorithms • Precision execution • Profit optimization")
        print("Maximum sophistication • Institutional performance • Seamless automation")
        print("=" * 80)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                
                self.execute_trading_cycle()
                
                # Dynamic timing based on market activity
                if len(self.active_positions) > 2:
                    wait_time = 15  # Fast monitoring with multiple positions
                elif len(self.active_positions) > 0:
                    wait_time = 25  # Standard monitoring
                else:
                    wait_time = 35  # Opportunity scanning
                
                print(f"Next cycle in {wait_time} seconds...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("\nAutonomous bot stopped by user")
                break
            except Exception as e:
                print(f"Bot error handled: {e}")
                time.sleep(30)

def main():
    bot = FinalMilitaryBot()
    bot.run_autonomous_bot()

if __name__ == "__main__":
    main()