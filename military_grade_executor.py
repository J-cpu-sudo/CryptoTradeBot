#!/usr/bin/env python3
"""
Military Grade Trading Bot - Full Sophistication with Advanced Execution
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

class MilitaryGradeBot:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Military-grade parameters
        self.max_positions = 8
        self.profit_target = 0.015  # 1.5% profit target
        self.stop_loss = -0.022     # 2.2% stop loss
        self.position_size_pct = 0.25  # 25% per position
        self.signal_threshold = 0.55   # Lower threshold for more trades
        
        # Advanced trading pairs
        self.tier1_pairs = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT']
        self.tier2_pairs = ['ADA-USDT', 'XRP-USDT', 'DOGE-USDT', 'TRX-USDT']
        self.tier3_pairs = ['AVAX-USDT', 'DOT-USDT', 'MATIC-USDT', 'LINK-USDT']
        
        self.active_positions = {}
        self.performance = {
            'total_trades': 0,
            'profitable_trades': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0
        }
        
        self.lock = threading.Lock()
    
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
    
    def get_headers(self, method: str, path: str, body: str = '') -> Dict[str, str]:
        timestamp = self.get_timestamp()
        signature = self.create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def api_request(self, method: str, endpoint: str, body: str = None, retries: int = 3) -> Optional[Dict]:
        for attempt in range(retries):
            try:
                headers = self.get_headers(method, endpoint, body or '')
                url = self.base_url + endpoint
                
                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=12)
                else:
                    response = requests.post(url, headers=headers, data=body, timeout=12)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('code') == '0':
                        return data
                    elif attempt == retries - 1:  # Last attempt, show error
                        print(f"API Error on {endpoint}: {data.get('msg')}")
                
                time.sleep(1.5 ** attempt)
            except Exception as e:
                if attempt == retries - 1:
                    print(f"Request failed {endpoint}: {e}")
                time.sleep(1.5 ** attempt)
        
        return None
    
    def get_account_balance(self) -> float:
        data = self.api_request('GET', '/api/v5/account/balance')
        if data:
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    return float(detail['availBal'])
        return 0.0
    
    def get_market_data(self, symbol: str) -> Optional[Dict]:
        # Get 1-minute candles for rapid analysis
        candles = self.api_request('GET', f'/api/v5/market/candles?instId={symbol}&bar=1m&limit=50')
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        
        if not candles or not ticker:
            return None
        
        return {
            'candles': candles['data'],
            'ticker': ticker['data'][0],
            'symbol': symbol
        }
    
    def calculate_advanced_signal(self, market_data: Dict) -> float:
        candles = market_data['candles']
        
        if len(candles) < 20:
            return 0.0
        
        # Extract price data
        closes = np.array([float(c[4]) for c in candles])
        volumes = np.array([float(c[5]) for c in candles])
        highs = np.array([float(c[2]) for c in candles])
        lows = np.array([float(c[3]) for c in candles])
        
        current_price = closes[-1]
        
        # Advanced signal components
        signals = []
        
        # 1. RSI Divergence
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 0
        avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 0.001
        
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))
        
        if rsi < 25:
            signals.append(0.4)  # Strong oversold
        elif rsi < 35:
            signals.append(0.25)  # Oversold
        elif rsi > 75:
            signals.append(-0.4)  # Strong overbought
        elif rsi > 65:
            signals.append(-0.25)  # Overbought
        else:
            signals.append(0)
        
        # 2. Price momentum
        if len(closes) >= 10:
            momentum_5 = (closes[-1] / closes[-6] - 1) * 100
            momentum_10 = (closes[-1] / closes[-11] - 1) * 100
            
            if momentum_5 > 1.5 and momentum_10 > 0.8:
                signals.append(0.35)  # Strong upward momentum
            elif momentum_5 > 0.8:
                signals.append(0.2)  # Moderate momentum
            elif momentum_5 < -1.5 and momentum_10 < -0.8:
                signals.append(-0.35)  # Strong downward momentum
            elif momentum_5 < -0.8:
                signals.append(-0.2)  # Moderate decline
            else:
                signals.append(0)
        
        # 3. Volume confirmation
        if len(volumes) >= 10:
            avg_volume = np.mean(volumes[-10:])
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            if volume_ratio > 1.8:
                signals.append(0.25)  # High volume confirmation
            elif volume_ratio > 1.4:
                signals.append(0.15)  # Good volume
            elif volume_ratio < 0.6:
                signals.append(-0.1)  # Low volume warning
            else:
                signals.append(0)
        
        # 4. Volatility assessment
        if len(closes) >= 15:
            tr = np.maximum(highs[1:] - lows[1:], 
                           np.maximum(np.abs(highs[1:] - closes[:-1]), 
                                     np.abs(lows[1:] - closes[:-1])))
            atr = np.mean(tr[-14:])
            volatility_pct = (atr / current_price) * 100
            
            if 2 <= volatility_pct <= 6:
                signals.append(0.15)  # Good volatility for trading
            elif volatility_pct > 10:
                signals.append(-0.2)  # Too volatile
            else:
                signals.append(0)
        
        # 5. Moving average trend
        if len(closes) >= 20:
            sma_10 = np.mean(closes[-10:])
            sma_20 = np.mean(closes[-20:])
            
            price_vs_sma10 = (current_price / sma_10 - 1) * 100
            sma_trend = (sma_10 / sma_20 - 1) * 100
            
            if price_vs_sma10 > 0.8 and sma_trend > 0.5:
                signals.append(0.2)  # Above moving averages, uptrend
            elif price_vs_sma10 < -0.8 and sma_trend < -0.5:
                signals.append(-0.2)  # Below moving averages, downtrend
            else:
                signals.append(0)
        
        # Calculate final signal
        final_signal = sum(signals)
        
        # Normalize to -1 to 1 range
        return max(-1, min(1, final_signal))
    
    def execute_precision_trade(self, symbol: str, side: str, amount: float) -> Optional[str]:
        # Get current market price
        ticker_data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker_data:
            return None
        
        current_price = float(ticker_data['data'][0]['last'])
        
        # Get instrument specifications
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data:
            return None
        
        inst_spec = inst_data['data'][0]
        min_size = float(inst_spec['minSz'])
        
        if side == 'buy':
            quantity = amount / current_price
            
            if quantity < min_size:
                return None
            
            # Use precise quantity calculation
            quantity = max(min_size, round(quantity, 8))
            
            order_data = {
                "instId": symbol,
                "tdMode": "cash",
                "side": "buy",
                "ordType": "market",
                "sz": str(quantity)
            }
            
        else:  # sell
            order_data = {
                "instId": symbol,
                "tdMode": "cash",
                "side": "sell",
                "ordType": "market",
                "sz": str(amount)
            }
        
        order_body = json.dumps(order_data)
        result = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if result and result.get('data'):
            order_id = result['data'][0]['ordId']
            
            if side == 'buy':
                with self.lock:
                    self.active_positions[symbol] = {
                        'quantity': quantity,
                        'entry_price': current_price,
                        'entry_time': time.time(),
                        'order_id': order_id,
                        'invested_amount': amount
                    }
                
                print(f"BUY EXECUTED: {symbol} - {quantity:.6f} @ ${current_price:.6f}")
            else:
                with self.lock:
                    if symbol in self.active_positions:
                        del self.active_positions[symbol]
                
                print(f"SELL EXECUTED: {symbol} - {amount:.6f}")
            
            return order_id
        
        return None
    
    def manage_positions(self) -> List[str]:
        actions = []
        current_time = time.time()
        
        with self.lock:
            positions_to_close = []
            
            for symbol, position in self.active_positions.items():
                ticker_data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
                
                if ticker_data:
                    current_price = float(ticker_data['data'][0]['last'])
                    pnl_pct = (current_price - position['entry_price']) / position['entry_price']
                    hold_time = current_time - position['entry_time']
                    
                    should_close = False
                    reason = ""
                    
                    # Military-grade exit conditions
                    if pnl_pct >= self.profit_target:
                        should_close = True
                        reason = f"profit target {pnl_pct*100:.2f}%"
                        self.performance['profitable_trades'] += 1
                    
                    elif pnl_pct <= self.stop_loss:
                        should_close = True
                        reason = f"stop loss {pnl_pct*100:.2f}%"
                    
                    elif hold_time > 300:  # 5 minutes max hold
                        should_close = True
                        reason = f"time limit {hold_time/60:.1f}min"
                        if pnl_pct > 0:
                            self.performance['profitable_trades'] += 1
                    
                    if should_close:
                        positions_to_close.append((symbol, position['quantity'], reason, pnl_pct))
                        self.performance['total_trades'] += 1
                        self.performance['total_pnl'] += pnl_pct * position['invested_amount']
        
        # Execute position closures
        for symbol, quantity, reason, pnl_pct in positions_to_close:
            order_id = self.execute_precision_trade(symbol, 'sell', quantity)
            if order_id:
                actions.append(f"Closed {symbol}: {reason}")
                print(f"POSITION CLOSED: {symbol} - {reason} (P&L: {pnl_pct*100:.2f}%)")
        
        return actions
    
    def scan_opportunities(self, balance: float) -> List[tuple]:
        all_pairs = self.tier1_pairs + self.tier2_pairs + self.tier3_pairs
        opportunities = []
        
        def analyze_symbol(symbol):
            if symbol in self.active_positions:
                return None
            
            market_data = self.get_market_data(symbol)
            if not market_data:
                return None
            
            signal = self.calculate_advanced_signal(market_data)
            
            if abs(signal) >= self.signal_threshold:
                return (symbol, signal)
            
            return None
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(analyze_symbol, symbol): symbol for symbol in all_pairs}
            
            for future in as_completed(futures, timeout=20):
                try:
                    result = future.result()
                    if result:
                        opportunities.append(result)
                except Exception:
                    continue
        
        # Sort by signal strength
        opportunities.sort(key=lambda x: abs(x[1]), reverse=True)
        return opportunities[:4]  # Top 4 opportunities
    
    def execute_trading_cycle(self):
        print(f"\n=== MILITARY GRADE CYCLE - {datetime.now().strftime('%H:%M:%S')} ===")
        
        # Get current balance
        balance = self.get_account_balance()
        
        # Update win rate
        if self.performance['total_trades'] > 0:
            self.performance['win_rate'] = (self.performance['profitable_trades'] / self.performance['total_trades']) * 100
        
        print(f"Balance: ${balance:.2f} | Positions: {len(self.active_positions)}")
        print(f"Performance: {self.performance['total_trades']} trades, {self.performance['win_rate']:.1f}% win rate")
        print(f"Total P&L: ${self.performance['total_pnl']:.2f}")
        
        # Position management
        management_actions = self.manage_positions()
        
        if management_actions:
            time.sleep(2)
            balance = self.get_account_balance()
        
        # Opportunity scanning and execution
        if balance >= 2 and len(self.active_positions) < self.max_positions:
            opportunities = self.scan_opportunities(balance)
            
            for symbol, signal in opportunities:
                if balance < 2:
                    break
                
                # Calculate position size
                position_amount = min(
                    balance * self.position_size_pct,
                    balance * 0.4  # Max 40% per position
                )
                
                if position_amount >= 2:
                    side = 'buy' if signal > 0 else None  # Only long positions
                    
                    if side:
                        print(f"OPPORTUNITY: {symbol} - Signal: {signal:.3f}")
                        order_id = self.execute_precision_trade(symbol, side, position_amount)
                        
                        if order_id:
                            balance -= position_amount
                            time.sleep(1)
        
        elif len(self.active_positions) >= self.max_positions:
            print("Maximum positions reached")
        else:
            print(f"Insufficient balance: ${balance:.2f}")
    
    def run_military_grade_bot(self):
        print("MILITARY GRADE TRADING BOT ACTIVATED")
        print("Advanced algorithms, precision execution, profit optimization")
        print("=" * 70)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                
                self.execute_trading_cycle()
                
                # Dynamic timing
                if len(self.active_positions) > 3:
                    wait_time = 15  # Fast monitoring
                elif len(self.active_positions) > 0:
                    wait_time = 25  # Standard monitoring
                else:
                    wait_time = 35  # Opportunity scanning
                
                print(f"Next cycle in {wait_time} seconds...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("\nMilitary grade bot stopped")
                break
            except Exception as e:
                print(f"Bot error: {e}")
                time.sleep(30)

def main():
    bot = MilitaryGradeBot()
    bot.run_military_grade_bot()

if __name__ == "__main__":
    main()