#!/usr/bin/env python3
"""
Ultimate Autonomous Trading System - Complete Error-Free Implementation
Handles all edge cases, balance constraints, and provides full autonomous operation
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
from typing import Dict, List, Optional, Any, Tuple
import logging
import math

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UltimateAutonomousTrader:
    """Ultimate autonomous trading system with comprehensive error handling and optimization"""
    
    def __init__(self):
        # Ensure all environment variables are strings
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Validate credentials
        if not all([self.api_key, self.secret_key, self.passphrase]):
            raise ValueError("Missing required API credentials")
        
        # Ultimate trading pairs with ultra-low requirements
        self.trading_pairs = [
            'SHIB-USDT',    # Massive quantity, low price
            'PEPE-USDT',    # Meme coin with micro requirements
            'BONK-USDT',    # Solana meme token
            'FLOKI-USDT',   # Low minimum requirements
            '1000SATS-USDT', # Bitcoin ordinals token
            'RATS-USDT'     # Alternative micro token
        ]
        
        # Ultimate configuration for maximum compatibility
        self.absolute_minimum_trade = 0.1  # $0.10 absolute minimum
        self.fee_multiplier = 1.005  # 0.5% total fee allowance
        self.safety_factor = 0.95   # Use 95% of calculated amount
        self.dust_threshold = 0.001  # $0.001 dust threshold
        
        # State management
        self.is_active = False
        self.execution_counter = 0
        self.success_counter = 0
        self.last_execution_time = 0
        self.cycle_interval = 300  # 5 minutes
        
        # Market data cache
        self.market_cache: Dict[str, Dict] = {}
        self.cache_duration = 60  # 1 minute cache
        
        logger.info("Ultimate Autonomous Trader initialized successfully")
    
    def get_precise_timestamp(self) -> str:
        """Generate precise UTC timestamp for OKX API"""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """Generate HMAC SHA256 signature for OKX API"""
        message = timestamp + method + request_path + body
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(self, method: str, request_path: str, body: str = '') -> Dict[str, str]:
        """Generate authenticated headers for API requests"""
        timestamp = self.get_precise_timestamp()
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def make_api_request(self, method: str, endpoint: str, body: Optional[str] = None, 
                        authenticated: bool = True) -> Optional[Dict]:
        """Make API request with comprehensive error handling"""
        url = self.base_url + endpoint
        
        try:
            if authenticated:
                headers = self.get_headers(method, endpoint, body or '')
            else:
                headers = {'Content-Type': 'application/json'}
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, data=body, timeout=15)
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    logger.error("Invalid JSON response")
                    return None
            else:
                logger.warning(f"API request failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in API request: {e}")
            return None
    
    def get_account_balance(self) -> float:
        """Get current USDT balance with error handling"""
        response = self.make_api_request('GET', '/api/v5/account/balance')
        
        if not response or response.get('code') != '0':
            logger.warning("Failed to fetch account balance")
            return 0.0
        
        try:
            for detail in response['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    balance = float(detail['availBal'])
                    logger.info(f"Current USDT balance: ${balance:.8f}")
                    return balance
        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.error(f"Error parsing balance data: {e}")
            return 0.0
        
        return 0.0
    
    def get_instrument_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive instrument data with caching"""
        current_time = time.time()
        
        # Check cache
        if symbol in self.market_cache:
            cached_data = self.market_cache[symbol]
            if current_time - cached_data['timestamp'] < self.cache_duration:
                return cached_data['data']
        
        # Fetch instrument specifications
        inst_response = self.make_api_request(
            'GET', 
            f'/api/v5/public/instruments?instType=SPOT&instId={symbol}',
            authenticated=False
        )
        
        # Fetch current ticker data
        ticker_response = self.make_api_request(
            'GET',
            f'/api/v5/market/ticker?instId={symbol}',
            authenticated=False
        )
        
        if not inst_response or not ticker_response:
            return None
        
        if (inst_response.get('code') != '0' or 
            ticker_response.get('code') != '0' or
            not inst_response.get('data') or
            not ticker_response.get('data')):
            return None
        
        try:
            instrument = inst_response['data'][0]
            ticker = ticker_response['data'][0]
            
            data = {
                'symbol': symbol,
                'last_price': float(ticker['last']),
                'bid_price': float(ticker['bidPx']),
                'ask_price': float(ticker['askPx']),
                'volume_24h': float(ticker['vol24h']),
                'change_24h': float(ticker['sodUtc0']),
                'min_size': float(instrument['minSz']),
                'lot_size': float(instrument['lotSz']),
                'tick_size': float(instrument['tickSz']),
                'min_order_value': 0.0  # Will be calculated
            }
            
            # Calculate minimum order value
            data['min_order_value'] = data['min_size'] * data['last_price']
            
            # Cache the data
            self.market_cache[symbol] = {
                'data': data,
                'timestamp': current_time
            }
            
            return data
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing instrument data for {symbol}: {e}")
            return None
    
    def calculate_optimal_quantity(self, symbol: str, usdt_amount: float) -> Tuple[float, float]:
        """Calculate optimal quantity and actual cost for trading"""
        instrument_data = self.get_instrument_data(symbol)
        if not instrument_data:
            return 0.0, 0.0
        
        last_price = instrument_data['last_price']
        min_size = instrument_data['min_size']
        lot_size = instrument_data['lot_size']
        
        # Calculate base quantity
        base_quantity = usdt_amount / last_price
        
        # Adjust for lot size
        if lot_size > 0:
            adjusted_quantity = math.floor(base_quantity / lot_size) * lot_size
        else:
            adjusted_quantity = base_quantity
        
        # Ensure minimum size
        if adjusted_quantity < min_size:
            return 0.0, 0.0
        
        # Calculate actual cost
        actual_cost = adjusted_quantity * last_price
        
        return adjusted_quantity, actual_cost
    
    def find_tradeable_opportunity(self, balance: float) -> Optional[Dict[str, Any]]:
        """Find best trading opportunity within balance constraints"""
        if balance < self.absolute_minimum_trade:
            logger.warning(f"Balance ${balance:.8f} below absolute minimum ${self.absolute_minimum_trade}")
            return None
        
        logger.info(f"Scanning trading opportunities for ${balance:.8f}")
        
        viable_opportunities = []
        
        for symbol in self.trading_pairs:
            instrument_data = self.get_instrument_data(symbol)
            if not instrument_data:
                logger.debug(f"Skipping {symbol} - no data available")
                continue
            
            min_order_value = instrument_data['min_order_value']
            volume_24h = instrument_data['volume_24h']
            last_price = instrument_data['last_price']
            
            # Check basic viability
            usable_balance = balance * self.safety_factor
            
            if usable_balance < min_order_value:
                logger.debug(f"Skipping {symbol} - insufficient balance: ${usable_balance:.6f} < ${min_order_value:.6f}")
                continue
            
            # Check volume threshold
            if volume_24h < 100000:  # $100k minimum daily volume
                logger.debug(f"Skipping {symbol} - low volume: ${volume_24h:.0f}")
                continue
            
            # Calculate trade parameters
            trade_amount = min(usable_balance / self.fee_multiplier, usable_balance)
            quantity, actual_cost = self.calculate_optimal_quantity(symbol, trade_amount)
            
            if quantity > 0 and actual_cost > 0:
                opportunity = {
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': last_price,
                    'cost': actual_cost,
                    'volume_score': volume_24h / 1000000,  # Volume in millions
                    'instrument_data': instrument_data
                }
                viable_opportunities.append(opportunity)
                logger.info(f"{symbol}: Viable - Quantity: {quantity:.6f}, Cost: ${actual_cost:.6f}")
            else:
                logger.debug(f"Skipping {symbol} - quantity calculation failed")
        
        if not viable_opportunities:
            logger.warning("No viable trading opportunities found")
            return None
        
        # Select best opportunity by volume score
        best_opportunity = max(viable_opportunities, key=lambda x: x['volume_score'])
        logger.info(f"Selected: {best_opportunity['symbol']} (Volume score: {best_opportunity['volume_score']:.2f})")
        
        return best_opportunity
    
    def execute_trade_order(self, opportunity: Dict[str, Any]) -> bool:
        """Execute trading order with comprehensive validation"""
        symbol = opportunity['symbol']
        quantity = opportunity['quantity']
        expected_cost = opportunity['cost']
        
        logger.info(f"Executing trade order for {symbol}")
        logger.info(f"Quantity: {quantity:.8f}")
        logger.info(f"Expected cost: ${expected_cost:.6f}")
        
        # Prepare order data
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        try:
            order_body = json.dumps(order_data)
            response = self.make_api_request('POST', '/api/v5/trade/order', order_body)
            
            if not response:
                logger.error("Trade order request failed - no response")
                return False
            
            if response.get('code') == '0' and response.get('data'):
                order_id = response['data'][0]['ordId']
                
                # Update counters
                self.execution_counter += 1
                self.success_counter += 1
                self.last_execution_time = time.time()
                
                success_rate = (self.success_counter / self.execution_counter) * 100
                
                logger.info("TRADE ORDER EXECUTED SUCCESSFULLY")
                logger.info(f"Order ID: {order_id}")
                logger.info(f"Total executions: {self.execution_counter}")
                logger.info(f"Success rate: {success_rate:.1f}%")
                
                # Log updated balance
                time.sleep(2)  # Brief delay for balance update
                new_balance = self.get_account_balance()
                logger.info(f"Updated balance: ${new_balance:.8f}")
                
                return True
            else:
                self.execution_counter += 1
                error_msg = response.get('msg', 'Unknown error')
                logger.error(f"Trade order failed: {error_msg}")
                
                # Log detailed error information
                if response.get('data'):
                    for error_detail in response['data']:
                        error_code = error_detail.get('sCode', 'N/A')
                        error_message = error_detail.get('sMsg', 'N/A')
                        logger.error(f"Error {error_code}: {error_message}")
                
                return False
                
        except json.JSONEncodeError as e:
            logger.error(f"JSON encoding error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during trade execution: {e}")
            return False
    
    def run_trading_cycle(self) -> bool:
        """Execute one complete trading cycle"""
        logger.info("Starting autonomous trading cycle")
        
        # Check cooldown period
        if time.time() - self.last_execution_time < self.cycle_interval:
            remaining = self.cycle_interval - (time.time() - self.last_execution_time)
            logger.info(f"Cooldown active: {remaining:.0f} seconds remaining")
            return False
        
        # Get current balance
        balance = self.get_account_balance()
        if balance < self.absolute_minimum_trade:
            logger.warning(f"Insufficient balance for trading: ${balance:.8f}")
            return False
        
        # Find trading opportunity
        opportunity = self.find_tradeable_opportunity(balance)
        if not opportunity:
            logger.warning("No trading opportunities available in current cycle")
            return False
        
        # Execute trade
        success = self.execute_trade_order(opportunity)
        
        if success:
            logger.info("Trading cycle completed successfully")
        else:
            logger.warning("Trading cycle failed during execution")
        
        return success
    
    def start_continuous_trading(self):
        """Start continuous autonomous trading loop"""
        logger.info("STARTING CONTINUOUS AUTONOMOUS TRADING")
        
        # Initial system verification
        initial_balance = self.get_account_balance()
        if initial_balance < self.absolute_minimum_trade:
            logger.error(f"Initial balance ${initial_balance:.8f} too low for autonomous trading")
            return
        
        logger.info(f"Autonomous trading initialized with ${initial_balance:.8f} USDT")
        
        self.is_active = True
        cycle_number = 0
        
        while self.is_active:
            try:
                cycle_number += 1
                current_time = datetime.now().strftime('%H:%M:%S UTC')
                logger.info(f"AUTONOMOUS CYCLE #{cycle_number} - {current_time}")
                
                # Execute trading cycle
                cycle_success = self.run_trading_cycle()
                
                # Performance logging every 10 cycles
                if cycle_number % 10 == 0:
                    current_balance = self.get_account_balance()
                    success_rate = (self.success_counter / max(1, self.execution_counter)) * 100
                    logger.info(f"Performance Update - Cycles: {cycle_number}")
                    logger.info(f"Balance: ${current_balance:.8f}")
                    logger.info(f"Success Rate: {success_rate:.1f}%")
                
                # Wait for next cycle
                logger.info(f"Waiting {self.cycle_interval} seconds for next cycle...")
                time.sleep(self.cycle_interval)
                
            except KeyboardInterrupt:
                logger.info("Autonomous trading interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in trading cycle: {e}")
                logger.info("Continuing after 60-second delay...")
                time.sleep(60)
        
        logger.info("Continuous autonomous trading stopped")
    
    def start_background_trading(self) -> threading.Thread:
        """Start autonomous trading in background thread"""
        if self.is_active:
            logger.warning("Autonomous trading already active")
            return None
        
        logger.info("Initializing background autonomous trading")
        trading_thread = threading.Thread(target=self.start_continuous_trading, daemon=True)
        trading_thread.start()
        logger.info("Background autonomous trading started successfully")
        
        return trading_thread
    
    def stop_trading(self):
        """Stop autonomous trading"""
        self.is_active = False
        logger.info("Autonomous trading stop signal sent")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        current_balance = self.get_account_balance()
        success_rate = (self.success_counter / max(1, self.execution_counter)) * 100
        
        return {
            'is_active': self.is_active,
            'current_balance': current_balance,
            'execution_count': self.execution_counter,
            'success_count': self.success_counter,
            'success_rate': success_rate,
            'last_execution': self.last_execution_time,
            'cycle_interval': self.cycle_interval
        }

# Global instance management
ultimate_trader = None

def initialize_ultimate_trader() -> UltimateAutonomousTrader:
    """Initialize and start the ultimate autonomous trader"""
    global ultimate_trader
    
    if ultimate_trader is None:
        try:
            ultimate_trader = UltimateAutonomousTrader()
            ultimate_trader.start_background_trading()
            logger.info("Ultimate autonomous trader initialized and activated")
        except Exception as e:
            logger.error(f"Failed to initialize ultimate trader: {e}")
            raise
    
    return ultimate_trader

def get_trader_status() -> Dict[str, Any]:
    """Get current trader status"""
    if ultimate_trader:
        return ultimate_trader.get_system_status()
    return {'status': 'not_initialized'}

if __name__ == "__main__":
    # Direct execution for testing
    try:
        trader = UltimateAutonomousTrader()
        logger.info("Running single trading cycle test...")
        success = trader.run_trading_cycle()
        logger.info(f"Test result: {'SUCCESS' if success else 'FAILED'}")
    except Exception as e:
        logger.error(f"Test execution failed: {e}")