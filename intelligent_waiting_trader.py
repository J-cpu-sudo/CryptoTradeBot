#!/usr/bin/env python3
"""
Intelligent Waiting Trader - Monitors for trading windows when account restrictions lift
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

class IntelligentWaitingTrader:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Trading parameters
        self.profit_target = 0.015  # 1.5% profit
        self.stop_loss = -0.02      # 2% stop
        self.max_hold_time = 180    # 3 minutes
        
        # Known working symbol
        self.symbol = 'TRX-USDT'
        
        self.active_position = None
        self.last_successful_trade = None
        self.total_attempts = 0
        self.successful_trades = 0
        
        print("INTELLIGENT WAITING TRADER - MONITORING FOR TRADING WINDOWS")
    
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
    
    def get_headers(self, method: str, path: str, body: str = '') -> dict:
        timestamp = self.get_timestamp()
        signature = self.create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def api_request(self, method: str, endpoint: str, body: str = None):
        try:
            headers = self.get_headers(method, endpoint, body or '')
            url = self.base_url + endpoint
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            
            return None
        except Exception:
            return None
    
    def get_balance(self) -> float:
        data = self.api_request('GET', '/api/v5/account/balance')
        if data and data.get('code') == '0':
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    return float(detail['availBal'])
        return 0.0
    
    def format_quantity(self, quantity: float, lot_size: str) -> str:
        lot_decimal = Decimal(lot_size)
        quantity_decimal = Decimal(str(quantity))
        formatted = quantity_decimal.quantize(lot_decimal, rounding=ROUND_DOWN)
        return str(formatted.normalize())
    
    def test_trading_capability(self) -> dict:
        """Test if we can place orders by attempting a small trade"""
        # Get current price
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={self.symbol}')
        if not ticker or ticker.get('code') != '0':
            return {'can_trade': False, 'reason': 'Failed to get price'}
        
        price = float(ticker['data'][0]['last'])
        
        # Get instrument specs
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={self.symbol}')
        if not inst_data or inst_data.get('code') != '0':
            return {'can_trade': False, 'reason': 'Failed to get instrument data'}
        
        inst_info = inst_data['data'][0]
        min_size = float(inst_info['minSz'])
        lot_size = inst_info['lotSz']
        
        # Test with small amount
        test_usdt = 2.0
        raw_quantity = test_usdt / price
        
        if raw_quantity < min_size:
            return {'can_trade': False, 'reason': f'Minimum size {min_size} too high'}
        
        formatted_quantity = self.format_quantity(raw_quantity, lot_size)
        
        # Test order
        order_data = {
            "instId": self.symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": formatted_quantity
        }
        
        order_body = json.dumps(order_data)
        result = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if result and result.get('code') == '0':
            # Success! We have a trading window
            order_id = result['data'][0]['ordId']
            
            self.active_position = {
                'symbol': self.symbol,
                'quantity': float(formatted_quantity),
                'entry_price': price,
                'entry_time': time.time(),
                'order_id': order_id,
                'invested': test_usdt
            }
            
            self.successful_trades += 1
            self.last_successful_trade = time.time()
            
            return {
                'can_trade': True, 
                'order_id': order_id,
                'quantity': formatted_quantity,
                'price': price
            }
        else:
            error_msg = 'Unknown error'
            if result and result.get('data') and result['data'][0].get('sMsg'):
                error_msg = result['data'][0]['sMsg']
            elif result and result.get('msg'):
                error_msg = result['msg']
            
            return {'can_trade': False, 'reason': error_msg}
    
    def sell_position(self) -> bool:
        """Sell active position"""
        if not self.active_position:
            return False
        
        symbol = self.active_position['symbol']
        quantity = self.active_position['quantity']
        
        # Get instrument specs
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data or inst_data.get('code') != '0':
            return False
        
        lot_size = inst_data['data'][0]['lotSz']
        formatted_quantity = self.format_quantity(quantity, lot_size)
        
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "sell",
            "ordType": "market",
            "sz": formatted_quantity
        }
        
        order_body = json.dumps(order_data)
        result = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if result and result.get('code') == '0':
            order_id = result['data'][0]['ordId']
            
            # Calculate P&L
            current_ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
            if current_ticker and current_ticker.get('code') == '0':
                current_price = float(current_ticker['data'][0]['last'])
                pnl_pct = (current_price - self.active_position['entry_price']) / self.active_position['entry_price']
                
                print(f"✓ SELL SUCCESS: {symbol} - P&L: {pnl_pct*100:.2f}%")
                print(f"Sell Order ID: {order_id}")
            
            self.active_position = None
            return True
        else:
            print(f"✗ SELL FAILED: {symbol}")
            return False
    
    def manage_position(self):
        """Monitor and manage active position"""
        if not self.active_position:
            return
        
        symbol = self.active_position['symbol']
        current_time = time.time()
        
        # Get current price
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker or ticker.get('code') != '0':
            return
        
        current_price = float(ticker['data'][0]['last'])
        pnl_pct = (current_price - self.active_position['entry_price']) / self.active_position['entry_price']
        hold_time = current_time - self.active_position['entry_time']
        
        should_close = False
        reason = ""
        
        if pnl_pct >= self.profit_target:
            should_close = True
            reason = f"PROFIT TARGET {pnl_pct*100:.2f}%"
        elif pnl_pct <= self.stop_loss:
            should_close = True
            reason = f"STOP LOSS {pnl_pct*100:.2f}%"
        elif hold_time > self.max_hold_time:
            should_close = True
            reason = f"TIME LIMIT {hold_time/60:.1f}min"
        
        if should_close:
            print(f"CLOSING POSITION: {reason}")
            self.sell_position()
    
    def monitor_and_trade(self):
        """Main monitoring loop"""
        cycle_time = datetime.now().strftime('%H:%M:%S')
        print(f"\n=== MONITORING CYCLE - {cycle_time} ===")
        
        balance = self.get_balance()
        self.total_attempts += 1
        
        # Show status
        success_rate = (self.successful_trades / max(self.total_attempts, 1)) * 100
        print(f"Balance: ${balance:.3f} | Attempts: {self.total_attempts} | Success: {self.successful_trades} ({success_rate:.1f}%)")
        
        if self.last_successful_trade:
            time_since_last = (time.time() - self.last_successful_trade) / 60
            print(f"Last successful trade: {time_since_last:.1f} minutes ago")
        
        # Manage existing position
        if self.active_position:
            self.manage_position()
            return
        
        # Test for trading window
        if balance >= 2.0:
            print("Testing trading capability...")
            test_result = self.test_trading_capability()
            
            if test_result['can_trade']:
                print(f"✓ TRADING WINDOW OPEN!")
                print(f"Order ID: {test_result['order_id']}")
                print(f"Bought {test_result['quantity']} {self.symbol} @ ${test_result['price']:.6f}")
            else:
                print(f"✗ Trading restricted: {test_result['reason']}")
        else:
            print(f"Insufficient balance: ${balance:.3f}")
    
    def run_intelligent_trader(self):
        """Main trading loop"""
        print("INTELLIGENT WAITING TRADER")
        print("Monitoring for trading windows when account restrictions lift")
        print("Will execute immediately when conditions allow")
        print("=" * 60)
        
        while True:
            try:
                self.monitor_and_trade()
                
                # Adaptive timing
                if self.active_position:
                    wait_time = 8   # Fast monitoring with position
                else:
                    wait_time = 30  # Regular monitoring for trading windows
                
                print(f"Next monitoring cycle in {wait_time} seconds...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("\nIntelligent trader stopped by user")
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(30)

def main():
    trader = IntelligentWaitingTrader()
    trader.run_intelligent_trader()

if __name__ == "__main__":
    main()