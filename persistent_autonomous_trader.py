#!/usr/bin/env python3
"""
Persistent Autonomous Trading Engine - Continuous 24/7 Operation
Self-healing, error-resistant, and fully autonomous execution
"""
import os
import time
import requests
import json
import hmac
import hashlib
import base64
import threading
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

class PersistentAutonomousTrader:
    def __init__(self):
        self.api_key = os.environ.get('OKX_API_KEY')
        self.secret_key = os.environ.get('OKX_SECRET_KEY')
        self.passphrase = os.environ.get('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Persistent operation flags
        self.running = True
        self.force_run = True
        self.last_execution_minute = -1
        self.trade_count = 0
        self.error_count = 0
        self.last_balance_check = 0
        self.cached_balance = 0.0
        
        # Trading configuration - optimized for low minimum orders
        self.trading_pairs = [
            'DOGE-USDT',  # Very low minimum
            'TRX-USDT',   # Low minimum
            'SHIB-USDT',  # Micro amounts
            'PEPE-USDT',  # Meme coin with low min
            'BONK-USDT'   # Another low minimum option
        ]
        
        # Error handling and resilience
        self.max_consecutive_errors = 10
        self.retry_delay = 30
        self.health_check_interval = 60
        
        print(f"[{self.get_timestamp()}] Persistent Autonomous Trader Initialized")
        print(f"API Status: {'Connected' if self.api_key else 'Missing Keys'}")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def get_timestamp(self) -> str:
        return datetime.now().strftime('%H:%M:%S')
    
    def signal_handler(self, signum, frame):
        print(f"\n[{self.get_timestamp()}] Shutdown signal received. Stopping...")
        self.running = False
        sys.exit(0)
    
    def generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    def get_headers(self, method: str, request_path: str, body: str = '') -> Dict[str, str]:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def safe_request(self, method: str, url: str, headers: Dict[str, str] = None, 
                    data: str = None, timeout: int = 10) -> Optional[requests.Response]:
        """Safe request with error handling and retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, headers=headers, timeout=timeout)
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=headers, data=data, timeout=timeout)
                else:
                    return None
                
                if response.status_code in [200, 201]:
                    return response
                elif response.status_code == 429:  # Rate limit
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return response
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"[{self.get_timestamp()}] Request failed after {max_retries} attempts: {e}")
                    return None
                time.sleep(1)
        return None
    
    def get_balance_cached(self) -> float:
        """Get balance with caching to avoid rate limits"""
        current_time = time.time()
        if current_time - self.last_balance_check < 30:  # Cache for 30 seconds
            return self.cached_balance
        
        try:
            path = '/api/v5/account/balance'
            headers = self.get_headers('GET', path)
            response = self.safe_request('GET', self.base_url + path, headers)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    for detail in data['data'][0]['details']:
                        if detail['ccy'] == 'USDT':
                            self.cached_balance = float(detail['availBal'])
                            self.last_balance_check = current_time
                            return self.cached_balance
            
            # If request fails, try funding account
            path = '/api/v5/asset/balances'
            headers = self.get_headers('GET', path)
            response = self.safe_request('GET', self.base_url + path, headers)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    for detail in data.get('data', []):
                        if detail['ccy'] == 'USDT':
                            self.cached_balance = float(detail['availBal'])
                            self.last_balance_check = current_time
                            return self.cached_balance
            
            return self.cached_balance  # Return cached if both fail
            
        except Exception as e:
            print(f"[{self.get_timestamp()}] Balance check error: {e}")
            return self.cached_balance
    
    def find_optimal_trading_pair(self, balance: float) -> Tuple[Optional[str], float, float, float]:
        """Find the best trading pair for current balance"""
        for symbol in self.trading_pairs:
            try:
                # Get current price
                response = self.safe_request('GET', f'{self.base_url}/api/v5/market/ticker?instId={symbol}')
                if not response or response.status_code != 200:
                    continue
                
                price_data = response.json()
                if not price_data.get('data'):
                    continue
                
                current_price = float(price_data['data'][0]['last'])
                
                # Get instrument info
                response = self.safe_request('GET', f'{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}')
                if not response or response.status_code != 200:
                    continue
                
                inst_data = response.json()
                if not inst_data.get('data'):
                    continue
                
                instrument = inst_data['data'][0]
                min_size = float(instrument.get('minSz', '0'))
                lot_size = float(instrument.get('lotSz', '0'))
                
                # Calculate optimal trade size (use 85% of balance for safety)
                trade_amount = balance * 0.85
                max_quantity = trade_amount / current_price
                
                # Adjust for lot size
                if lot_size > 0:
                    max_quantity = int(max_quantity / lot_size) * lot_size
                
                # Check if we can meet minimum requirements
                if max_quantity >= min_size and trade_amount >= 1.0:  # Minimum $1 trade
                    final_amount = max_quantity * current_price
                    return symbol, current_price, max_quantity, final_amount
                
            except Exception as e:
                print(f"[{self.get_timestamp()}] Error analyzing {symbol}: {e}")
                continue
        
        return None, 0, 0, 0
    
    def execute_autonomous_trade(self, symbol: str, quantity: float, price: float, amount: float) -> bool:
        """Execute trade with comprehensive error handling"""
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
            
            response = self.safe_request('POST', self.base_url + path, headers, body)
            
            if response and response.status_code == 200:
                result = response.json()
                if result.get('code') == '0':
                    order_id = result['data'][0]['ordId']
                    print(f"\n[{self.get_timestamp()}] ✅ AUTONOMOUS TRADE EXECUTED!")
                    print(f"Order ID: {order_id}")
                    print(f"Pair: {symbol} | Qty: {quantity:.6f} | Price: ${price:.6f}")
                    print(f"Value: ${amount:.2f} | Trade #{self.trade_count + 1}")
                    
                    # Reset error count on successful trade
                    self.error_count = 0
                    return True
                else:
                    print(f"[{self.get_timestamp()}] Trade rejected: {result.get('msg', 'Unknown error')}")
            else:
                status = response.status_code if response else "No response"
                print(f"[{self.get_timestamp()}] Trade failed - HTTP {status}")
            
            return False
            
        except Exception as e:
            print(f"[{self.get_timestamp()}] Trade execution error: {e}")
            return False
    
    def autonomous_trading_cycle(self) -> bool:
        """Execute one autonomous trading cycle"""
        try:
            current_time = datetime.now()
            current_minute = current_time.minute
            
            # Execute every 4 minutes: 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56
            if current_minute % 4 == 0 and current_minute != self.last_execution_minute:
                self.last_execution_minute = current_minute
                
                print(f"\n[{self.get_timestamp()}] 🔄 Autonomous Cycle #{self.trade_count + 1}")
                
                # Get current balance
                balance = self.get_balance_cached()
                print(f"Available Balance: ${balance:.2f} USDT")
                
                if balance < 0.5:  # Minimum threshold
                    print(f"[{self.get_timestamp()}] Insufficient balance for trading")
                    return True  # Continue running
                
                # Find optimal trading pair
                symbol, price, quantity, amount = self.find_optimal_trading_pair(balance)
                
                if symbol:
                    print(f"Selected: {symbol} | ${price:.6f} | Qty: {quantity:.6f} | Value: ${amount:.2f}")
                    
                    # Execute trade
                    if self.execute_autonomous_trade(symbol, quantity, price, amount):
                        self.trade_count += 1
                        print(f"[{self.get_timestamp()}] Total autonomous trades: {self.trade_count}")
                        
                        # Update balance cache after successful trade
                        self.cached_balance = 0  # Force refresh on next check
                        
                    else:
                        self.error_count += 1
                        print(f"[{self.get_timestamp()}] Trade failed - Error count: {self.error_count}")
                else:
                    print(f"[{self.get_timestamp()}] No suitable trading pairs found")
                
                return True
            
            return True  # Continue running
            
        except Exception as e:
            print(f"[{self.get_timestamp()}] Cycle error: {e}")
            self.error_count += 1
            return self.error_count < self.max_consecutive_errors
    
    def health_monitor(self):
        """Background health monitoring"""
        while self.running:
            try:
                # Basic health check
                if self.error_count >= self.max_consecutive_errors:
                    print(f"[{self.get_timestamp()}] ⚠️ High error count - Resetting")
                    self.error_count = 0
                    time.sleep(self.retry_delay)
                
                # Check if we're still getting market data
                response = self.safe_request('GET', f'{self.base_url}/api/v5/market/ticker?instId=BTC-USDT')
                if response and response.status_code == 200:
                    data = response.json()
                    if data.get('data'):
                        btc_price = float(data['data'][0]['last'])
                        print(f"[{self.get_timestamp()}] Health Check OK - BTC: ${btc_price:,.2f}")
                
                time.sleep(self.health_check_interval)
                
            except Exception as e:
                print(f"[{self.get_timestamp()}] Health monitor error: {e}")
                time.sleep(30)
    
    def run_persistent(self):
        """Main persistent trading loop"""
        print(f"[{self.get_timestamp()}] 🚀 Starting Persistent Autonomous Trading")
        print("Schedule: Every 4 minutes (00, 04, 08, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56)")
        print("Mode: Continuous 24/7 operation with self-healing")
        print("Press Ctrl+C to stop gracefully\n")
        
        # Start health monitor in background
        health_thread = threading.Thread(target=self.health_monitor, daemon=True)
        health_thread.start()
        
        cycle_count = 0
        
        while self.running and self.force_run:
            try:
                # Execute trading cycle
                if not self.autonomous_trading_cycle():
                    print(f"[{self.get_timestamp()}] Too many errors - Restarting in {self.retry_delay}s")
                    time.sleep(self.retry_delay)
                    self.error_count = 0  # Reset after cooldown
                
                cycle_count += 1
                
                # Log status every 100 cycles
                if cycle_count % 100 == 0:
                    print(f"[{self.get_timestamp()}] Status: {cycle_count} cycles, {self.trade_count} trades, {self.error_count} errors")
                
                # Sleep for 30 seconds before next check
                time.sleep(30)
                
            except KeyboardInterrupt:
                print(f"\n[{self.get_timestamp()}] Graceful shutdown requested...")
                break
            except Exception as e:
                print(f"[{self.get_timestamp()}] Main loop error: {e}")
                self.error_count += 1
                time.sleep(self.retry_delay)
        
        print(f"[{self.get_timestamp()}] Autonomous trading stopped. Total trades: {self.trade_count}")

def main():
    """Main entry point"""
    try:
        trader = PersistentAutonomousTrader()
        trader.run_persistent()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()