#!/usr/bin/env python3
"""
Optimized Micro Trading System - Designed for small balance autonomous trading
Handles minimum order requirements and maximizes trading opportunities with limited funds
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
from typing import Dict, List, Optional, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimizedMicroTrader:
    """Micro trading system optimized for small balances and minimum order requirements"""
    
    def __init__(self):
        self.api_key = os.environ.get('OKX_API_KEY')
        self.secret_key = os.environ.get('OKX_SECRET_KEY')
        self.passphrase = os.environ.get('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Micro trading pairs optimized for ultra-low minimums
        self.micro_pairs = [
            'SHIB-USDT',    # Ultra low minimum orders
            'PEPE-USDT',    # Meme coin with tiny minimums
            'DOGE-USDT',    # Popular with reasonable minimums
            'FLOKI-USDT',   # Alternative micro-cap option
            'NEIRO-USDT'    # Emerging micro-cap
        ]
        
        # Micro trading configuration
        self.min_trade_threshold = 0.1  # Minimum $0.10 trades
        self.max_balance_usage = 0.95   # Use 95% of available balance
        self.reserve_balance = 0.05     # Keep $0.05 minimum reserve
        
        # Trading state
        self.is_active = False
        self.last_execution = 0
        self.cycle_interval = 300  # 5 minutes between cycles
        self.total_executions = 0
        self.successful_executions = 0
        
        logger.info("Optimized Micro Trader initialized for small balance trading")
    
    def get_precise_timestamp(self) -> str:
        """Get precise UTC timestamp for OKX API"""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
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
        """Get authenticated headers"""
        timestamp = self.get_precise_timestamp()
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def api_request(self, method: str, endpoint: str, body: str = None) -> Optional[Dict]:
        """Execute API request with error handling"""
        url = self.base_url + endpoint
        headers = self.get_headers(method, endpoint, body or '')
        
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
                logger.warning(f"API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def get_account_balance(self) -> float:
        """Get current USDT balance"""
        response = self.api_request('GET', '/api/v5/account/balance')
        
        if response and response.get('code') == '0':
            for detail in response['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    balance = float(detail['availBal'])
                    logger.info(f"Current balance: ${balance:.6f}")
                    return balance
        
        logger.warning("Failed to retrieve balance")
        return 0.0
    
    def get_micro_instrument_specs(self, symbol: str) -> Dict[str, float]:
        """Get detailed instrument specifications for micro trading"""
        # Get public instrument info
        public_response = requests.get(
            f"{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}",
            timeout=10
        )
        
        # Get current market price
        ticker_response = requests.get(
            f"{self.base_url}/api/v5/market/ticker?instId={symbol}",
            timeout=10
        )
        
        if (public_response.status_code == 200 and 
            ticker_response.status_code == 200):
            
            instrument = public_response.json()['data'][0]
            ticker = ticker_response.json()['data'][0]
            
            min_size = float(instrument.get('minSz', '1'))
            lot_size = float(instrument.get('lotSz', '1'))
            current_price = float(ticker['last'])
            min_order_value = min_size * current_price
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'min_size': min_size,
                'lot_size': lot_size,
                'min_order_value': min_order_value,
                'volume_24h': float(ticker.get('vol24h', '0'))
            }
        
        return {}
    
    def find_optimal_micro_trade(self, balance: float) -> Optional[Dict]:
        """Find the best micro trading opportunity for small balance"""
        logger.info(f"Scanning micro trading opportunities for ${balance:.6f}")
        
        available_balance = balance - self.reserve_balance
        if available_balance < self.min_trade_threshold:
            logger.warning(f"Insufficient balance for micro trading: ${available_balance:.6f}")
            return None
        
        best_opportunity = None
        lowest_minimum = float('inf')
        
        for symbol in self.micro_pairs:
            try:
                specs = self.get_micro_instrument_specs(symbol)
                if not specs:
                    continue
                
                min_order_value = specs['min_order_value']
                current_price = specs['current_price']
                min_size = specs['min_size']
                lot_size = specs['lot_size']
                volume_24h = specs['volume_24h']
                
                # Check if we can afford this trade
                if min_order_value <= available_balance:
                    # Calculate exact quantity we can buy
                    max_usdt_to_spend = min(available_balance * self.max_balance_usage, available_balance)
                    base_quantity = max_usdt_to_spend / current_price
                    
                    # Adjust for lot size
                    if lot_size > 0:
                        adjusted_quantity = int(base_quantity / lot_size) * lot_size
                    else:
                        adjusted_quantity = base_quantity
                    
                    # Verify it meets minimum size
                    if adjusted_quantity >= min_size:
                        actual_cost = adjusted_quantity * current_price
                        
                        # Score based on affordability and volume
                        score = volume_24h / 1000000  # Volume in millions
                        
                        opportunity = {
                            'symbol': symbol,
                            'quantity': adjusted_quantity,
                            'price': current_price,
                            'cost': actual_cost,
                            'min_order_value': min_order_value,
                            'volume_24h': volume_24h,
                            'score': score
                        }
                        
                        # Track lowest minimum for reference
                        if min_order_value < lowest_minimum:
                            lowest_minimum = min_order_value
                            best_opportunity = opportunity
                        
                        logger.info(f"{symbol}: ${actual_cost:.6f} cost, Score: {score:.2f}")
                    else:
                        logger.info(f"{symbol}: Quantity {adjusted_quantity:.2f} < minimum {min_size:.2f}")
                else:
                    logger.info(f"{symbol}: Min order ${min_order_value:.6f} > available ${available_balance:.6f}")
                    
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                continue
        
        if best_opportunity:
            logger.info(f"Selected: {best_opportunity['symbol']} - Cost: ${best_opportunity['cost']:.6f}")
        else:
            logger.warning("No viable micro trading opportunities found")
        
        return best_opportunity
    
    def execute_micro_trade(self, opportunity: Dict) -> bool:
        """Execute micro trade with precise order handling"""
        symbol = opportunity['symbol']
        quantity = opportunity['quantity']
        cost = opportunity['cost']
        
        logger.info(f"Executing micro trade: {symbol}")
        logger.info(f"Quantity: {quantity:.6f}")
        logger.info(f"Expected cost: ${cost:.6f}")
        
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        response = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if response and response.get('code') == '0':
            order_id = response['data'][0]['ordId']
            
            self.total_executions += 1
            self.successful_executions += 1
            self.last_execution = time.time()
            
            success_rate = (self.successful_executions / self.total_executions) * 100
            
            logger.info("MICRO TRADE EXECUTED SUCCESSFULLY")
            logger.info(f"Order ID: {order_id}")
            logger.info(f"Total executions: {self.total_executions}")
            logger.info(f"Success rate: {success_rate:.1f}%")
            
            return True
        else:
            self.total_executions += 1
            error_msg = response.get('msg', 'Unknown error') if response else 'Request failed'
            logger.error(f"Micro trade failed: {error_msg}")
            
            if response and response.get('data'):
                for error_detail in response['data']:
                    logger.error(f"Error code {error_detail.get('sCode')}: {error_detail.get('sMsg')}")
            
            return False
    
    def execute_micro_cycle(self) -> bool:
        """Execute one micro trading cycle"""
        logger.info("Starting micro trading cycle")
        
        # Check cooldown
        if time.time() - self.last_execution < self.cycle_interval:
            remaining = self.cycle_interval - (time.time() - self.last_execution)
            logger.info(f"Cooldown active: {remaining:.0f}s remaining")
            return False
        
        # Get current balance
        balance = self.get_account_balance()
        if balance < self.min_trade_threshold:
            logger.warning(f"Balance too low for micro trading: ${balance:.6f}")
            return False
        
        # Find micro trading opportunity
        opportunity = self.find_optimal_micro_trade(balance)
        if not opportunity:
            logger.warning("No micro trading opportunities available")
            return False
        
        # Execute the micro trade
        success = self.execute_micro_trade(opportunity)
        
        if success:
            logger.info("Micro trading cycle completed successfully")
        else:
            logger.warning("Micro trading cycle failed")
        
        return success
    
    def run_continuous_micro_trading(self):
        """Run continuous micro trading loop"""
        logger.info("STARTING CONTINUOUS MICRO TRADING SYSTEM")
        
        # Initial balance check
        initial_balance = self.get_account_balance()
        logger.info(f"Starting micro trading with ${initial_balance:.6f}")
        
        if initial_balance < self.min_trade_threshold:
            logger.error(f"Initial balance too low: ${initial_balance:.6f}")
            return
        
        self.is_active = True
        cycle_count = 0
        
        while self.is_active:
            try:
                cycle_count += 1
                logger.info(f"MICRO CYCLE #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Execute micro trading cycle
                self.execute_micro_cycle()
                
                # Status update every 5 cycles
                if cycle_count % 5 == 0:
                    current_balance = self.get_account_balance()
                    success_rate = (self.successful_executions / max(1, self.total_executions)) * 100
                    logger.info(f"Status - Balance: ${current_balance:.6f}, Success: {success_rate:.1f}%")
                
                # Wait for next cycle
                logger.info(f"Waiting {self.cycle_interval}s for next micro cycle...")
                time.sleep(self.cycle_interval)
                
            except KeyboardInterrupt:
                logger.info("Micro trading stopped by user")
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                time.sleep(60)
        
        logger.info("Continuous micro trading stopped")
    
    def start_micro_trading(self):
        """Start micro trading in background"""
        if self.is_active:
            logger.warning("Micro trading already active")
            return
        
        logger.info("Initializing micro trading system")
        trading_thread = threading.Thread(target=self.run_continuous_micro_trading, daemon=True)
        trading_thread.start()
        logger.info("Micro trading system started")
        return trading_thread
    
    def stop_micro_trading(self):
        """Stop micro trading"""
        self.is_active = False
        logger.info("Micro trading stopped")
    
    def get_micro_status(self) -> Dict[str, Any]:
        """Get micro trading status"""
        current_balance = self.get_account_balance()
        success_rate = (self.successful_executions / max(1, self.total_executions)) * 100
        
        return {
            'is_active': self.is_active,
            'current_balance': current_balance,
            'total_executions': self.total_executions,
            'successful_executions': self.successful_executions,
            'success_rate': success_rate,
            'last_execution': self.last_execution
        }

# Global micro trader instance
micro_trader = None

def initialize_micro_trader():
    """Initialize and start micro trader"""
    global micro_trader
    
    if micro_trader is None:
        micro_trader = OptimizedMicroTrader()
        micro_trader.start_micro_trading()
        logger.info("Micro trader initialized and started")
    
    return micro_trader

def get_micro_status():
    """Get micro trader status"""
    if micro_trader:
        return micro_trader.get_micro_status()
    return {'status': 'not_initialized'}

if __name__ == "__main__":
    # Direct execution
    trader = OptimizedMicroTrader()
    trader.run_continuous_micro_trading()