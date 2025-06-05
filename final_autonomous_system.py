#!/usr/bin/env python3
"""
Final Autonomous Trading System - Complete Configuration with Fixed Authentication
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

class FinalAutonomousSystem:
    """Complete autonomous trading system with fixed authentication and full configuration"""
    
    def __init__(self):
        self.api_key = os.environ.get('OKX_API_KEY')
        self.secret_key = os.environ.get('OKX_SECRET_KEY') 
        self.passphrase = os.environ.get('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Trading pairs optimized for low balance requirements
        self.trading_pairs = [
            'DOGE-USDT',    # Very low minimum order
            'TRX-USDT',     # Low minimum order
            'SHIB-USDT',    # Ultra low minimum
            'PEPE-USDT',    # Meme coin with low requirements
            'XRP-USDT',     # Established, reasonable minimums
            'FLOKI-USDT'    # Alternative low-requirement option
        ]
        
        # Enhanced trading configuration
        self.max_trade_amount = 5.0
        self.min_balance_threshold = 0.5
        self.risk_percentage = 0.85
        self.trade_cooldown = 240  # 4 minutes
        
        # System state
        self.is_running = False
        self.last_trade_time = 0
        self.trade_count = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_volume = 0.0
        
        # Performance tracking
        self.start_time = time.time()
        self.market_cache = {}
        self.cache_duration = 30
        
        logger.info("Final Autonomous System initialized with enhanced configuration")
    
    def get_precise_timestamp(self) -> str:
        """Get precise UTC timestamp in ISO format for OKX API"""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """Generate OKX API signature with precise timestamp handling"""
        try:
            message = timestamp + method + request_path + body
            mac = hmac.new(
                bytes(self.secret_key, encoding='utf8'),
                bytes(message, encoding='utf-8'),
                digestmod=hashlib.sha256
            )
            return base64.b64encode(mac.digest()).decode()
        except Exception as e:
            logger.error(f"Signature generation failed: {e}")
            return ""
    
    def get_authenticated_headers(self, method: str, request_path: str, body: str = '') -> Dict[str, str]:
        """Get authenticated headers with precise timestamp"""
        timestamp = self.get_precise_timestamp()
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }
    
    def execute_api_request(self, method: str, endpoint: str, body: str = None, authenticated: bool = True) -> Optional[Dict]:
        """Execute API request with comprehensive error handling"""
        url = self.base_url + endpoint
        
        try:
            headers = self.get_authenticated_headers(method, endpoint, body or '') if authenticated else {}
            
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            elif method == 'POST':
                response = requests.post(url, headers=headers, data=body, timeout=15)
            else:
                return None
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"API request failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None
    
    def verify_trading_capabilities(self) -> Dict[str, Any]:
        """Comprehensive verification of trading capabilities"""
        logger.info("Verifying trading capabilities...")
        
        result = {
            'balance_access': False,
            'trading_permissions': False,
            'current_balance': 0.0,
            'error_details': None
        }
        
        # Test balance access
        balance_response = self.execute_api_request('GET', '/api/v5/account/balance')
        if balance_response and balance_response.get('code') == '0':
            result['balance_access'] = True
            
            # Extract USDT balance
            for detail in balance_response['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    result['current_balance'] = float(detail['availBal'])
                    break
            
            logger.info(f"Balance access verified: ${result['current_balance']:.2f} USDT")
        else:
            result['error_details'] = balance_response
            logger.error("Balance access failed")
            return result
        
        # Test trading permissions with minimal test order
        test_order = {
            "instId": "DOGE-USDT",
            "tdMode": "cash", 
            "side": "buy",
            "ordType": "limit",
            "sz": "1",
            "px": "0.001"  # Very low price to avoid execution
        }
        
        test_body = json.dumps(test_order)
        trade_response = self.execute_api_request('POST', '/api/v5/trade/order', test_body)
        
        if trade_response and trade_response.get('code') == '0':
            result['trading_permissions'] = True
            
            # Cancel the test order immediately
            order_id = trade_response['data'][0]['ordId']
            cancel_order = {"instId": "DOGE-USDT", "ordId": order_id}
            cancel_body = json.dumps(cancel_order)
            self.execute_api_request('POST', '/api/v5/trade/cancel-order', cancel_body)
            
            logger.info("Trading permissions verified successfully")
        else:
            result['error_details'] = trade_response
            logger.error("Trading permissions not available")
        
        return result
    
    def get_optimal_market_data(self, symbol: str) -> Optional[Dict]:
        """Get comprehensive market data with caching"""
        current_time = time.time()
        
        # Check cache first
        if symbol in self.market_cache:
            cached = self.market_cache[symbol]
            if current_time - cached['timestamp'] < self.cache_duration:
                return cached['data']
        
        # Fetch fresh market data
        ticker_data = self.execute_api_request('GET', f'/api/v5/market/ticker?instId={symbol}', authenticated=False)
        
        if ticker_data and ticker_data.get('data'):
            market_info = ticker_data['data'][0]
            
            # Get instrument specifications
            instrument_data = self.execute_api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}', authenticated=False)
            
            if instrument_data and instrument_data.get('data'):
                instrument_info = instrument_data['data'][0]
                
                enhanced_data = {
                    'symbol': symbol,
                    'price': float(market_info['last']),
                    'volume_24h': float(market_info['vol24h']),
                    'change_24h': float(market_info['sodUtc0']),
                    'bid': float(market_info['bidPx']),
                    'ask': float(market_info['askPx']),
                    'min_size': float(instrument_info.get('minSz', '1')),
                    'lot_size': float(instrument_info.get('lotSz', '1')),
                    'tick_size': float(instrument_info.get('tickSz', '0.000001'))
                }
                
                # Cache the data
                self.market_cache[symbol] = {
                    'data': enhanced_data,
                    'timestamp': current_time
                }
                
                return enhanced_data
        
        return None
    
    def analyze_trading_opportunity(self, symbol: str, available_balance: float) -> Dict[str, Any]:
        """Advanced analysis of trading opportunity"""
        market_data = self.get_optimal_market_data(symbol)
        if not market_data:
            return {'viable': False, 'reason': 'No market data available'}
        
        analysis = {
            'symbol': symbol,
            'viable': False,
            'reason': '',
            'market_data': market_data,
            'trade_amount': 0.0,
            'quantity': 0.0,
            'estimated_cost': 0.0
        }
        
        current_price = market_data['price']
        volume_24h = market_data['volume_24h']
        min_size = market_data['min_size']
        lot_size = market_data['lot_size']
        
        # Volume filter - ensure sufficient liquidity
        if volume_24h < 500000:  # $500K minimum daily volume
            analysis['reason'] = f'Low volume: ${volume_24h:,.0f}'
            return analysis
        
        # Volatility filter - avoid extreme movements
        price_change = abs(market_data['change_24h'])
        if price_change > 25:  # Avoid >25% daily moves
            analysis['reason'] = f'High volatility: {price_change:.1f}%'
            return analysis
        
        # Calculate optimal trade amount
        max_trade = min(available_balance * self.risk_percentage, self.max_trade_amount)
        if max_trade < 1.0:
            analysis['reason'] = f'Insufficient funds: ${max_trade:.2f}'
            return analysis
        
        # Calculate quantity and adjust for lot size
        base_quantity = max_trade / current_price
        if lot_size > 0:
            adjusted_quantity = int(base_quantity / lot_size) * lot_size
        else:
            adjusted_quantity = base_quantity
        
        # Verify minimum size requirements
        if adjusted_quantity < min_size:
            analysis['reason'] = f'Below minimum size: {adjusted_quantity:.4f} < {min_size:.4f}'
            return analysis
        
        # Calculate final trade parameters
        estimated_cost = adjusted_quantity * current_price
        
        analysis.update({
            'viable': True,
            'reason': 'Trade opportunity identified',
            'trade_amount': max_trade,
            'quantity': adjusted_quantity,
            'estimated_cost': estimated_cost
        })
        
        return analysis
    
    def execute_market_trade(self, analysis: Dict[str, Any]) -> bool:
        """Execute market trade based on analysis"""
        symbol = analysis['symbol']
        quantity = analysis['quantity']
        estimated_cost = analysis['estimated_cost']
        
        logger.info(f"Executing trade: {symbol}")
        logger.info(f"Quantity: {quantity:.6f}")
        logger.info(f"Estimated cost: ${estimated_cost:.2f}")
        
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy", 
            "ordType": "market",
            "sz": str(quantity)
        }
        
        order_body = json.dumps(order_data)
        response = self.execute_api_request('POST', '/api/v5/trade/order', order_body)
        
        if response and response.get('code') == '0':
            order_id = response['data'][0]['ordId']
            
            # Update statistics
            self.trade_count += 1
            self.successful_trades += 1
            self.total_volume += estimated_cost
            self.last_trade_time = time.time()
            
            logger.info("TRADE EXECUTED SUCCESSFULLY")
            logger.info(f"Order ID: {order_id}")
            logger.info(f"Total trades: {self.trade_count}")
            logger.info(f"Success rate: {(self.successful_trades/self.trade_count)*100:.1f}%")
            
            return True
        else:
            self.failed_trades += 1
            error_msg = response.get('msg', 'Unknown error') if response else 'Request failed'
            logger.error(f"Trade execution failed: {error_msg}")
            return False
    
    def find_best_trading_opportunity(self, balance: float) -> Optional[Dict]:
        """Find the best trading opportunity from available pairs"""
        logger.info("Scanning for optimal trading opportunities...")
        
        opportunities = []
        
        for symbol in self.trading_pairs:
            analysis = self.analyze_trading_opportunity(symbol, balance)
            if analysis['viable']:
                # Score based on volume and trade size
                score = (analysis['market_data']['volume_24h'] / 1000000) + (analysis['trade_amount'] / 10)
                analysis['score'] = score
                opportunities.append(analysis)
                logger.info(f"{symbol}: Score {score:.2f} - Viable")
            else:
                logger.info(f"{symbol}: {analysis['reason']}")
        
        if not opportunities:
            logger.warning("No viable trading opportunities found")
            return None
        
        # Select highest scoring opportunity
        best_opportunity = max(opportunities, key=lambda x: x['score'])
        logger.info(f"Selected: {best_opportunity['symbol']} (Score: {best_opportunity['score']:.2f})")
        
        return best_opportunity
    
    def execute_autonomous_cycle(self) -> bool:
        """Execute one complete autonomous trading cycle"""
        logger.info("Starting autonomous trading cycle")
        
        # Check cooldown period
        if time.time() - self.last_trade_time < self.trade_cooldown:
            remaining = self.trade_cooldown - (time.time() - self.last_trade_time)
            logger.info(f"Cooldown active: {remaining:.0f}s remaining")
            return False
        
        # Verify system capabilities
        verification = self.verify_trading_capabilities()
        if not verification['balance_access'] or not verification['trading_permissions']:
            logger.error("System verification failed")
            return False
        
        balance = verification['current_balance']
        if balance < self.min_balance_threshold:
            logger.warning(f"Insufficient balance: ${balance:.2f}")
            return False
        
        # Find and execute best opportunity
        opportunity = self.find_best_trading_opportunity(balance)
        if not opportunity:
            logger.warning("No trading opportunities available")
            return False
        
        # Execute the trade
        success = self.execute_market_trade(opportunity)
        
        if success:
            logger.info("Autonomous cycle completed successfully")
        else:
            logger.warning("Autonomous cycle failed during execution")
        
        return success
    
    def run_continuous_autonomous_loop(self):
        """Main continuous autonomous trading loop"""
        logger.info("STARTING CONTINUOUS AUTONOMOUS TRADING SYSTEM")
        
        # Initial system verification
        verification = self.verify_trading_capabilities()
        if not verification['balance_access']:
            logger.error("Cannot access account balance - stopping")
            return
        
        if not verification['trading_permissions']:
            logger.error("Trading permissions not enabled - stopping")
            return
        
        logger.info(f"System verified - Starting with ${verification['current_balance']:.2f} USDT")
        
        self.is_running = True
        cycle_number = 0
        
        while self.is_running:
            try:
                cycle_number += 1
                logger.info(f"CYCLE #{cycle_number} - {datetime.now().strftime('%H:%M:%S UTC')}")
                
                # Execute trading cycle
                self.execute_autonomous_cycle()
                
                # Performance summary every 10 cycles
                if cycle_number % 10 == 0:
                    runtime = (time.time() - self.start_time) / 3600
                    logger.info(f"Performance Summary - Runtime: {runtime:.1f}h")
                    logger.info(f"Total trades: {self.trade_count}")
                    logger.info(f"Success rate: {(self.successful_trades/max(1,self.trade_count))*100:.1f}%")
                    logger.info(f"Total volume: ${self.total_volume:.2f}")
                
                # Wait for next cycle
                logger.info("Waiting 240 seconds for next cycle...")
                time.sleep(240)
                
            except KeyboardInterrupt:
                logger.info("Autonomous trading stopped by user")
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                time.sleep(60)  # Wait 1 minute on error
        
        logger.info("Autonomous trading system stopped")
    
    def start_background_trading(self):
        """Start autonomous trading in background thread"""
        if self.is_running:
            logger.warning("Autonomous trading already running")
            return
        
        logger.info("Initializing background autonomous trading")
        trading_thread = threading.Thread(target=self.run_continuous_autonomous_loop, daemon=True)
        trading_thread.start()
        logger.info("Background autonomous trading started")
        return trading_thread
    
    def stop_trading(self):
        """Stop autonomous trading"""
        self.is_running = False
        logger.info("Autonomous trading stopped")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        runtime = (time.time() - self.start_time) / 3600
        success_rate = (self.successful_trades / max(1, self.trade_count)) * 100
        
        return {
            'is_running': self.is_running,
            'runtime_hours': runtime,
            'total_trades': self.trade_count,
            'successful_trades': self.successful_trades,
            'failed_trades': self.failed_trades,
            'success_rate': success_rate,
            'total_volume': self.total_volume,
            'last_trade_time': self.last_trade_time,
            'current_balance': self.verify_trading_capabilities().get('current_balance', 0.0)
        }

# Global system instance
autonomous_system = None

def initialize_final_autonomous_system():
    """Initialize and start the final autonomous system"""
    global autonomous_system
    
    if autonomous_system is None:
        autonomous_system = FinalAutonomousSystem()
        autonomous_system.start_background_trading()
        logger.info("Final autonomous system initialized and started")
    
    return autonomous_system

def get_system_status():
    """Get current system status"""
    if autonomous_system:
        return autonomous_system.get_system_status()
    return {'status': 'not_initialized'}

if __name__ == "__main__":
    # Direct execution for testing
    system = FinalAutonomousSystem()
    system.run_continuous_autonomous_loop()