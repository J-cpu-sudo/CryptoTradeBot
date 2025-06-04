#!/usr/bin/env python3
"""
Final Autonomous Trading Service - Optimized for successful execution
Handles minimum order requirements and executes trades every 4 minutes
"""
import os
import time
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone

class FinalAutonomousTrader:
    def __init__(self):
        self.api_key = os.environ.get('OKX_API_KEY')
        self.secret_key = os.environ.get('OKX_SECRET_KEY')
        self.passphrase = os.environ.get('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        self.last_trade_minute = -1
        self.trade_count = 0
        self.running = True
        
        # Trading pairs optimized for lower minimum requirements
        self.symbols = ['DOGE-USDT', 'TRX-USDT', 'SHIB-USDT']
        
        print("Final Autonomous Trading Service Initialized")
        print(f"API Key: {self.api_key[:8]}..." if self.api_key else "No API Key")
    
    def generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    def get_headers(self, method: str, request_path: str, body: str = '') -> dict:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def get_balance(self) -> float:
        try:
            path = '/api/v5/account/balance'
            headers = self.get_headers('GET', path)
            response = requests.get(self.base_url + path, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    for detail in data['data'][0]['details']:
                        if detail['ccy'] == 'USDT':
                            return float(detail['availBal'])
            return 0.0
        except Exception as e:
            print(f"Balance error: {e}")
            return 0.0
    
    def find_tradeable_symbol(self, balance: float) -> tuple:
        """Find a symbol that can be traded with available balance"""
        for symbol in self.symbols:
            try:
                # Get current price
                price_response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}', timeout=10)
                if price_response.status_code != 200:
                    continue
                    
                price_data = price_response.json()
                if not price_data.get('data'):
                    continue
                    
                current_price = float(price_data['data'][0]['last'])
                
                # Get instrument specifications
                inst_response = requests.get(f'{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}', timeout=10)
                if inst_response.status_code != 200:
                    continue
                    
                inst_data = inst_response.json()
                if not inst_data.get('data'):
                    continue
                    
                instrument = inst_data['data'][0]
                min_size = float(instrument.get('minSz', '0'))
                lot_size = float(instrument.get('lotSz', '0'))
                
                # Calculate maximum possible quantity with available balance
                max_trade_amount = balance * 0.9  # Use 90% of balance
                max_quantity = max_trade_amount / current_price
                
                if lot_size > 0:
                    max_quantity = int(max_quantity / lot_size) * lot_size
                
                if max_quantity >= min_size:
                    trade_amount = max_quantity * current_price
                    return symbol, current_price, max_quantity, trade_amount
                    
            except Exception as e:
                print(f"Error checking {symbol}: {e}")
                continue
        
        return None, 0, 0, 0
    
    def execute_trade(self, symbol: str, quantity: float, price: float, amount: float) -> bool:
        try:
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
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == '0':
                    order_id = result['data'][0]['ordId']
                    print("\n" + "="*60)
                    print("🚀 AUTONOMOUS TRADE EXECUTED SUCCESSFULLY!")
                    print(f"Order ID: {order_id}")
                    print(f"Symbol: {symbol}")
                    print(f"Quantity: {quantity:.6f}")
                    print(f"Price: ${price:.6f}")
                    print(f"Total Value: ${amount:.2f}")
                    print(f"Execution Time: {datetime.now().strftime('%H:%M:%S')}")
                    print("="*60 + "\n")
                    return True
                else:
                    print(f"Order failed: {result.get('msg', 'Unknown error')}")
            else:
                print(f"HTTP error: {response.status_code}")
            
            return False
            
        except Exception as e:
            print(f"Trade execution error: {e}")
            return False
    
    def autonomous_cycle(self):
        """Execute autonomous trading cycle"""
        current_time = datetime.now()
        current_minute = current_time.minute
        
        # Execute every 4 minutes
        if current_minute % 4 == 0 and current_minute != self.last_trade_minute:
            self.last_trade_minute = current_minute
            
            print(f"\n[{current_time.strftime('%H:%M:%S')}] Autonomous Trading Cycle #{self.trade_count + 1}")
            
            balance = self.get_balance()
            print(f"Available USDT: ${balance:.2f}")
            
            if balance > 0.1:
                symbol, price, quantity, amount = self.find_tradeable_symbol(balance)
                
                if symbol:
                    print(f"Selected: {symbol} - ${price:.6f} - Qty: {quantity:.6f}")
                    
                    if self.execute_trade(symbol, quantity, price, amount):
                        self.trade_count += 1
                        print(f"Total autonomous trades: {self.trade_count}")
                    else:
                        print("Trade execution failed")
                else:
                    print("No tradeable symbols found with current balance")
            else:
                print("Insufficient balance for trading")
    
    def run(self):
        """Main autonomous trading loop"""
        print("Starting Autonomous Trading Service")
        print("Trading every 4 minutes (at :00, :04, :08, :12, :16, :20, :24, :28, :32, :36, :40, :44, :48, :52, :56)")
        print("Press Ctrl+C to stop\n")
        
        while self.running:
            try:
                self.autonomous_cycle()
                time.sleep(30)  # Check every 30 seconds
            except KeyboardInterrupt:
                print("\nStopping autonomous trading service...")
                self.running = False
                break
            except Exception as e:
                print(f"Service error: {e}")
                time.sleep(60)

if __name__ == "__main__":
    trader = FinalAutonomousTrader()
    trader.run()