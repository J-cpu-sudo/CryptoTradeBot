#!/usr/bin/env python3
"""
Force Micro Trade - Lower threshold autonomous trading for demonstration
"""
import os
import time
import json
import requests
import hmac
import hashlib
import base64
from datetime import datetime
import threading

class MicroTradingBot:
    """Autonomous bot with lower thresholds to ensure trade execution"""
    
    def __init__(self):
        self.api_key = os.getenv('OKX_API_KEY')
        self.secret_key = os.getenv('OKX_SECRET_KEY')
        self.passphrase = os.getenv('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Very low thresholds for demonstration
        self.active_pairs = ['TRX-USDT', 'DOGE-USDT']
        self.max_trade_amount = 1.0  # $1 trades
        self.min_confidence = 0.40   # 40% confidence (very low)
        
        self.trades_executed = 0
        self.running = False
        
        print("Micro Trading Bot - LOW THRESHOLD for guaranteed execution")
        print(f"Trade size: ${self.max_trade_amount}")
        print(f"Confidence threshold: {self.min_confidence*100}% (very low)")

    def generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.secret_key or '', encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()

    def get_headers(self, method: str, request_path: str, body: str = '') -> dict:
        timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key or '',
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase or '',
            'Content-Type': 'application/json'
        }

    def get_balance(self) -> float:
        try:
            path = '/api/v5/account/balance'
            headers = self.get_headers('GET', path)
            
            response = requests.get(self.base_url + path, headers=headers)
            data = response.json()
            
            if data.get('code') == '0':
                for detail in data['data'][0]['details']:
                    if detail['ccy'] == 'USDT':
                        return float(detail['availBal'])
            return 0.0
        except Exception as e:
            print(f"Balance error: {e}")
            return 0.0

    def analyze_simple_opportunity(self, symbol: str) -> dict:
        """Very simple analysis to ensure trade execution"""
        try:
            # Get ticker
            ticker_response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}')
            ticker_data = ticker_response.json()
            
            if not ticker_data.get('data'):
                return {'action': 'hold', 'confidence': 0.0}
                
            ticker = ticker_data['data'][0]
            change_24h = float(ticker.get('chg24h', '0'))
            volume_24h = float(ticker['vol24h'])
            price = float(ticker['last'])
            
            # Very liberal scoring for guaranteed execution
            confidence = 0.3  # Base confidence
            signals = []
            
            # Any volume gets points
            if volume_24h > 100000:
                signals.append("Has volume")
                confidence += 0.2
            
            # Any price movement gets points
            if abs(change_24h) > 0.1:
                signals.append("Price movement")
                confidence += 0.1
            
            # Always give some baseline confidence for active markets
            if volume_24h > 50000:
                signals.append("Active market")
                confidence += 0.1
            
            return {
                'action': 'buy' if confidence >= self.min_confidence else 'hold',
                'confidence': confidence,
                'signals': signals,
                'symbol': symbol,
                'price': price
            }
            
        except Exception as e:
            print(f"Analysis error for {symbol}: {e}")
            return {'action': 'hold', 'confidence': 0.0}

    def execute_micro_trade(self, symbol: str, amount: float) -> bool:
        """Execute a small trade"""
        try:
            # Get current price
            ticker_response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}')
            ticker_data = ticker_response.json()
            
            if not ticker_data.get('data'):
                return False
                
            current_price = float(ticker_data['data'][0]['last'])
            quantity = amount / current_price
            
            # Get minimum order size
            instrument_response = requests.get(f'{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}')
            if instrument_response.status_code == 200:
                instrument_data = instrument_response.json()
                if instrument_data.get('data'):
                    instrument = instrument_data['data'][0]
                    min_size = float(instrument.get('minSz', '0'))
                    lot_size = float(instrument.get('lotSz', '0'))
                    
                    if lot_size > 0:
                        quantity = round(quantity / lot_size) * lot_size
                    
                    if quantity < min_size:
                        print(f"Quantity {quantity:.8f} below minimum {min_size}")
                        return False
            
            # Place order
            order_data = {
                "instId": symbol,
                "tdMode": "cash",
                "side": "buy",
                "ordType": "market",
                "sz": str(quantity)
            }
            
            path = '/api/v5/trade/order'
            body = json.dumps(order_data)
            headers = self.get_headers('POST', path, body)
            
            response = requests.post(self.base_url + path, headers=headers, data=body)
            result = response.json()
            
            if result.get('code') == '0':
                order_id = result['data'][0]['ordId']
                self.trades_executed += 1
                
                print(f"\nAUTONOMOUS TRADE EXECUTED: {symbol}")
                print(f"Order ID: {order_id}")
                print(f"Quantity: {quantity:.6f}")
                print(f"Price: ${current_price:.6f}")
                print(f"Value: ${amount:.2f}")
                print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
                print(f"Total autonomous trades: {self.trades_executed}")
                
                return True
            else:
                error_msg = result.get('msg', 'Unknown error')
                print(f"Trade failed: {error_msg}")
                return False
                
        except Exception as e:
            print(f"Trade execution error: {e}")
            return False

    def run_autonomous_cycle(self):
        """Run one autonomous trading cycle with low threshold"""
        print(f"\n--- Autonomous Cycle {datetime.now().strftime('%H:%M:%S')} ---")
        
        balance = self.get_balance()
        print(f"Available USDT: ${balance:.2f}")
        
        if balance < 0.5:
            print("Insufficient balance")
            return False
        
        # Analyze pairs with low threshold
        for symbol in self.active_pairs:
            try:
                analysis = self.analyze_simple_opportunity(symbol)
                confidence = analysis.get('confidence', 0)
                
                print(f"{symbol}: {analysis['action']} (conf: {confidence:.2f})")
                
                if analysis['action'] == 'buy' and confidence >= self.min_confidence:
                    print(f"\nExecuting autonomous trade for {symbol}")
                    print(f"Confidence: {confidence:.2f}")
                    print(f"Signals: {', '.join(analysis.get('signals', []))}")
                    
                    trade_amount = min(self.max_trade_amount, balance - 0.1)
                    
                    if self.execute_micro_trade(symbol, trade_amount):
                        print("AUTONOMOUS TRADE SUCCESSFUL")
                        return True
                    
            except Exception as e:
                print(f"{symbol}: Error - {e}")
        
        print("No autonomous trades executed this cycle")
        return False

    def start_autonomous_trading(self, max_cycles=5):
        """Start autonomous trading with limited cycles for demonstration"""
        print("\n" + "="*60)
        print("AUTONOMOUS MICRO TRADING - DEMONSTRATION MODE")
        print("="*60)
        print("Low threshold trading to demonstrate autonomous execution")
        print(f"Will run {max_cycles} cycles maximum")
        print("="*60)
        
        self.running = True
        cycle_count = 0
        trades_made = 0
        
        try:
            while self.running and cycle_count < max_cycles:
                cycle_count += 1
                print(f"\n[Cycle {cycle_count}/{max_cycles}]")
                
                if self.run_autonomous_cycle():
                    trades_made += 1
                    print(f"Trades executed this session: {trades_made}")
                    
                    if trades_made >= 2:  # Stop after 2 autonomous trades
                        print("\nDemonstration complete - 2 autonomous trades executed")
                        break
                
                if cycle_count < max_cycles:
                    print("Next cycle in 30 seconds...")
                    time.sleep(30)
                
        except KeyboardInterrupt:
            print("\nStopped by user")
        finally:
            self.running = False
            print(f"\nSession complete:")
            print(f"Cycles: {cycle_count}")
            print(f"Autonomous trades: {trades_made}")

def main():
    bot = MicroTradingBot()
    bot.start_autonomous_trading()

if __name__ == "__main__":
    main()