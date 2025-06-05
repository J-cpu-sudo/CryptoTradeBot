#!/usr/bin/env python3
"""
Complete Autonomous Trading System - Full Configuration and Execution
Handles all trading operations with comprehensive error handling and autonomous decision making
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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompleteAutonomousTrader:
    """Complete autonomous trading system with full configuration"""
    
    def __init__(self):
        self.api_key = os.environ.get('OKX_API_KEY')
        self.secret_key = os.environ.get('OKX_SECRET_KEY')
        self.passphrase = os.environ.get('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Trading configuration
        self.trading_pairs = [
            'DOGE-USDT',
            'TRX-USDT', 
            'SHIB-USDT',
            'PEPE-USDT',
            'XRP-USDT',
            'ADA-USDT'
        ]
        
        # Risk management
        self.max_trade_amount = 5.0  # Max $5 per trade
        self.min_balance_threshold = 0.5  # Keep minimum $0.50
        self.risk_percentage = 0.8  # Use 80% of available balance
        
        # Trading state
        self.is_running = False
        self.last_trade_time = 0
        self.trade_cooldown = 240  # 4 minutes between trades
        self.trade_count = 0
        self.total_profit = 0.0
        
        # Market data cache
        self.market_cache = {}
        self.cache_timeout = 30  # 30 seconds
        
        logger.info("Complete Autonomous Trader initialized")
    
    def generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """Generate OKX API signature"""
        try:
            message = timestamp + method + request_path + body
            mac = hmac.new(
                bytes(self.secret_key, encoding='utf8'),
                bytes(message, encoding='utf-8'),
                digestmod=hashlib.sha256
            )
            return base64.b64encode(mac.digest()).decode()
        except Exception as e:
            logger.error(f"Signature generation error: {e}")
            return ""
    
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
    
    def safe_request(self, method: str, url: str, headers: Dict = None, data: str = None, timeout: int = 10) -> Optional[Dict]:
        """Safe HTTP request with error handling"""
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, headers=headers, data=data, timeout=timeout)
            else:
                return None
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"HTTP {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None
    
    def test_credentials(self) -> bool:
        """Test if API credentials work for trading"""
        logger.info("Testing API credentials...")
        
        # Test balance access
        path = '/api/v5/account/balance'
        headers = self.get_headers('GET', path)
        response = self.safe_request('GET', self.base_url + path, headers=headers)
        
        if not response or response.get('code') != '0':
            logger.error("Failed to access account balance")
            return False
        
        # Test trading permissions with a small test order (will be cancelled)
        test_symbol = 'DOGE-USDT'
        order_data = {
            "instId": test_symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "limit",
            "sz": "1",
            "px": "0.001"  # Very low price, won't execute
        }
        
        path = '/api/v5/trade/order'
        body = json.dumps(order_data)
        headers = self.get_headers('POST', path, body)
        response = self.safe_request('POST', self.base_url + path, headers=headers, data=body)
        
        if response and response.get('code') == '0':
            # Cancel the test order immediately
            order_id = response['data'][0]['ordId']
            cancel_data = {"instId": test_symbol, "ordId": order_id}
            cancel_path = '/api/v5/trade/cancel-order'
            cancel_body = json.dumps(cancel_data)
            cancel_headers = self.get_headers('POST', cancel_path, cancel_body)
            self.safe_request('POST', self.base_url + cancel_path, headers=cancel_headers, data=cancel_body)
            
            logger.info("✅ Trading credentials verified successfully")
            return True
        else:
            logger.error("❌ Trading permissions not enabled")
            return False
    
    def get_account_balance(self) -> float:
        """Get current USDT balance"""
        path = '/api/v5/account/balance'
        headers = self.get_headers('GET', path)
        response = self.safe_request('GET', self.base_url + path, headers=headers)
        
        if response and response.get('code') == '0':
            for detail in response['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    balance = float(detail['availBal'])
                    logger.info(f"Current USDT balance: ${balance:.2f}")
                    return balance
        
        logger.warning("Failed to get balance")
        return 0.0
    
    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for symbol with caching"""
        current_time = time.time()
        
        # Check cache
        if symbol in self.market_cache:
            cache_data = self.market_cache[symbol]
            if current_time - cache_data['timestamp'] < self.cache_timeout:
                return cache_data['data']
        
        # Fetch fresh data
        ticker_url = f"{self.base_url}/api/v5/market/ticker?instId={symbol}"
        response = self.safe_request('GET', ticker_url)
        
        if response and response.get('data'):
            market_data = response['data'][0]
            
            # Cache the data
            self.market_cache[symbol] = {
                'data': market_data,
                'timestamp': current_time
            }
            
            return market_data
        
        return None
    
    def get_instrument_info(self, symbol: str) -> Dict[str, float]:
        """Get trading instrument specifications"""
        url = f"{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}"
        response = self.safe_request('GET', url)
        
        if response and response.get('data'):
            instrument = response['data'][0]
            return {
                'min_size': float(instrument.get('minSz', '1')),
                'lot_size': float(instrument.get('lotSz', '1')),
                'tick_size': float(instrument.get('tickSz', '0.000001'))
            }
        
        return {'min_size': 1.0, 'lot_size': 1.0, 'tick_size': 0.000001}
    
    def calculate_trade_quantity(self, symbol: str, usdt_amount: float, current_price: float) -> float:
        """Calculate optimal trade quantity"""
        instrument_info = self.get_instrument_info(symbol)
        min_size = instrument_info['min_size']
        lot_size = instrument_info['lot_size']
        
        # Calculate base quantity
        quantity = usdt_amount / current_price
        
        # Adjust for lot size
        if lot_size > 0:
            quantity = int(quantity / lot_size) * lot_size
        
        # Ensure minimum size
        if quantity < min_size:
            logger.warning(f"Calculated quantity {quantity} below minimum {min_size} for {symbol}")
            return 0.0
        
        return quantity
    
    def analyze_market_conditions(self, symbol: str) -> Dict[str, Any]:
        """Analyze market conditions for trading decision"""
        market_data = self.get_market_data(symbol)
        if not market_data:
            return {'trade': False, 'reason': 'No market data'}
        
        current_price = float(market_data['last'])
        volume_24h = float(market_data['vol24h'])
        price_change = float(market_data['sodUtc0'])
        
        # Basic trading conditions
        conditions = {
            'price': current_price,
            'volume': volume_24h,
            'change_24h': price_change,
            'trade': True,
            'reason': 'Market conditions favorable'
        }
        
        # Volume check
        if volume_24h < 1000000:  # Minimum $1M daily volume
            conditions['trade'] = False
            conditions['reason'] = 'Low volume'
            return conditions
        
        # Volatility check - avoid extreme movements
        if abs(price_change) > 20:  # Avoid >20% moves
            conditions['trade'] = False
            conditions['reason'] = 'High volatility'
            return conditions
        
        return conditions
    
    def select_optimal_trading_pair(self, balance: float) -> Optional[str]:
        """Select the best trading pair based on current conditions"""
        best_pair = None
        best_score = 0
        
        logger.info("Analyzing trading pairs...")
        
        for symbol in self.trading_pairs:
            analysis = self.analyze_market_conditions(symbol)
            
            if not analysis['trade']:
                logger.info(f"{symbol}: {analysis['reason']}")
                continue
            
            # Calculate trade amount for this pair
            trade_amount = min(balance * self.risk_percentage, self.max_trade_amount)
            if trade_amount < 1.0:
                continue
            
            # Get instrument info to check feasibility
            current_price = analysis['price']
            quantity = self.calculate_trade_quantity(symbol, trade_amount, current_price)
            
            if quantity <= 0:
                logger.info(f"{symbol}: Insufficient quantity")
                continue
            
            # Score based on volume and feasibility
            score = analysis['volume'] / 1000000  # Volume in millions
            if score > best_score:
                best_score = score
                best_pair = symbol
                logger.info(f"{symbol}: Score {score:.2f} - Current best")
        
        if best_pair:
            logger.info(f"Selected optimal pair: {best_pair}")
        else:
            logger.info("No suitable trading pairs found")
        
        return best_pair
    
    def execute_trade(self, symbol: str, usdt_amount: float) -> bool:
        """Execute a buy trade"""
        logger.info(f"Executing trade: {symbol} with ${usdt_amount:.2f}")
        
        # Get current market data
        market_data = self.get_market_data(symbol)
        if not market_data:
            logger.error("Failed to get market data")
            return False
        
        current_price = float(market_data['last'])
        quantity = self.calculate_trade_quantity(symbol, usdt_amount, current_price)
        
        if quantity <= 0:
            logger.error("Invalid trade quantity")
            return False
        
        # Prepare order
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        # Execute order
        path = '/api/v5/trade/order'
        body = json.dumps(order_data)
        headers = self.get_headers('POST', path, body)
        response = self.safe_request('POST', self.base_url + path, headers=headers, data=body)
        
        if response and response.get('code') == '0':
            order_id = response['data'][0]['ordId']
            estimated_value = quantity * current_price
            
            logger.info("🎯 TRADE EXECUTED SUCCESSFULLY!")
            logger.info(f"Order ID: {order_id}")
            logger.info(f"Symbol: {symbol}")
            logger.info(f"Quantity: {quantity:.4f}")
            logger.info(f"Price: ${current_price:.6f}")
            logger.info(f"Value: ${estimated_value:.2f}")
            
            self.trade_count += 1
            self.last_trade_time = time.time()
            return True
        else:
            error_msg = response.get('msg', 'Unknown error') if response else 'Request failed'
            logger.error(f"Trade failed: {error_msg}")
            return False
    
    def autonomous_cycle(self) -> bool:
        """Execute one autonomous trading cycle"""
        logger.info("🔄 Starting autonomous trading cycle")
        
        # Check cooldown
        if time.time() - self.last_trade_time < self.trade_cooldown:
            remaining = self.trade_cooldown - (time.time() - self.last_trade_time)
            logger.info(f"⏱️ Cooldown active: {remaining:.0f}s remaining")
            return False
        
        # Get account balance
        balance = self.get_account_balance()
        if balance < self.min_balance_threshold:
            logger.warning(f"❌ Insufficient balance: ${balance:.2f}")
            return False
        
        # Calculate trade amount
        available_amount = balance - self.min_balance_threshold
        trade_amount = min(available_amount * self.risk_percentage, self.max_trade_amount)
        
        if trade_amount < 1.0:
            logger.warning(f"❌ Trade amount too small: ${trade_amount:.2f}")
            return False
        
        # Select trading pair
        selected_pair = self.select_optimal_trading_pair(balance)
        if not selected_pair:
            logger.warning("❌ No suitable trading pairs")
            return False
        
        # Execute trade
        success = self.execute_trade(selected_pair, trade_amount)
        
        if success:
            logger.info(f"✅ Cycle completed successfully - Trade #{self.trade_count}")
        else:
            logger.warning("❌ Cycle failed - Trade execution error")
        
        return success
    
    def run_autonomous_loop(self):
        """Main autonomous trading loop"""
        logger.info("🚀 Starting autonomous trading loop")
        
        # Test credentials first
        if not self.test_credentials():
            logger.error("❌ Credential test failed - stopping")
            return
        
        self.is_running = True
        cycle_count = 0
        
        while self.is_running:
            try:
                cycle_count += 1
                logger.info(f"🔄 Cycle #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Execute trading cycle
                self.autonomous_cycle()
                
                # Sleep for next cycle (4 minutes)
                logger.info("⏳ Waiting 240 seconds for next cycle...")
                time.sleep(240)
                
            except KeyboardInterrupt:
                logger.info("👋 Autonomous trading stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Cycle error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def start_autonomous_trading(self):
        """Start autonomous trading in background thread"""
        if self.is_running:
            logger.warning("Autonomous trading already running")
            return
        
        logger.info("🚀 Initializing autonomous trading system")
        
        # Start in background thread
        trading_thread = threading.Thread(target=self.run_autonomous_loop, daemon=True)
        trading_thread.start()
        
        logger.info("✅ Autonomous trading system started")
        return trading_thread
    
    def stop_autonomous_trading(self):
        """Stop autonomous trading"""
        self.is_running = False
        logger.info("🛑 Autonomous trading stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current trading status"""
        return {
            'is_running': self.is_running,
            'trade_count': self.trade_count,
            'last_trade': self.last_trade_time,
            'total_profit': self.total_profit,
            'balance': self.get_account_balance()
        }

# Global trader instance
autonomous_trader = None

def initialize_autonomous_trader():
    """Initialize and start the autonomous trader"""
    global autonomous_trader
    
    if autonomous_trader is None:
        autonomous_trader = CompleteAutonomousTrader()
        autonomous_trader.start_autonomous_trading()
        logger.info("✅ Complete autonomous trader initialized and started")
    
    return autonomous_trader

def get_trader_status():
    """Get current trader status"""
    if autonomous_trader:
        return autonomous_trader.get_status()
    return {'status': 'not_initialized'}

if __name__ == "__main__":
    # Direct execution
    trader = CompleteAutonomousTrader()
    trader.run_autonomous_loop()