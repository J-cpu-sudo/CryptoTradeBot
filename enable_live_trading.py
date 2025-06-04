#!/usr/bin/env python3
"""
Enable Live Trading - Background autonomous trading service
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
import signal
import sys

class BackgroundTradingService:
    """True autonomous trading service that runs in background"""
    
    def __init__(self):
        self.api_key = os.getenv('OKX_API_KEY')
        self.secret_key = os.getenv('OKX_SECRET_KEY')
        self.passphrase = os.getenv('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Trading configuration
        self.active_pairs = ['TRX-USDT', 'DOGE-USDT', 'ADA-USDT']
        self.trade_amount = 0.8  # $0.80 per trade
        self.confidence_threshold = 0.45  # 45% confidence
        self.cycle_interval = 120  # 2 minutes between cycles
        
        # State tracking
        self.running = False
        self.total_autonomous_trades = 0
        self.last_trade_time = None
        self.service_thread = None
        
        print(f"Background Trading Service initialized")
        print(f"Trade amount: ${self.trade_amount}")
        print(f"Cycle interval: {self.cycle_interval} seconds")

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
        """Get USDT balance"""
        try:
            path = '/api/v5/account/balance'
            headers = self.get_headers('GET', path)
            
            response = requests.get(self.base_url + path, headers=headers, timeout=10)
            data = response.json()
            
            if data.get('code') == '0':
                for detail in data['data'][0]['details']:
                    if detail['ccy'] == 'USDT':
                        return float(detail['availBal'])
            return 0.0
        except Exception as e:
            print(f"Balance error: {e}")
            return 0.0

    def analyze_market(self, symbol: str) -> dict:
        """Simple market analysis for autonomous trading"""
        try:
            # Get market data
            ticker_response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}', timeout=10)
            ticker_data = ticker_response.json()
            
            if not ticker_data.get('data'):
                return {'trade': False, 'confidence': 0.0}
                
            ticker = ticker_data['data'][0]
            volume_24h = float(ticker['vol24h'])
            change_24h = float(ticker.get('chg24h', '0'))
            price = float(ticker['last'])
            
            # Simple scoring system
            confidence = 0.2  # Base confidence
            reasons = []
            
            # Volume check
            if volume_24h > 500000:
                confidence += 0.15
                reasons.append("Good volume")
            
            # Price movement check
            if abs(change_24h) > 0.5:
                confidence += 0.1
                reasons.append("Price volatility")
            
            # Market activity check
            if volume_24h > 100000:
                confidence += 0.1
                reasons.append("Market active")
            
            # Time-based boost for demonstration
            current_hour = datetime.now().hour
            if current_hour % 2 == 0:  # Every even hour
                confidence += 0.15
                reasons.append("Time cycle")
            
            return {
                'trade': confidence >= self.confidence_threshold,
                'confidence': confidence,
                'price': price,
                'reasons': reasons,
                'symbol': symbol
            }
            
        except Exception as e:
            print(f"Analysis error for {symbol}: {e}")
            return {'trade': False, 'confidence': 0.0}

    def execute_autonomous_trade(self, symbol: str, amount: float) -> bool:
        """Execute trade autonomously"""
        try:
            # Get current price
            ticker_response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}', timeout=10)
            ticker_data = ticker_response.json()
            
            if not ticker_data.get('data'):
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
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Quantity too small for {symbol}")
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
            result = response.json()
            
            if result.get('code') == '0':
                order_id = result['data'][0]['ordId']
                self.total_autonomous_trades += 1
                self.last_trade_time = datetime.now()
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] AUTONOMOUS TRADE EXECUTED")
                print(f"Symbol: {symbol}")
                print(f"Order ID: {order_id}")
                print(f"Quantity: {quantity:.6f}")
                print(f"Price: ${current_price:.6f}")
                print(f"Value: ${amount:.2f}")
                print(f"Total autonomous trades: {self.total_autonomous_trades}")
                
                return True
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Trade failed: {result.get('msg', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Trade execution error: {e}")
            return False

    def trading_cycle(self):
        """Execute one autonomous trading cycle"""
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === Autonomous Trading Cycle ===")
            
            # Check balance
            balance = self.get_balance()
            print(f"Available USDT: ${balance:.2f}")
            
            if balance < 0.5:
                print("Insufficient balance for trading")
                return
            
            # Analyze markets
            best_opportunity = None
            best_confidence = 0
            
            for symbol in self.active_pairs:
                analysis = self.analyze_market(symbol)
                confidence = analysis.get('confidence', 0)
                
                print(f"{symbol}: {confidence:.2f} confidence")
                
                if analysis.get('trade') and confidence > best_confidence:
                    best_opportunity = analysis
                    best_confidence = confidence
            
            # Execute best opportunity
            if best_opportunity:
                symbol = best_opportunity['symbol']
                print(f"\nExecuting autonomous trade: {symbol}")
                print(f"Confidence: {best_confidence:.2f}")
                print(f"Reasons: {', '.join(best_opportunity.get('reasons', []))}")
                
                trade_amount = min(self.trade_amount, balance - 0.1)
                self.execute_autonomous_trade(symbol, trade_amount)
            else:
                print("No trading opportunities found")
                
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cycle error: {e}")

    def background_service(self):
        """Background trading service loop"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Background trading service started")
        print("This service runs independently of user interactions")
        print("Press Ctrl+C to stop")
        
        cycle_count = 0
        
        while self.running:
            try:
                cycle_count += 1
                print(f"\n[Cycle {cycle_count}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                self.trading_cycle()
                
                if not self.running:
                    break
                
                print(f"Next cycle in {self.cycle_interval} seconds...")
                
                # Sleep with periodic checks for stop signal
                for _ in range(self.cycle_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Service error: {e}")
                time.sleep(30)  # Wait before retrying
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Background trading service stopped")
        print(f"Total autonomous trades executed: {self.total_autonomous_trades}")

    def start_service(self):
        """Start the background trading service"""
        if self.running:
            print("Service already running")
            return
        
        self.running = True
        self.service_thread = threading.Thread(target=self.background_service, daemon=True)
        self.service_thread.start()
        
        print("Background trading service started in separate thread")
        return self.service_thread

    def stop_service(self):
        """Stop the background trading service"""
        if not self.running:
            print("Service not running")
            return
        
        print("Stopping background trading service...")
        self.running = False
        
        if self.service_thread and self.service_thread.is_alive():
            self.service_thread.join(timeout=5)
        
        print("Background trading service stopped")

    def get_status(self):
        """Get service status"""
        return {
            'running': self.running,
            'total_trades': self.total_autonomous_trades,
            'last_trade': self.last_trade_time.strftime('%H:%M:%S') if self.last_trade_time else 'None',
            'thread_alive': self.service_thread.is_alive() if self.service_thread else False
        }

# Global service instance
trading_service = BackgroundTradingService()

def signal_handler(signum, frame):
    """Handle interrupt signals"""
    print("\nReceived interrupt signal")
    trading_service.stop_service()
    sys.exit(0)

def main():
    """Main function to run the service"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting autonomous trading service...")
    trading_service.start_service()
    
    try:
        # Keep main thread alive
        while trading_service.running:
            time.sleep(10)
            status = trading_service.get_status()
            if not status['thread_alive'] and status['running']:
                print("Service thread died, restarting...")
                trading_service.start_service()
    except KeyboardInterrupt:
        trading_service.stop_service()

if __name__ == "__main__":
    main()