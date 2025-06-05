#!/usr/bin/env python3
"""
Multi-Currency Autonomous Trader - Simultaneous trading across multiple pairs
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

class MultiCurrencyTrader:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Active trading pairs for different balance levels
        self.tier1_pairs = ['PEPE-USDT', 'NEIRO-USDT', 'WIF-USDT', 'MEME-USDT']
        self.tier2_pairs = ['TURBO-USDT', 'RATS-USDT', 'ORDI-USDT', 'SATS-USDT']
        self.tier3_pairs = ['TRX-USDT', 'XRP-USDT', 'DOGE-USDT', 'ADA-USDT']
        
        self.active_positions = {}
        self.position_lock = threading.Lock()
    
    def get_timestamp(self):
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def create_signature(self, timestamp, method, path, body=''):
        message = timestamp + method + path + body
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(self, method, path, body=''):
        timestamp = self.get_timestamp()
        signature = self.create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def api_request(self, method, endpoint, body=None):
        try:
            headers = self.get_headers(method, endpoint, body or '')
            url = self.base_url + endpoint
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=10)
            
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def get_portfolio(self):
        data = self.api_request('GET', '/api/v5/account/balance')
        portfolio = {}
        
        if data and data.get('code') == '0':
            for detail in data['data'][0]['details']:
                balance = float(detail['availBal'])
                if balance > 0:
                    portfolio[detail['ccy']] = balance
        
        return portfolio
    
    def get_price(self, symbol):
        data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if data and data.get('data'):
            return float(data['data'][0]['last'])
        return None
    
    def get_volatility_score(self, symbol):
        data = self.api_request('GET', f'/api/v5/market/candles?instId={symbol}&bar=1m&limit=20')
        
        if data and data.get('data'):
            candles = data['data']
            prices = [float(candle[4]) for candle in candles]
            
            if len(prices) >= 10:
                high_price = max(prices[-10:])
                low_price = min(prices[-10:])
                volatility = (high_price - low_price) / low_price * 100
                return volatility
        
        return 0
    
    def execute_buy(self, symbol, usdt_amount):
        price = self.get_price(symbol)
        if not price:
            return None
        
        # Get instrument info
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data or not inst_data.get('data'):
            return None
        
        min_size = float(inst_data['data'][0]['minSz'])
        quantity = usdt_amount / price
        
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
        
        if result and result.get('code') == '0':
            order_id = result['data'][0]['ordId']
            
            with self.position_lock:
                self.active_positions[symbol] = {
                    'quantity': quantity,
                    'entry_price': price,
                    'entry_time': time.time(),
                    'order_id': order_id
                }
            
            print(f"BUY {symbol}: {quantity:.6f} @ ${price:.6f} = ${usdt_amount:.2f}")
            return order_id
        
        return None
    
    def execute_sell(self, symbol, quantity):
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
            print(f"SELL {symbol}: {quantity:.6f}")
            
            with self.position_lock:
                if symbol in self.active_positions:
                    del self.active_positions[symbol]
            
            return order_id
        
        return None
    
    def manage_position(self, symbol):
        """Manage a single position with profit-taking logic"""
        current_time = time.time()
        
        with self.position_lock:
            if symbol not in self.active_positions:
                return
            
            position = self.active_positions[symbol].copy()
        
        current_price = self.get_price(symbol)
        if not current_price:
            return
        
        profit_pct = (current_price - position['entry_price']) / position['entry_price']
        hold_time = current_time - position['entry_time']
        
        should_sell = False
        reason = ""
        
        # Profit target: 1.5% for quick trades
        if profit_pct >= 0.015:
            should_sell = True
            reason = f"profit {profit_pct*100:.2f}%"
        
        # Time-based exit: 2 minutes max hold
        elif hold_time > 120:
            should_sell = True
            reason = f"time limit {hold_time/60:.1f}min"
        
        # Stop loss: -3%
        elif profit_pct <= -0.03:
            should_sell = True
            reason = f"stop loss {profit_pct*100:.2f}%"
        
        if should_sell:
            print(f"SELL {symbol}: {reason}")
            self.execute_sell(symbol, position['quantity'])
    
    def scan_opportunities(self, usdt_balance):
        """Scan for trading opportunities based on balance"""
        opportunities = []
        
        if usdt_balance >= 15:
            pairs = self.tier1_pairs + self.tier2_pairs + self.tier3_pairs
        elif usdt_balance >= 8:
            pairs = self.tier1_pairs + self.tier2_pairs
        else:
            pairs = self.tier1_pairs
        
        for symbol in pairs:
            if symbol in self.active_positions:
                continue
            
            volatility = self.get_volatility_score(symbol)
            if volatility > 2:  # Minimum 2% volatility
                opportunities.append((symbol, volatility))
        
        # Sort by volatility descending
        opportunities.sort(key=lambda x: x[1], reverse=True)
        return opportunities[:3]  # Top 3 opportunities
    
    def execute_parallel_trades(self, opportunities, available_usdt):
        """Execute multiple trades in parallel"""
        if not opportunities:
            return
        
        trade_amount = available_usdt / len(opportunities) * 0.95
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for symbol, volatility in opportunities:
                if trade_amount >= 1:  # Minimum $1 per trade
                    future = executor.submit(self.execute_buy, symbol, trade_amount)
                    futures.append((symbol, future))
            
            for symbol, future in futures:
                try:
                    result = future.result(timeout=30)
                    if result:
                        print(f"Parallel trade executed: {symbol}")
                except:
                    print(f"Failed parallel trade: {symbol}")
    
    def trading_cycle(self):
        """Execute one complete trading cycle"""
        print(f"\n=== MULTI-CURRENCY CYCLE {datetime.now().strftime('%H:%M:%S')} ===")
        
        # Get current portfolio
        portfolio = self.get_portfolio()
        usdt_balance = portfolio.get('USDT', 0)
        
        print(f"Portfolio: USDT ${usdt_balance:.2f}, Positions: {len(self.active_positions)}")
        
        # Manage existing positions
        active_symbols = list(self.active_positions.keys())
        for symbol in active_symbols:
            self.manage_position(symbol)
        
        time.sleep(2)  # Brief pause after position management
        
        # Refresh balance
        portfolio = self.get_portfolio()
        usdt_balance = portfolio.get('USDT', 0)
        
        # Look for new opportunities
        if usdt_balance >= 2:  # Minimum threshold for multi-currency
            opportunities = self.scan_opportunities(usdt_balance)
            
            if opportunities:
                print(f"Found {len(opportunities)} opportunities")
                for symbol, vol in opportunities:
                    print(f"  {symbol}: {vol:.2f}% volatility")
                
                self.execute_parallel_trades(opportunities, usdt_balance)
            else:
                print("No suitable opportunities found")
        else:
            print(f"Insufficient balance: ${usdt_balance:.2f}")
    
    def run_continuous_trading(self):
        print("Multi-Currency Autonomous Trader Starting...")
        print("Targeting simultaneous trades across multiple pairs")
        print("=" * 60)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                print(f"\nCycle #{cycle_count}")
                
                self.trading_cycle()
                
                # Dynamic wait time based on market activity
                wait_time = 30 if len(self.active_positions) > 0 else 45
                print(f"Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("\nTrading stopped")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(30)

def main():
    trader = MultiCurrencyTrader()
    trader.run_continuous_trading()

if __name__ == "__main__":
    main()