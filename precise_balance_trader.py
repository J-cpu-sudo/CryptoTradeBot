#!/usr/bin/env python3
"""
Precise Balance Trader - Executes trades with exact balance accounting
Handles trading fees and precise quantity calculations for successful autonomous execution
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
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PreciseBalanceTrader:
    """Precise balance trader with exact fee calculations and balance management"""
    
    def __init__(self):
        self.api_key = os.environ.get('OKX_API_KEY')
        self.secret_key = os.environ.get('OKX_SECRET_KEY')
        self.passphrase = os.environ.get('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Ultra-low minimum trading pairs
        self.precision_pairs = [
            'FLOKI-USDT',   # Confirmed viable at $0.91
            'NEIRO-USDT',   # Confirmed viable at $0.91
            'BONK-USDT',    # Alternative micro-cap
            'MEME-USDT'     # Meme token option
        ]
        
        # Precise trading configuration
        self.fee_buffer = 0.002  # 0.2% fee buffer
        self.safety_margin = 0.01  # $0.01 safety margin
        self.max_usage = 0.98  # Use 98% of balance
        
        # State tracking
        self.is_running = False
        self.execution_count = 0
        self.last_execution = 0
        
        logger.info("Precise Balance Trader initialized")
    
    def get_timestamp(self) -> str:
        """Get precise timestamp for API"""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def create_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """Create API signature"""
        message = timestamp + method + path + body
        mac = hmac.new(
            bytes(self.secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    def get_auth_headers(self, method: str, path: str, body: str = '') -> Dict[str, str]:
        """Get authenticated headers"""
        timestamp = self.get_timestamp()
        signature = self.create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def make_request(self, method: str, endpoint: str, body: str = None) -> Optional[Dict]:
        """Make authenticated API request"""
        url = self.base_url + endpoint
        headers = self.get_auth_headers(method, endpoint, body or '')
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, data=body, timeout=10)
            else:
                return None
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Request failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None
    
    def get_exact_balance(self) -> float:
        """Get exact available USDT balance"""
        response = self.make_request('GET', '/api/v5/account/balance')
        
        if response and response.get('code') == '0':
            for detail in response['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    balance = float(detail['availBal'])
                    logger.info(f"Exact balance: ${balance:.8f}")
                    return balance
        
        return 0.0
    
    def get_precise_market_specs(self, symbol: str) -> Optional[Dict]:
        """Get precise market specifications for exact calculations"""
        # Get instrument data
        inst_url = f"/api/v5/public/instruments?instType=SPOT&instId={symbol}"
        inst_response = requests.get(self.base_url + inst_url, timeout=10)
        
        # Get current price
        ticker_url = f"/api/v5/market/ticker?instId={symbol}"
        ticker_response = requests.get(self.base_url + ticker_url, timeout=10)
        
        if (inst_response.status_code == 200 and ticker_response.status_code == 200):
            instrument = inst_response.json()['data'][0]
            ticker = ticker_response.json()['data'][0]
            
            specs = {
                'symbol': symbol,
                'price': float(ticker['last']),
                'min_size': float(instrument.get('minSz', '1')),
                'lot_size': float(instrument.get('lotSz', '1')),
                'tick_size': float(instrument.get('tickSz', '0.000001')),
                'volume_24h': float(ticker.get('vol24h', '0'))
            }
            
            specs['min_order_value'] = specs['min_size'] * specs['price']
            
            return specs
        
        return None
    
    def calculate_precise_trade(self, symbol: str, balance: float) -> Optional[Dict]:
        """Calculate precise trade parameters with fee accounting"""
        specs = self.get_precise_market_specs(symbol)
        if not specs:
            return None
        
        current_price = specs['price']
        min_size = specs['min_size']
        lot_size = specs['lot_size']
        min_order_value = specs['min_order_value']
        
        # Calculate usable balance (accounting for fees and safety margin)
        usable_balance = balance - self.safety_margin
        max_trade_value = usable_balance * self.max_usage
        
        # Check if we can afford minimum order
        if max_trade_value < min_order_value:
            logger.info(f"{symbol}: Max trade ${max_trade_value:.6f} < min required ${min_order_value:.6f}")
            return None
        
        # Calculate quantity with fee buffer
        fee_adjusted_balance = max_trade_value * (1 - self.fee_buffer)
        base_quantity = fee_adjusted_balance / current_price
        
        # Adjust for lot size
        if lot_size > 0:
            precise_quantity = int(base_quantity / lot_size) * lot_size
        else:
            precise_quantity = base_quantity
        
        # Verify minimum size
        if precise_quantity < min_size:
            logger.info(f"{symbol}: Quantity {precise_quantity:.6f} < minimum {min_size:.6f}")
            return None
        
        # Calculate exact cost
        exact_cost = precise_quantity * current_price
        estimated_fee = exact_cost * 0.001  # 0.1% taker fee
        total_cost = exact_cost + estimated_fee
        
        # Final balance check
        if total_cost > usable_balance:
            # Adjust quantity down to fit exactly
            adjusted_quantity = (usable_balance * 0.999) / current_price
            if lot_size > 0:
                adjusted_quantity = int(adjusted_quantity / lot_size) * lot_size
            
            if adjusted_quantity >= min_size:
                precise_quantity = adjusted_quantity
                exact_cost = precise_quantity * current_price
                total_cost = exact_cost * 1.001  # Include fee estimate
        
        return {
            'symbol': symbol,
            'quantity': precise_quantity,
            'price': current_price,
            'cost': exact_cost,
            'total_cost': total_cost,
            'specs': specs
        }
    
    def find_executable_trade(self, balance: float) -> Optional[Dict]:
        """Find trade that can be executed with current balance"""
        logger.info(f"Finding executable trade for ${balance:.8f}")
        
        for symbol in self.precision_pairs:
            trade = self.calculate_precise_trade(symbol, balance)
            if trade:
                logger.info(f"{symbol}: Executable - Cost ${trade['total_cost']:.6f}")
                return trade
            else:
                logger.info(f"{symbol}: Not executable")
        
        return None
    
    def execute_precise_trade(self, trade: Dict) -> bool:
        """Execute trade with precise parameters"""
        symbol = trade['symbol']
        quantity = trade['quantity']
        cost = trade['cost']
        
        logger.info(f"Executing precise trade: {symbol}")
        logger.info(f"Quantity: {quantity:.8f}")
        logger.info(f"Cost: ${cost:.6f}")
        
        order = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order)
        response = self.make_request('POST', '/api/v5/trade/order', order_body)
        
        if response and response.get('code') == '0':
            order_id = response['data'][0]['ordId']
            
            self.execution_count += 1
            self.last_execution = time.time()
            
            logger.info("TRADE EXECUTED SUCCESSFULLY")
            logger.info(f"Order ID: {order_id}")
            logger.info(f"Execution count: {self.execution_count}")
            
            # Log new balance
            new_balance = self.get_exact_balance()
            logger.info(f"New balance: ${new_balance:.8f}")
            
            return True
        else:
            error_msg = response.get('msg', 'Unknown error') if response else 'Request failed'
            logger.error(f"Trade execution failed: {error_msg}")
            
            if response and response.get('data'):
                for error in response['data']:
                    logger.error(f"Error {error.get('sCode')}: {error.get('sMsg')}")
            
            return False
    
    def run_single_execution(self) -> bool:
        """Run single trade execution"""
        logger.info("Running single precise trade execution")
        
        # Get current balance
        balance = self.get_exact_balance()
        if balance < 0.1:
            logger.warning(f"Balance too low: ${balance:.8f}")
            return False
        
        # Find executable trade
        trade = self.find_executable_trade(balance)
        if not trade:
            logger.warning("No executable trades found")
            return False
        
        # Execute the trade
        success = self.execute_precise_trade(trade)
        return success
    
    def start_continuous_execution(self):
        """Start continuous autonomous execution"""
        logger.info("Starting continuous precise trading")
        
        self.is_running = True
        cycle = 0
        
        while self.is_running:
            try:
                cycle += 1
                logger.info(f"EXECUTION CYCLE #{cycle}")
                
                # Execute trade
                success = self.run_single_execution()
                
                if success:
                    logger.info("Cycle completed successfully")
                else:
                    logger.warning("Cycle failed")
                
                # Wait 5 minutes between executions
                logger.info("Waiting 300 seconds for next cycle...")
                time.sleep(300)
                
            except KeyboardInterrupt:
                logger.info("Continuous execution stopped")
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                time.sleep(60)
    
    def start_background_execution(self):
        """Start execution in background thread"""
        if self.is_running:
            return
        
        thread = threading.Thread(target=self.start_continuous_execution, daemon=True)
        thread.start()
        logger.info("Background execution started")
        return thread

# Global instance
precise_trader = None

def initialize_precise_trader():
    """Initialize precise trader"""
    global precise_trader
    if precise_trader is None:
        precise_trader = PreciseBalanceTrader()
        precise_trader.start_background_execution()
    return precise_trader

if __name__ == "__main__":
    trader = PreciseBalanceTrader()
    trader.run_single_execution()