#!/usr/bin/env python3
"""
Autonomous Trading Daemon - Completely independent background service
Executes trades based on time intervals without any Flask dependencies
"""
import os
import time
import requests
import json
import hmac
import hashlib
import base64
import signal
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any

class AutonomousTradingDaemon:
    def __init__(self):
        # OKX API Configuration
        self.api_key = os.environ.get('OKX_API_KEY')
        self.secret_key = os.environ.get('OKX_SECRET_KEY')  
        self.passphrase = os.environ.get('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Trading state
        self.autonomous_trades = 0
        self.last_trade_minute = -1
        self.running = True
        self.trade_symbols = ['TRX-USDT', 'DOGE-USDT', 'ADA-USDT']
        
        # Validate credentials
        if not all([self.api_key, self.secret_key, self.passphrase]):
            self.log("ERROR: Missing OKX API credentials")
            sys.exit(1)
    
    def log(self, message: str):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()
    
    def generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """Generate OKX API signature"""
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    def get_headers(self, method: str, request_path: str, body: str = '') -> Dict[str, str]:
        """Get authenticated API headers"""
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def get_usdt_balance(self) -> float:
        """Get available USDT balance"""
        try:
            path = '/api/v5/account/balance'
            headers = self.get_headers('GET', path)
            response = requests.get(self.base_url + path, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0' and data.get('data'):
                    for detail in data['data'][0]['details']:
                        if detail['ccy'] == 'USDT':
                            return float(detail['availBal'])
            return 0.0
        except Exception as e:
            self.log(f"Balance error: {e}")
            return 0.0
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for symbol"""
        try:
            response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    return float(data['data'][0]['last'])
            return None
        except Exception as e:
            self.log(f"Price error for {symbol}: {e}")
            return None
    
    def get_instrument_info(self, symbol: str) -> Dict[str, float]:
        """Get trading instrument specifications"""
        try:
            response = requests.get(f'{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    instrument = data['data'][0]
                    return {
                        'min_size': float(instrument.get('minSz', '0')),
                        'lot_size': float(instrument.get('lotSz', '0'))
                    }
            return {'min_size': 0, 'lot_size': 0}
        except Exception as e:
            self.log(f"Instrument info error for {symbol}: {e}")
            return {'min_size': 0, 'lot_size': 0}
    
    def execute_market_buy(self, symbol: str, usdt_amount: float) -> bool:
        """Execute autonomous market buy order"""
        try:
            # Get current price
            current_price = self.get_current_price(symbol)
            if not current_price:
                self.log(f"Failed to get price for {symbol}")
                return False
            
            # Calculate quantity
            quantity = usdt_amount / current_price
            
            # Get instrument specifications
            instrument_info = self.get_instrument_info(symbol)
            min_size = instrument_info['min_size']
            lot_size = instrument_info['lot_size']
            
            # Adjust quantity to lot size
            if lot_size > 0:
                quantity = round(quantity / lot_size) * lot_size
            
            # Check minimum size
            if quantity < min_size:
                self.log(f"Quantity {quantity:.8f} below minimum {min_size} for {symbol}")
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
            
            response = requests.post(self.base_url + path, headers=headers, data=body, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == '0' and result.get('data'):
                    order_id = result['data'][0]['ordId']
                    self.log("=" * 60)
                    self.log("AUTONOMOUS TRADE EXECUTED SUCCESSFULLY")
                    self.log(f"Order ID: {order_id}")
                    self.log(f"Symbol: {symbol}")
                    self.log(f"Quantity: {quantity:.6f}")
                    self.log(f"Price: ${current_price:.6f}")
                    self.log(f"Value: ${usdt_amount:.2f}")
                    self.log("=" * 60)
                    return True
                else:
                    self.log(f"Order failed: {result.get('msg', 'Unknown error')}")
                    return False
            else:
                self.log(f"API request failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"Trade execution error: {e}")
            return False
    
    def should_trade_now(self) -> bool:
        """Check if it's time to execute a trade (every 4 minutes)"""
        current_time = datetime.now()
        current_minute = current_time.minute
        
        # Trade at minutes: 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56
        return (current_minute % 4 == 0 and current_minute != self.last_trade_minute)
    
    def select_trading_symbol(self) -> str:
        """Select trading symbol based on current hour"""
        hour = datetime.now().hour
        return self.trade_symbols[hour % len(self.trade_symbols)]
    
    def execute_trading_cycle(self):
        """Execute one autonomous trading cycle"""
        current_time = datetime.now()
        current_minute = current_time.minute
        
        if self.should_trade_now():
            self.last_trade_minute = current_minute
            
            self.log(f"AUTONOMOUS TRADING CYCLE - {current_time.strftime('%H:%M:%S')}")
            
            # Check balance
            balance = self.get_usdt_balance()
            self.log(f"Available USDT: ${balance:.2f}")
            
            if balance > 0.6:
                # Select symbol and amount
                symbol = self.select_trading_symbol()
                trade_amount = min(0.6, balance - 0.1)
                
                self.log(f"Selected: {symbol} for ${trade_amount:.2f}")
                
                # Execute trade
                if self.execute_market_buy(symbol, trade_amount):
                    self.autonomous_trades += 1
                    self.log(f"Total autonomous trades: {self.autonomous_trades}")
                else:
                    self.log("Trade execution failed")
            else:
                self.log("Insufficient balance for trading")
            
            self.log("")  # Empty line for readability
    
    def run(self):
        """Main daemon loop"""
        self.log("AUTONOMOUS TRADING DAEMON STARTED")
        self.log(f"API Key: {self.api_key[:8]}...")
        self.log(f"Trading symbols: {', '.join(self.trade_symbols)}")
        self.log("Trading schedule: Every 4 minutes (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56)")
        self.log("Daemon running independently...")
        self.log("")
        
        while self.running:
            try:
                self.execute_trading_cycle()
                time.sleep(30)  # Check every 30 seconds
            except KeyboardInterrupt:
                self.log("Received interrupt signal")
                self.stop()
                break
            except Exception as e:
                self.log(f"Daemon error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def stop(self):
        """Stop the daemon"""
        self.running = False
        self.log("AUTONOMOUS TRADING DAEMON STOPPED")

def signal_handler(signum, frame):
    """Handle termination signals"""
    daemon.stop()
    sys.exit(0)

# Global daemon instance
daemon = None

def main():
    """Main entry point"""
    global daemon
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run daemon
    daemon = AutonomousTradingDaemon()
    daemon.run()

if __name__ == "__main__":
    main()