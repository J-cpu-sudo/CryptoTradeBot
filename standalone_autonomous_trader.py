#!/usr/bin/env python3
"""
Standalone Autonomous Trading Service
Operates completely independently without Flask context dependencies
"""
import os
import time
import requests
import json
import hmac
import hashlib
import base64
import sys
from datetime import datetime, timezone
import threading
import signal

class StandaloneAutonomousTrader:
    def __init__(self):
        self.api_key = os.environ.get('OKX_API_KEY')
        self.secret_key = os.environ.get('OKX_SECRET_KEY')
        self.passphrase = os.environ.get('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        self.autonomous_trades = 0
        self.last_trade_minute = -1
        self.running = True
        
        # Validate API credentials
        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("ERROR: Missing OKX API credentials")
            sys.exit(1)
    
    def generate_signature(self, timestamp, method, request_path, body=''):
        """Generate OKX API signature"""
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    def get_headers(self, method, request_path, body=''):
        """Get authenticated headers"""
        timestamp = datetime.now(timezone.utc).isoformat()[:-9] + 'Z'
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def get_balance(self):
        """Get USDT balance"""
        try:
            path = '/api/v5/account/balance'
            headers = self.get_headers('GET', path)
            response = requests.get(self.base_url + path, headers=headers, timeout=10)
            data = response.json()
            
            if data.get('code') == '0' and data.get('data'):
                for detail in data['data'][0]['details']:
                    if detail['ccy'] == 'USDT':
                        return float(detail['availBal'])
            return 0.0
        except Exception as e:
            print(f"Balance check error: {e}")
            return 0.0
    
    def execute_trade(self, symbol, amount):
        """Execute autonomous trade"""
        try:
            # Get current price
            ticker_response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}', timeout=10)
            ticker_data = ticker_response.json()
            
            if not ticker_data.get('data'):
                print(f"Failed to get price for {symbol}")
                return False
            
            current_price = float(ticker_data['data'][0]['last'])
            quantity = amount / current_price
            
            # Get instrument specifications
            instrument_response = requests.get(f'{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}', timeout=10)
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
            
            # Place market buy order
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
            
            response = requests.post(self.base_url + path, headers=headers, data=body, timeout=10)
            result = response.json()
            
            if result.get('code') == '0' and result.get('data'):
                order_id = result['data'][0]['ordId']
                print(f"[AUTONOMOUS TRADE EXECUTED]")
                print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Order ID: {order_id}")
                print(f"Symbol: {symbol}")
                print(f"Quantity: {quantity:.6f}")
                print(f"Price: ${current_price:.6f}")
                print(f"Value: ${amount:.2f}")
                print("-" * 50)
                return True
            else:
                print(f"Trade failed: {result.get('msg', 'Unknown error')}")
                print(f"Full response: {result}")
                return False
                
        except Exception as e:
            print(f"Trade execution error: {e}")
            return False
    
    def trading_cycle(self):
        """Execute one trading cycle"""
        current_time = datetime.now()
        current_minute = current_time.minute
        
        # Trade every 4 minutes (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56)
        if current_minute % 4 == 0 and current_minute != self.last_trade_minute:
            self.last_trade_minute = current_minute
            
            print(f"[AUTONOMOUS CYCLE] {current_time.strftime('%H:%M:%S')}")
            
            balance = self.get_balance()
            print(f"USDT Balance: ${balance:.2f}")
            
            if balance > 0.6:
                # Time-based symbol selection for autonomy
                hour = current_time.hour
                symbols = ['TRX-USDT', 'DOGE-USDT', 'ADA-USDT']
                symbol = symbols[hour % len(symbols)]
                
                trade_amount = min(0.6, balance - 0.1)
                
                print(f"Attempting autonomous trade: {symbol} for ${trade_amount:.2f}")
                
                if self.execute_trade(symbol, trade_amount):
                    self.autonomous_trades += 1
                    print(f"Total autonomous trades: {self.autonomous_trades}")
                else:
                    print("Trade execution failed")
            else:
                print("Insufficient balance for trading")
            
            print()
    
    def run_continuous(self):
        """Run continuous autonomous trading"""
        print("Starting Standalone Autonomous Trading Service")
        print(f"API Key: {self.api_key[:8]}...")
        print(f"Trading every 4 minutes (at minutes 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56)")
        print("=" * 60)
        
        while self.running:
            try:
                self.trading_cycle()
                time.sleep(30)  # Check every 30 seconds
            except KeyboardInterrupt:
                print("Stopping autonomous trading...")
                self.running = False
                break
            except Exception as e:
                print(f"Service error: {e}")
                time.sleep(60)
    
    def stop(self):
        """Stop the trading service"""
        self.running = False

def signal_handler(signum, frame):
    """Handle interrupt signals"""
    print("Received interrupt signal. Stopping autonomous trading...")
    trader.stop()
    sys.exit(0)

# Global trader instance
trader = None

def main():
    """Main function"""
    global trader
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    trader = StandaloneAutonomousTrader()
    trader.run_continuous()

if __name__ == "__main__":
    main()