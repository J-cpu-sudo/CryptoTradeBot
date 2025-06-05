#!/usr/bin/env python3
"""
Enhanced Autonomous Trader - Active balance utilization with profit cycling
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
from typing import Dict, List, Optional, Tuple

class EnhancedAutonomousTrader:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Trading configuration
        self.min_profit_threshold = 0.02  # 2% minimum profit to sell
        self.max_position_age = 300  # 5 minutes max hold time
        self.cycle_interval = 60  # 1 minute between cycles
        
        # Track positions and entry times
        self.positions = {}
        self.last_trade_time = {}
        
        # Priority trading pairs for different balance levels
        self.trading_tiers = {
            'micro': ['RATS-USDT', 'SATS-USDT', 'ORDI-USDT', 'MEME-USDT'],
            'small': ['NEIRO-USDT', 'PEPE-USDT', 'WIF-USDT', 'TURBO-USDT'],
            'medium': ['TRX-USDT', 'XRP-USDT', 'DOGE-USDT', 'ADA-USDT'],
            'large': ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT']
        }
    
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
    
    def api_request(self, method: str, endpoint: str, body: str = None) -> Optional[Dict]:
        try:
            headers = self.get_headers(method, endpoint, body or '')
            url = self.base_url + endpoint
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=10)
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"API request error: {e}")
        return None
    
    def get_current_portfolio(self) -> Dict[str, float]:
        data = self.api_request('GET', '/api/v5/account/balance')
        portfolio = {}
        
        if data and data.get('code') == '0':
            for detail in data['data'][0]['details']:
                balance = float(detail['availBal'])
                if balance > 0:
                    portfolio[detail['ccy']] = balance
        
        return portfolio
    
    def get_market_price(self, symbol: str) -> Optional[float]:
        data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if data and data.get('data'):
            return float(data['data'][0]['last'])
        return None
    
    def get_instrument_info(self, symbol: str) -> Optional[Dict]:
        data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if data and data.get('data'):
            return data['data'][0]
        return None
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        if len(prices) < period + 1:
            return None
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def get_market_signals(self, symbol: str) -> Dict[str, float]:
        # Get recent candles for technical analysis
        data = self.api_request('GET', f'/api/v5/market/candles?instId={symbol}&bar=1m&limit=50')
        
        signals = {'rsi': 50, 'trend': 0, 'volatility': 0, 'volume_ratio': 1}
        
        if data and data.get('data'):
            candles = data['data']
            prices = [float(candle[4]) for candle in candles]  # Close prices
            volumes = [float(candle[5]) for candle in candles]  # Volumes
            
            # Calculate RSI
            rsi = self.calculate_rsi(prices)
            if rsi:
                signals['rsi'] = rsi
            
            # Calculate trend (simple slope)
            if len(prices) >= 10:
                x = np.arange(len(prices[-10:]))
                y = np.array(prices[-10:])
                slope = np.polyfit(x, y, 1)[0]
                signals['trend'] = slope / prices[-1] * 1000  # Normalize
            
            # Calculate volatility
            if len(prices) >= 20:
                returns = np.diff(prices[-20:]) / prices[-20:-1]
                signals['volatility'] = np.std(returns) * 100
            
            # Volume analysis
            if len(volumes) >= 5:
                recent_vol = np.mean(volumes[-3:])
                avg_vol = np.mean(volumes[-20:])
                signals['volume_ratio'] = recent_vol / avg_vol if avg_vol > 0 else 1
        
        return signals
    
    def calculate_trade_score(self, symbol: str, signals: Dict[str, float]) -> float:
        score = 0
        
        # RSI scoring (buy oversold, sell overbought)
        rsi = signals['rsi']
        if rsi < 30:
            score += 0.4  # Strong buy signal
        elif rsi < 40:
            score += 0.2  # Moderate buy
        elif rsi > 70:
            score -= 0.4  # Strong sell signal
        elif rsi > 60:
            score -= 0.2  # Moderate sell
        
        # Trend scoring
        trend = signals['trend']
        if trend > 0.5:
            score += 0.3  # Uptrend
        elif trend < -0.5:
            score -= 0.3  # Downtrend
        
        # Volume confirmation
        vol_ratio = signals['volume_ratio']
        if vol_ratio > 1.5:
            score += 0.2  # High volume confirmation
        elif vol_ratio < 0.5:
            score -= 0.1  # Low volume warning
        
        # Volatility consideration
        volatility = signals['volatility']
        if volatility > 5:
            score -= 0.2  # Too volatile
        elif volatility < 1:
            score -= 0.1  # Too stable
        
        return max(-1, min(1, score))  # Clamp between -1 and 1
    
    def execute_buy_order(self, symbol: str, usdt_amount: float) -> Optional[str]:
        inst_info = self.get_instrument_info(symbol)
        if not inst_info:
            return None
        
        price = self.get_market_price(symbol)
        if not price:
            return None
        
        min_size = float(inst_info['minSz'])
        quantity = usdt_amount / price
        
        if quantity < min_size:
            return None
        
        # Round to proper precision
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
        
        if result and result.get('code') == '0':
            order_id = result['data'][0]['ordId']
            self.positions[symbol] = {
                'quantity': quantity,
                'entry_price': price,
                'entry_time': time.time(),
                'order_id': order_id
            }
            print(f"BUY: {quantity:.8f} {symbol} at ${price:.6f} (Order: {order_id})")
            return order_id
        
        return None
    
    def execute_sell_order(self, symbol: str, quantity: float) -> Optional[str]:
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "sell",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        result = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if result and result.get('code') == '0':
            order_id = result['data'][0]['ordId']
            print(f"SELL: {quantity:.8f} {symbol} (Order: {order_id})")
            return order_id
        
        return None
    
    def check_profit_opportunities(self, portfolio: Dict[str, float]) -> List[Tuple[str, str]]:
        actions = []
        current_time = time.time()
        
        for currency, balance in portfolio.items():
            if currency == 'USDT' or balance <= 0:
                continue
            
            symbol = f"{currency}-USDT"
            current_price = self.get_market_price(symbol)
            
            if not current_price:
                continue
            
            # Check if we have position data
            if symbol in self.positions:
                position = self.positions[symbol]
                entry_price = position['entry_price']
                entry_time = position['entry_time']
                
                # Calculate profit percentage
                profit_pct = (current_price - entry_price) / entry_price
                
                # Check sell conditions
                should_sell = False
                reason = ""
                
                if profit_pct >= self.min_profit_threshold:
                    should_sell = True
                    reason = f"profit target ({profit_pct*100:.2f}%)"
                elif current_time - entry_time > self.max_position_age:
                    should_sell = True
                    reason = f"time limit ({(current_time - entry_time)/60:.1f}min)"
                elif profit_pct < -0.05:  # 5% stop loss
                    should_sell = True
                    reason = f"stop loss ({profit_pct*100:.2f}%)"
                
                if should_sell:
                    actions.append((symbol, f"sell ({reason})"))
                    del self.positions[symbol]
            else:
                # No position data, sell anyway to realize gains
                actions.append((symbol, "sell (realize gains)"))
        
        return actions
    
    def get_trading_pairs_for_balance(self, usdt_balance: float) -> List[str]:
        if usdt_balance < 1:
            return self.trading_tiers['micro']
        elif usdt_balance < 5:
            return self.trading_tiers['micro'] + self.trading_tiers['small']
        elif usdt_balance < 20:
            return self.trading_tiers['small'] + self.trading_tiers['medium']
        else:
            return self.trading_tiers['medium'] + self.trading_tiers['large']
    
    def find_best_buy_opportunity(self, usdt_balance: float) -> Optional[Tuple[str, float]]:
        pairs = self.get_trading_pairs_for_balance(usdt_balance)
        best_pair = None
        best_score = -1
        
        for symbol in pairs:
            # Skip if recently traded
            if symbol in self.last_trade_time:
                if time.time() - self.last_trade_time[symbol] < 120:  # 2 min cooldown
                    continue
            
            signals = self.get_market_signals(symbol)
            score = self.calculate_trade_score(symbol, signals)
            
            # Only consider positive scores for buying
            if score > 0.3 and score > best_score:
                inst_info = self.get_instrument_info(symbol)
                if inst_info:
                    price = self.get_market_price(symbol)
                    if price:
                        min_cost = float(inst_info['minSz']) * price
                        if min_cost <= usdt_balance * 0.95:  # Leave 5% buffer
                            best_pair = symbol
                            best_score = score
        
        return (best_pair, best_score) if best_pair else None
    
    def execute_trading_cycle(self):
        print(f"\n=== Trading Cycle at {datetime.now().strftime('%H:%M:%S')} ===")
        
        # Get current portfolio
        portfolio = self.get_current_portfolio()
        usdt_balance = portfolio.get('USDT', 0)
        
        print(f"Portfolio: {len(portfolio)} assets, USDT: ${usdt_balance:.4f}")
        
        # Check for profit-taking opportunities
        sell_actions = self.check_profit_opportunities(portfolio)
        
        for symbol, reason in sell_actions:
            currency = symbol.split('-')[0]
            if currency in portfolio:
                quantity = portfolio[currency]
                print(f"Selling {currency}: {reason}")
                order_id = self.execute_sell_order(symbol, quantity)
                if order_id:
                    self.last_trade_time[symbol] = time.time()
                    time.sleep(2)  # Brief pause between trades
        
        # Refresh balance after sells
        time.sleep(3)
        portfolio = self.get_current_portfolio()
        usdt_balance = portfolio.get('USDT', 0)
        
        # Look for new buy opportunities
        if usdt_balance > 0.5:  # Minimum threshold
            opportunity = self.find_best_buy_opportunity(usdt_balance)
            
            if opportunity:
                symbol, score = opportunity
                # Use 90% of available balance for the trade
                trade_amount = usdt_balance * 0.9
                print(f"Buying {symbol} (score: {score:.3f}) with ${trade_amount:.4f}")
                order_id = self.execute_buy_order(symbol, trade_amount)
                if order_id:
                    self.last_trade_time[symbol] = time.time()
            else:
                print("No suitable buy opportunities found")
        else:
            print("Insufficient USDT balance for new trades")
    
    def run_continuous_trading(self):
        print("Enhanced Autonomous Trader Starting...")
        print("=" * 50)
        
        cycle_count = 0
        while True:
            try:
                cycle_count += 1
                print(f"\nCycle #{cycle_count}")
                
                self.execute_trading_cycle()
                
                print(f"Waiting {self.cycle_interval} seconds...")
                time.sleep(self.cycle_interval)
                
            except KeyboardInterrupt:
                print("\nTrading stopped by user")
                break
            except Exception as e:
                print(f"Error in trading cycle: {e}")
                time.sleep(30)  # Wait before retrying

def main():
    trader = EnhancedAutonomousTrader()
    trader.run_continuous_trading()

if __name__ == "__main__":
    main()