#!/usr/bin/env python3
"""
Precision Autonomous Trader - Uses exact working format from successful TRX trade
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

class PrecisionAutonomousTrader:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Trading parameters based on successful TRX trade
        self.profit_target = 0.012  # 1.2% profit
        self.stop_loss = -0.018     # 1.8% stop
        self.max_hold_time = 150    # 2.5 minutes
        
        # Focus on TRX-USDT since it has proven execution
        self.primary_symbol = 'TRX-USDT'
        self.backup_symbols = ['DOGE-USDT', 'SHIB-USDT']
        
        self.active_position = None
        self.trades_completed = 0
        self.total_pnl = 0.0
        
        print("PRECISION AUTONOMOUS TRADER - PROVEN EXECUTION")
    
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
                response = requests.get(url, headers=headers, timeout=8)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=8)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    return data
            
            return None
        except Exception:
            return None
    
    def get_balance(self) -> float:
        data = self.api_request('GET', '/api/v5/account/balance')
        if data:
            for detail in data['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    return float(detail['availBal'])
        return 0.0
    
    def format_quantity(self, quantity: float, lot_size: str) -> str:
        """Use exact formatting that worked in successful TRX trade"""
        lot_decimal = Decimal(lot_size)
        quantity_decimal = Decimal(str(quantity))
        formatted = quantity_decimal.quantize(lot_decimal, rounding=ROUND_DOWN)
        return str(formatted.normalize())
    
    def get_max_buy_usdt(self, symbol: str) -> float:
        """Get maximum USDT amount we can spend on this symbol"""
        max_data = self.api_request('GET', f'/api/v5/account/max-size?instId={symbol}&tdMode=cash')
        if max_data and max_data['data']:
            max_buy_usdt = float(max_data['data'][0]['maxBuy'])
            current_balance = self.get_balance()
            
            # Use the smaller of max_buy or current balance, with buffer
            usable_amount = min(max_buy_usdt, current_balance * 0.75)
            return max(usable_amount, 0)
        return 0.0
    
    def should_trade(self, symbol: str) -> bool:
        """Simple momentum check"""
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker:
            return False
        
        data = ticker['data'][0]
        change_24h = float(data['sodUtc8'])
        
        # Trade on any positive momentum
        return change_24h > 0
    
    def execute_precision_buy(self, symbol: str) -> bool:
        """Execute buy using exact format from successful TRX trade"""
        print(f"PRECISION BUY: {symbol}")
        
        # Get maximum usable amount
        usdt_amount = self.get_max_buy_usdt(symbol)
        
        if usdt_amount < 2.0:
            print(f"Insufficient amount: ${usdt_amount:.3f}")
            return False
        
        # Get current price
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker:
            print("Failed to get ticker")
            return False
        
        price = float(ticker['data'][0]['last'])
        
        # Get instrument specs
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data:
            print("Failed to get instrument data")
            return False
        
        inst_info = inst_data['data'][0]
        min_size = float(inst_info['minSz'])
        lot_size = inst_info['lotSz']
        
        # Calculate quantity using successful method
        raw_quantity = usdt_amount / price
        
        if raw_quantity < min_size:
            print(f"Quantity {raw_quantity:.8f} below minimum {min_size}")
            return False
        
        # Use exact format that worked
        formatted_quantity = self.format_quantity(raw_quantity, lot_size)
        
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": formatted_quantity
        }
        
        order_body = json.dumps(order_data)
        print(f"Order payload: {order_body}")
        
        result = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if result and result.get('data'):
            order_id = result['data'][0]['ordId']
            
            self.active_position = {
                'symbol': symbol,
                'quantity': float(formatted_quantity),
                'entry_price': price,
                'entry_time': time.time(),
                'order_id': order_id,
                'invested': usdt_amount
            }
            
            print(f"✓ BUY SUCCESS: {symbol} - {formatted_quantity} @ ${price:.6f}")
            print(f"Order ID: {order_id}")
            return True
        else:
            error_msg = result.get('msg', 'Unknown error') if result else 'Request failed'
            print(f"✗ BUY FAILED: {symbol} - {error_msg}")
            return False
    
    def execute_precision_sell(self) -> bool:
        """Execute sell for active position"""
        if not self.active_position:
            return False
        
        symbol = self.active_position['symbol']
        quantity = self.active_position['quantity']
        
        print(f"PRECISION SELL: {symbol} - {quantity}")
        
        # Get instrument specs for formatting
        inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_data:
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
        
        if result and result.get('data'):
            order_id = result['data'][0]['ordId']
            
            # Calculate P&L
            current_ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
            if current_ticker:
                current_price = float(current_ticker['data'][0]['last'])
                pnl_pct = (current_price - self.active_position['entry_price']) / self.active_position['entry_price']
                pnl_usd = pnl_pct * self.active_position['invested']
                
                self.total_pnl += pnl_usd
                self.trades_completed += 1
                
                print(f"✓ SELL SUCCESS: {symbol} - {formatted_quantity}")
                print(f"P&L: {pnl_pct*100:.2f}% (${pnl_usd:.3f})")
                print(f"Order ID: {order_id}")
            
            self.active_position = None
            return True
        else:
            error_msg = result.get('msg', 'Unknown error') if result else 'Request failed'
            print(f"✗ SELL FAILED: {symbol} - {error_msg}")
            return False
    
    def manage_position(self):
        """Manage active position with precision timing"""
        if not self.active_position:
            return
        
        symbol = self.active_position['symbol']
        current_time = time.time()
        
        # Get current price
        ticker = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker:
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
            self.execute_precision_sell()
    
    def run_precision_cycle(self):
        """Execute one precision trading cycle"""
        cycle_time = datetime.now().strftime('%H:%M:%S')
        print(f"\n=== PRECISION CYCLE - {cycle_time} ===")
        
        balance = self.get_balance()
        win_rate = (self.trades_completed / max(1, self.trades_completed)) * 100 if self.trades_completed > 0 else 0
        
        print(f"Balance: ${balance:.3f} | Trades: {self.trades_completed} | P&L: ${self.total_pnl:.3f}")
        
        # Manage existing position
        self.manage_position()
        
        # Look for new opportunity if no position
        if not self.active_position and balance >= 2.0:
            # Try primary symbol first (TRX-USDT)
            if self.should_trade(self.primary_symbol):
                print(f"PRIMARY OPPORTUNITY: {self.primary_symbol}")
                self.execute_precision_buy(self.primary_symbol)
            else:
                # Try backup symbols
                for symbol in self.backup_symbols:
                    if self.should_trade(symbol):
                        print(f"BACKUP OPPORTUNITY: {symbol}")
                        if self.execute_precision_buy(symbol):
                            break
                else:
                    print("No trading opportunities found")
        elif self.active_position:
            symbol = self.active_position['symbol']
            hold_time = time.time() - self.active_position['entry_time']
            print(f"Monitoring {symbol} - Hold time: {hold_time/60:.1f}min")
        else:
            print(f"Insufficient balance: ${balance:.3f}")
    
    def run_autonomous_trader(self):
        """Main autonomous trading loop"""
        print("PRECISION AUTONOMOUS TRADING SYSTEM")
        print("Proven execution format • TRX-USDT focus • Consistent profits")
        print("=" * 60)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                self.run_precision_cycle()
                
                # Adaptive timing
                if self.active_position:
                    wait_time = 12  # Fast monitoring when position active
                else:
                    wait_time = 25  # Regular scanning
                
                print(f"Next precision cycle in {wait_time} seconds...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("\nPrecision trader stopped by user")
                break
            except Exception as e:
                print(f"Precision trader error: {e}")
                time.sleep(20)

def main():
    trader = PrecisionAutonomousTrader()
    trader.run_autonomous_trader()

if __name__ == "__main__":
    main()