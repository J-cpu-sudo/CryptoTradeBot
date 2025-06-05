#!/usr/bin/env python3
"""
Ultra Performance Trading Engine - Maximum sophistication with validated trading pairs
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
from typing import Dict, List, Tuple, Optional

class UltraPerformanceEngine:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Validated high-performance trading pairs
        self.core_pairs = [
            'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT',
            'ADA-USDT', 'XRP-USDT', 'DOGE-USDT', 'TRX-USDT',
            'AVAX-USDT', 'DOT-USDT', 'MATIC-USDT', 'LINK-USDT'
        ]
        
        self.momentum_pairs = [
            'PEPE-USDT', 'SHIB-USDT', 'WIF-USDT', 'BONK-USDT',
            'FLOKI-USDT', 'MEME-USDT'
        ]
        
        # Ultra-performance parameters
        self.max_positions = 6
        self.profit_target = 0.018  # 1.8% profit target
        self.stop_loss = -0.025     # 2.5% stop loss
        self.max_hold_time = 240    # 4 minutes max hold
        self.min_signal_strength = 0.65
        
        self.active_positions = {}
        self.trade_history = []
        self.performance_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0.0,
            'max_consecutive_wins': 0,
            'current_streak': 0
        }
        
        self.position_lock = threading.Lock()
    
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
    
    def api_request(self, method: str, endpoint: str, body: str = None, timeout: int = 12) -> Optional[Dict]:
        try:
            headers = self.get_headers(method, endpoint, body or '')
            url = self.base_url + endpoint
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    return data
            
            return None
        except Exception:
            return None
    
    def get_portfolio(self) -> Dict[str, float]:
        data = self.api_request('GET', '/api/v5/account/balance')
        portfolio = {}
        
        if data:
            for detail in data['data'][0]['details']:
                balance = float(detail['availBal'])
                if balance > 0:
                    portfolio[detail['ccy']] = balance
        
        return portfolio
    
    def get_market_analysis(self, symbol: str) -> Optional[Dict]:
        # Get 1-minute candles for analysis
        candle_data = self.api_request('GET', f'/api/v5/market/candles?instId={symbol}&bar=1m&limit=60')
        ticker_data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        
        if not candle_data or not ticker_data:
            return None
        
        candles = candle_data['data']
        ticker = ticker_data['data'][0]
        
        if len(candles) < 30:
            return None
        
        # Extract price and volume data
        closes = np.array([float(c[4]) for c in candles])
        volumes = np.array([float(c[5]) for c in candles])
        highs = np.array([float(c[2]) for c in candles])
        lows = np.array([float(c[3]) for c in candles])
        
        # Calculate advanced indicators
        analysis = self.calculate_ultra_indicators(closes, volumes, highs, lows)
        analysis['current_price'] = float(ticker['last'])
        analysis['volume_24h'] = float(ticker['vol24h'])
        analysis['price_change_24h'] = float(ticker['chgUtc'])
        
        return analysis
    
    def calculate_ultra_indicators(self, closes: np.ndarray, volumes: np.ndarray, 
                                  highs: np.ndarray, lows: np.ndarray) -> Dict[str, float]:
        indicators = {}
        
        # RSI with dynamic period
        rsi_period = min(14, len(closes) // 2)
        if len(closes) > rsi_period:
            deltas = np.diff(closes)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains[-rsi_period:])
            avg_loss = np.mean(losses[-rsi_period:])
            
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                indicators['rsi'] = 100 - (100 / (1 + rs))
            else:
                indicators['rsi'] = 100
        else:
            indicators['rsi'] = 50
        
        # Momentum indicators
        if len(closes) >= 10:
            indicators['momentum_5'] = (closes[-1] / closes[-6] - 1) * 100
            indicators['momentum_10'] = (closes[-1] / closes[-11] - 1) * 100
        else:
            indicators['momentum_5'] = 0
            indicators['momentum_10'] = 0
        
        # Volatility (ATR)
        if len(closes) >= 15:
            tr = np.maximum(highs[1:] - lows[1:], 
                           np.maximum(np.abs(highs[1:] - closes[:-1]), 
                                     np.abs(lows[1:] - closes[:-1])))
            indicators['atr'] = np.mean(tr[-14:])
            indicators['volatility_pct'] = (indicators['atr'] / closes[-1]) * 100
        else:
            indicators['atr'] = 0
            indicators['volatility_pct'] = 1
        
        # Volume analysis
        if len(volumes) >= 20:
            indicators['volume_sma'] = np.mean(volumes[-20:])
            indicators['volume_ratio'] = volumes[-1] / indicators['volume_sma']
            
            # Volume momentum
            recent_volume = np.mean(volumes[-5:])
            older_volume = np.mean(volumes[-20:-15])
            indicators['volume_momentum'] = (recent_volume / older_volume - 1) * 100 if older_volume > 0 else 0
        else:
            indicators['volume_sma'] = volumes[-1] if len(volumes) > 0 else 1
            indicators['volume_ratio'] = 1
            indicators['volume_momentum'] = 0
        
        # Moving averages
        if len(closes) >= 20:
            indicators['sma_10'] = np.mean(closes[-10:])
            indicators['sma_20'] = np.mean(closes[-20:])
            indicators['price_vs_sma10'] = (closes[-1] / indicators['sma_10'] - 1) * 100
            indicators['price_vs_sma20'] = (closes[-1] / indicators['sma_20'] - 1) * 100
        else:
            indicators['sma_10'] = closes[-1]
            indicators['sma_20'] = closes[-1]
            indicators['price_vs_sma10'] = 0
            indicators['price_vs_sma20'] = 0
        
        return indicators
    
    def calculate_signal_score(self, analysis: Dict) -> float:
        if not analysis:
            return 0
        
        score_components = []
        
        # RSI component (oversold/overbought)
        rsi = analysis.get('rsi', 50)
        if rsi < 25:
            score_components.append(0.4)  # Strong oversold
        elif rsi < 35:
            score_components.append(0.25)  # Oversold
        elif rsi > 75:
            score_components.append(-0.4)  # Strong overbought
        elif rsi > 65:
            score_components.append(-0.25)  # Overbought
        else:
            score_components.append(0)
        
        # Momentum component
        momentum_5 = analysis.get('momentum_5', 0)
        momentum_10 = analysis.get('momentum_10', 0)
        
        if momentum_5 > 2 and momentum_10 > 1:
            score_components.append(0.3)  # Strong upward momentum
        elif momentum_5 > 1:
            score_components.append(0.15)  # Moderate momentum
        elif momentum_5 < -2 and momentum_10 < -1:
            score_components.append(-0.3)  # Strong downward momentum
        elif momentum_5 < -1:
            score_components.append(-0.15)  # Moderate decline
        else:
            score_components.append(0)
        
        # Volume confirmation
        volume_ratio = analysis.get('volume_ratio', 1)
        volume_momentum = analysis.get('volume_momentum', 0)
        
        if volume_ratio > 1.8 and volume_momentum > 20:
            score_components.append(0.25)  # Strong volume confirmation
        elif volume_ratio > 1.4:
            score_components.append(0.15)  # Good volume
        elif volume_ratio < 0.6:
            score_components.append(-0.1)  # Low volume warning
        else:
            score_components.append(0)
        
        # Moving average trend
        price_vs_sma10 = analysis.get('price_vs_sma10', 0)
        price_vs_sma20 = analysis.get('price_vs_sma20', 0)
        
        if price_vs_sma10 > 1 and price_vs_sma20 > 0.5:
            score_components.append(0.2)  # Above moving averages
        elif price_vs_sma10 < -1 and price_vs_sma20 < -0.5:
            score_components.append(-0.2)  # Below moving averages
        else:
            score_components.append(0)
        
        # Volatility check
        volatility = analysis.get('volatility_pct', 1)
        if 2 <= volatility <= 8:
            score_components.append(0.1)  # Good volatility
        elif volatility > 12:
            score_components.append(-0.15)  # Too volatile
        else:
            score_components.append(0)
        
        # Calculate final score
        final_score = sum(score_components)
        
        # Normalize to -1 to 1 range
        return max(-1, min(1, final_score))
    
    def execute_ultra_trade(self, symbol: str, side: str, amount: float) -> Optional[str]:
        if side == 'buy':
            ticker_data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
            if not ticker_data:
                return None
            
            price = float(ticker_data['data'][0]['last'])
            
            inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
            if not inst_data:
                return None
            
            min_size = float(inst_data['data'][0]['minSz'])
            quantity = amount / price
            
            if quantity < min_size:
                return None
            
            quantity = round(quantity / min_size) * min_size
            
            order_data = {
                "instId": symbol,
                "tdMode": "cash",
                "side": "buy",
                "ordType": "market",
                "sz": str(quantity)
            }
            
            order_body = json.dumps(order_data)
            result = self.api_request('POST', '/api/v5/trade/order', order_body)
            
            if result:
                order_id = result['data'][0]['ordId']
                
                with self.position_lock:
                    self.active_positions[symbol] = {
                        'quantity': quantity,
                        'entry_price': price,
                        'entry_time': time.time(),
                        'order_id': order_id,
                        'amount_invested': amount
                    }
                
                print(f"ULTRA BUY: {symbol} - {quantity:.6f} @ ${price:.6f} = ${amount:.2f}")
                return order_id
        
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
            
            if result:
                order_id = result['data'][0]['ordId']
                
                with self.position_lock:
                    if symbol in self.active_positions:
                        del self.active_positions[symbol]
                
                print(f"ULTRA SELL: {symbol} - {amount:.6f}")
                return order_id
        
        return None
    
    def manage_ultra_positions(self) -> List[str]:
        actions = []
        current_time = time.time()
        
        with self.position_lock:
            positions_to_close = []
            
            for symbol, position in self.active_positions.items():
                ticker_data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
                
                if ticker_data:
                    current_price = float(ticker_data['data'][0]['last'])
                    pnl_pct = (current_price - position['entry_price']) / position['entry_price']
                    hold_time = current_time - position['entry_time']
                    
                    should_close = False
                    reason = ""
                    
                    # Ultra performance targets
                    if pnl_pct >= self.profit_target:
                        should_close = True
                        reason = f"profit target {pnl_pct*100:.2f}%"
                        self.performance_stats['winning_trades'] += 1
                        self.performance_stats['current_streak'] += 1
                    
                    elif pnl_pct <= self.stop_loss:
                        should_close = True
                        reason = f"stop loss {pnl_pct*100:.2f}%"
                        self.performance_stats['current_streak'] = 0
                    
                    elif hold_time > self.max_hold_time:
                        should_close = True
                        reason = f"time limit {hold_time/60:.1f}min"
                        if pnl_pct > 0:
                            self.performance_stats['winning_trades'] += 1
                            self.performance_stats['current_streak'] += 1
                        else:
                            self.performance_stats['current_streak'] = 0
                    
                    if should_close:
                        positions_to_close.append((symbol, position['quantity'], reason, pnl_pct))
                        self.performance_stats['total_trades'] += 1
                        self.performance_stats['total_pnl'] += pnl_pct * position['amount_invested']
        
        # Execute position closures
        for symbol, quantity, reason, pnl_pct in positions_to_close:
            order_id = self.execute_ultra_trade(symbol, 'sell', quantity)
            if order_id:
                actions.append(f"Closed {symbol}: {reason}")
                print(f"POSITION CLOSED: {symbol} - {reason} (P&L: {pnl_pct*100:.2f}%)")
        
        return actions
    
    def scan_ultra_opportunities(self, available_balance: float) -> List[Tuple[str, float]]:
        opportunities = []
        
        # Determine trading universe based on balance
        if available_balance >= 20:
            pairs_to_scan = self.core_pairs + self.momentum_pairs
        elif available_balance >= 10:
            pairs_to_scan = self.core_pairs[:8] + self.momentum_pairs
        else:
            pairs_to_scan = self.core_pairs[:6] + self.momentum_pairs[:4]
        
        def analyze_pair(symbol):
            if symbol in self.active_positions:
                return None
            
            analysis = self.get_market_analysis(symbol)
            if not analysis:
                return None
            
            signal_score = self.calculate_signal_score(analysis)
            
            if abs(signal_score) >= self.min_signal_strength:
                return (symbol, signal_score)
            
            return None
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(analyze_pair, symbol): symbol for symbol in pairs_to_scan}
            
            for future in as_completed(futures, timeout=25):
                try:
                    result = future.result()
                    if result:
                        opportunities.append(result)
                except Exception:
                    continue
        
        # Sort by signal strength
        opportunities.sort(key=lambda x: abs(x[1]), reverse=True)
        return opportunities[:3]  # Top 3 opportunities
    
    def execute_ultra_cycle(self):
        print(f"\n=== ULTRA PERFORMANCE CYCLE - {datetime.now().strftime('%H:%M:%S')} ===")
        
        # Portfolio state
        portfolio = self.get_portfolio()
        usdt_balance = portfolio.get('USDT', 0)
        
        # Calculate win rate
        win_rate = (self.performance_stats['winning_trades'] / max(self.performance_stats['total_trades'], 1)) * 100
        
        print(f"Balance: ${usdt_balance:.2f} | Positions: {len(self.active_positions)}")
        print(f"Performance: {self.performance_stats['total_trades']} trades, {win_rate:.1f}% win rate")
        print(f"Total P&L: ${self.performance_stats['total_pnl']:.2f} | Streak: {self.performance_stats['current_streak']}")
        
        # Position management
        management_actions = self.manage_ultra_positions()
        
        if management_actions:
            time.sleep(2)  # Brief pause after position management
            portfolio = self.get_portfolio()
            usdt_balance = portfolio.get('USDT', 0)
        
        # Opportunity scanning
        if usdt_balance >= 1.5 and len(self.active_positions) < self.max_positions:
            opportunities = self.scan_ultra_opportunities(usdt_balance)
            
            for symbol, signal_score in opportunities:
                if usdt_balance < 1.5:
                    break
                
                # Position sizing based on signal strength and available balance
                position_size = min(
                    usdt_balance * 0.25 * abs(signal_score),  # Up to 25% based on signal
                    usdt_balance * 0.4  # Maximum 40% per position
                )
                
                if position_size >= 1.5:
                    side = 'buy' if signal_score > 0 else None  # Only long positions for simplicity
                    
                    if side:
                        print(f"ULTRA OPPORTUNITY: {symbol} - Signal: {signal_score:.3f}")
                        order_id = self.execute_ultra_trade(symbol, side, position_size)
                        
                        if order_id:
                            usdt_balance -= position_size
                            time.sleep(1)  # Brief pause between trades
        
        elif len(self.active_positions) >= self.max_positions:
            print("Maximum positions reached - waiting for exits")
        else:
            print(f"Insufficient balance: ${usdt_balance:.2f}")
    
    def run_ultra_engine(self):
        print("ULTRA PERFORMANCE TRADING ENGINE")
        print("Maximum sophistication - Advanced algorithms active")
        print("=" * 60)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                
                self.execute_ultra_cycle()
                
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
                print("\nUltra engine stopped")
                break
            except Exception as e:
                print(f"Engine error: {e}")
                time.sleep(20)

def main():
    engine = UltraPerformanceEngine()
    engine.run_ultra_engine()

if __name__ == "__main__":
    main()