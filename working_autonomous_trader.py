#!/usr/bin/env python3
"""
Working Autonomous Trader - Final implementation with exact balance calculations
Resolves error 51008 by using ultra-conservative balance calculations
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

class WorkingAutonomousTrader:
    """Working autonomous trader with ultra-conservative balance management"""
    
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Ultra-conservative settings to avoid balance errors
        self.max_balance_usage = 0.85  # Use only 85% of balance
        self.fee_buffer = 0.02  # 2% buffer for all fees
        self.dust_reserve = 0.01  # Keep $0.01 reserve
        
        # Working trading pairs
        self.pairs = ['FLOKI-USDT', 'SHIB-USDT', 'BONK-USDT']
        
        # State
        self.is_running = False
        self.trades_executed = 0
        self.last_trade_time = 0
        
        logger.info("Working Autonomous Trader initialized")
    
    def get_timestamp(self) -> str:
        """Get precise timestamp"""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def create_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """Create API signature"""
        message = timestamp + method + path + body
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(self, method: str, path: str, body: str = '') -> Dict[str, str]:
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
    
    def api_call(self, method: str, endpoint: str, body: str = None) -> Optional[Dict]:
        """Make API call with error handling"""
        url = self.base_url + endpoint
        headers = self.get_headers(method, endpoint, body or '')
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def get_balance(self) -> float:
        """Get exact USDT balance"""
        response = self.api_call('GET', '/api/v5/account/balance')
        
        if response and response.get('code') == '0':
            for detail in response['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    balance = float(detail['availBal'])
                    logger.info(f"Balance: ${balance:.8f}")
                    return balance
        return 0.0
    
    def get_market_info(self, symbol: str) -> Optional[Dict]:
        """Get market information for symbol"""
        # Get instrument specs
        inst_url = f"/api/v5/public/instruments?instType=SPOT&instId={symbol}"
        inst_response = requests.get(self.base_url + inst_url, timeout=10)
        
        # Get current price
        ticker_url = f"/api/v5/market/ticker?instId={symbol}"
        ticker_response = requests.get(self.base_url + ticker_url, timeout=10)
        
        if inst_response.status_code == 200 and ticker_response.status_code == 200:
            instrument = inst_response.json()['data'][0]
            ticker = ticker_response.json()['data'][0]
            
            return {
                'price': float(ticker['last']),
                'min_size': float(instrument['minSz']),
                'lot_size': float(instrument['lotSz']),
                'volume': float(ticker['vol24h'])
            }
        return None
    
    def calculate_safe_quantity(self, symbol: str, balance: float) -> Optional[Dict]:
        """Calculate ultra-safe trade quantity to avoid balance errors"""
        market_info = self.get_market_info(symbol)
        if not market_info:
            return None
        
        price = market_info['price']
        min_size = market_info['min_size']
        lot_size = market_info['lot_size']
        
        # Ultra-conservative balance calculation
        usable_balance = balance - self.dust_reserve
        max_spend = usable_balance * self.max_balance_usage
        
        # Account for fees and slippage
        trade_amount = max_spend * (1 - self.fee_buffer)
        
        # Calculate quantity
        base_quantity = trade_amount / price
        
        # Adjust for lot size
        if lot_size > 0:
            adjusted_quantity = int(base_quantity / lot_size) * lot_size
        else:
            adjusted_quantity = base_quantity
        
        # Check minimum size
        if adjusted_quantity < min_size:
            logger.info(f"{symbol}: Quantity {adjusted_quantity:.6f} below minimum {min_size:.6f}")
            return None
        
        actual_cost = adjusted_quantity * price
        
        # Final safety check - ensure we have enough balance
        if actual_cost > trade_amount:
            logger.info(f"{symbol}: Cost ${actual_cost:.6f} exceeds safe amount ${trade_amount:.6f}")
            return None
        
        return {
            'symbol': symbol,
            'quantity': adjusted_quantity,
            'cost': actual_cost,
            'price': price
        }
    
    def find_trade_opportunity(self, balance: float) -> Optional[Dict]:
        """Find viable trade opportunity"""
        logger.info(f"Finding trade opportunity for ${balance:.8f}")
        
        for symbol in self.pairs:
            trade_calc = self.calculate_safe_quantity(symbol, balance)
            if trade_calc:
                logger.info(f"{symbol}: Safe trade found - Cost: ${trade_calc['cost']:.6f}")
                return trade_calc
            else:
                logger.info(f"{symbol}: No safe trade possible")
        
        return None
    
    def execute_trade(self, trade_data: Dict) -> bool:
        """Execute the trade with ultra-safe parameters"""
        symbol = trade_data['symbol']
        quantity = trade_data['quantity']
        cost = trade_data['cost']
        
        logger.info(f"Executing safe trade: {symbol}")
        logger.info(f"Quantity: {quantity:.8f}")
        logger.info(f"Cost: ${cost:.6f}")
        
        # Use slightly reduced quantity for final safety
        safe_quantity = quantity * 0.99  # 1% reduction for final safety
        
        order = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(safe_quantity)
        }
        
        order_body = json.dumps(order)
        response = self.api_call('POST', '/api/v5/trade/order', order_body)
        
        if response and response.get('code') == '0':
            order_id = response['data'][0]['ordId']
            self.trades_executed += 1
            self.last_trade_time = time.time()
            
            logger.info("TRADE EXECUTED SUCCESSFULLY")
            logger.info(f"Order ID: {order_id}")
            logger.info(f"Total trades: {self.trades_executed}")
            
            return True
        else:
            error_msg = response.get('msg', 'Unknown error') if response else 'Request failed'
            logger.error(f"Trade failed: {error_msg}")
            
            if response and response.get('data'):
                for error in response['data']:
                    logger.error(f"Error {error.get('sCode')}: {error.get('sMsg')}")
            
            return False
    
    def run_single_trade(self) -> bool:
        """Execute a single autonomous trade"""
        logger.info("Running single autonomous trade")
        
        # Get current balance
        balance = self.get_balance()
        if balance < 0.5:
            logger.warning(f"Balance too low: ${balance:.8f}")
            return False
        
        # Find trade opportunity
        trade_opportunity = self.find_trade_opportunity(balance)
        if not trade_opportunity:
            logger.warning("No safe trade opportunities found")
            return False
        
        # Execute trade
        success = self.execute_trade(trade_opportunity)
        return success
    
    def start_autonomous_loop(self):
        """Start continuous autonomous trading"""
        logger.info("Starting autonomous trading loop")
        
        self.is_running = True
        cycle = 0
        
        while self.is_running:
            try:
                cycle += 1
                logger.info(f"AUTONOMOUS CYCLE #{cycle}")
                
                # Execute trade
                self.run_single_trade()
                
                # Wait 5 minutes
                logger.info("Waiting 300 seconds for next cycle...")
                time.sleep(300)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                time.sleep(60)
    
    def start_background(self):
        """Start in background"""
        if self.is_running:
            return
        
        thread = threading.Thread(target=self.start_autonomous_loop, daemon=True)
        thread.start()
        logger.info("Background autonomous trading started")
        return thread

# Global instance
working_trader = None

def initialize_working_trader():
    """Initialize working trader"""
    global working_trader
    if working_trader is None:
        working_trader = WorkingAutonomousTrader()
        working_trader.start_background()
    return working_trader

if __name__ == "__main__":
    trader = WorkingAutonomousTrader()
    success = trader.run_single_trade()
    logger.info(f"Single trade result: {'SUCCESS' if success else 'FAILED'}")
    
    if success:
        logger.info("Trade executed successfully - starting continuous operation")
        trader.start_autonomous_loop()
    else:
        logger.info("Initial trade failed - checking balance requirements")