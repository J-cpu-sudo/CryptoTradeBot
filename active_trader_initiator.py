#!/usr/bin/env python3
"""
Active Trader Initiator - Forces immediate trading execution
Implements aggressive strategies to initiate trades within current balance constraints
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime, timezone
from typing import Dict, Optional, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ActiveTraderInitiator:
    """Aggressive trading initiator for immediate execution"""
    
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Aggressive trading pairs - sorted by likelihood of success
        self.aggressive_pairs = [
            'PEPE-USDT',     # Meme coin with potential lower minimums
            'SHIB-USDT',     # High volume, established minimum
            'FLOKI-USDT',    # Previously viable option
            '1000SATS-USDT', # Bitcoin ordinals token
            'BONK-USDT',     # Solana ecosystem token
            'WIF-USDT',      # Alternative meme token
            'BOME-USDT',     # Book of Meme token
            'DOGE-USDT'      # Established memecoin
        ]
        
        # Maximum aggression settings
        self.max_balance_usage = 0.99  # Use 99% of balance
        self.minimum_fee_buffer = 0.001  # Minimal fee buffer
        
        logger.info("Active Trader Initiator ready for immediate execution")
    
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
    
    def api_request(self, method: str, endpoint: str, body: str = None) -> Optional[Dict]:
        """Make API request"""
        url = self.base_url + endpoint
        headers = self.get_headers(method, endpoint, body or '')
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def get_current_balance(self) -> float:
        """Get exact current balance"""
        response = self.api_request('GET', '/api/v5/account/balance')
        
        if response and response.get('code') == '0':
            for detail in response['data'][0]['details']:
                if detail['ccy'] == 'USDT':
                    balance = float(detail['availBal'])
                    logger.info(f"Current balance: ${balance:.8f}")
                    return balance
        return 0.0
    
    def scan_all_markets(self) -> List[Dict]:
        """Scan all available markets for opportunities"""
        logger.info("Scanning all available markets for immediate opportunities...")
        
        opportunities = []
        
        for symbol in self.aggressive_pairs:
            try:
                # Get instrument data
                inst_response = requests.get(
                    f"{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}",
                    timeout=10
                )
                
                # Get ticker data
                ticker_response = requests.get(
                    f"{self.base_url}/api/v5/market/ticker?instId={symbol}",
                    timeout=10
                )
                
                if (inst_response.status_code == 200 and ticker_response.status_code == 200):
                    instrument = inst_response.json()['data'][0]
                    ticker = ticker_response.json()['data'][0]
                    
                    market_data = {
                        'symbol': symbol,
                        'price': float(ticker['last']),
                        'min_size': float(instrument['minSz']),
                        'lot_size': float(instrument['lotSz']),
                        'volume_24h': float(ticker['vol24h']),
                        'min_order_value': float(instrument['minSz']) * float(ticker['last'])
                    }
                    
                    opportunities.append(market_data)
                    logger.info(f"{symbol}: Min order ${market_data['min_order_value']:.6f}")
                    
            except Exception as e:
                logger.debug(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by minimum order value (lowest first)
        opportunities.sort(key=lambda x: x['min_order_value'])
        return opportunities
    
    def calculate_maximum_quantity(self, market_data: Dict, balance: float) -> Optional[Dict]:
        """Calculate maximum possible quantity for immediate execution"""
        symbol = market_data['symbol']
        price = market_data['price']
        min_size = market_data['min_size']
        lot_size = market_data['lot_size']
        min_order_value = market_data['min_order_value']
        
        # Use maximum available balance
        max_usable = balance * self.max_balance_usage
        
        # Check if we can afford minimum order
        if max_usable < min_order_value:
            logger.debug(f"{symbol}: Max usable ${max_usable:.6f} < min required ${min_order_value:.6f}")
            return None
        
        # Calculate maximum quantity
        max_quantity = max_usable / price
        
        # Adjust for lot size
        if lot_size > 0:
            adjusted_quantity = int(max_quantity / lot_size) * lot_size
        else:
            adjusted_quantity = max_quantity
        
        # Final size check
        if adjusted_quantity < min_size:
            logger.debug(f"{symbol}: Adjusted quantity {adjusted_quantity:.6f} < minimum {min_size:.6f}")
            return None
        
        actual_cost = adjusted_quantity * price
        
        return {
            'symbol': symbol,
            'quantity': adjusted_quantity,
            'cost': actual_cost,
            'price': price,
            'market_data': market_data
        }
    
    def attempt_immediate_execution(self, trade_params: Dict) -> bool:
        """Attempt immediate trade execution with maximum aggression"""
        symbol = trade_params['symbol']
        quantity = trade_params['quantity']
        cost = trade_params['cost']
        
        logger.info(f"ATTEMPTING IMMEDIATE EXECUTION: {symbol}")
        logger.info(f"Quantity: {quantity:.8f}")
        logger.info(f"Cost: ${cost:.6f}")
        
        # Create order with maximum quantity
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
            
            logger.info("IMMEDIATE EXECUTION SUCCESSFUL!")
            logger.info(f"Order ID: {order_id}")
            logger.info(f"Symbol: {symbol}")
            logger.info(f"Quantity: {quantity:.8f}")
            logger.info(f"Cost: ${cost:.6f}")
            
            # Check new balance
            time.sleep(3)
            new_balance = self.get_current_balance()
            logger.info(f"New balance: ${new_balance:.8f}")
            
            return True
        else:
            error_msg = response.get('msg', 'Unknown error') if response else 'Request failed'
            logger.warning(f"Execution failed: {error_msg}")
            
            if response and response.get('data'):
                for error in response['data']:
                    logger.debug(f"Error {error.get('sCode')}: {error.get('sMsg')}")
            
            return False
    
    def force_immediate_trade(self) -> bool:
        """Force immediate trade execution using aggressive strategies"""
        logger.info("INITIATING FORCED IMMEDIATE TRADE EXECUTION")
        
        # Get current balance
        balance = self.get_current_balance()
        if balance < 0.1:
            logger.error(f"Balance too low for any trading: ${balance:.8f}")
            return False
        
        # Scan all markets for opportunities
        opportunities = self.scan_all_markets()
        if not opportunities:
            logger.error("No market opportunities found")
            return False
        
        logger.info(f"Found {len(opportunities)} potential markets")
        
        # Try each opportunity in order of increasing minimum requirements
        for market_data in opportunities:
            symbol = market_data['symbol']
            min_order_value = market_data['min_order_value']
            
            logger.info(f"Attempting {symbol} (min order: ${min_order_value:.6f})")
            
            # Calculate trade parameters
            trade_params = self.calculate_maximum_quantity(market_data, balance)
            if not trade_params:
                logger.info(f"{symbol}: Cannot meet minimum requirements")
                continue
            
            # Attempt immediate execution
            success = self.attempt_immediate_execution(trade_params)
            if success:
                logger.info(f"SUCCESS: Trade executed on {symbol}")
                return True
            else:
                logger.warning(f"FAILED: {symbol} execution unsuccessful")
                continue
        
        logger.error("All immediate execution attempts failed")
        return False
    
    def run_continuous_attempts(self, max_attempts: int = 10):
        """Run continuous execution attempts"""
        logger.info(f"Starting continuous execution attempts (max: {max_attempts})")
        
        for attempt in range(1, max_attempts + 1):
            logger.info(f"EXECUTION ATTEMPT #{attempt}")
            
            success = self.force_immediate_trade()
            if success:
                logger.info("EXECUTION SUCCESSFUL - AUTONOMOUS TRADING ACTIVATED")
                return True
            
            if attempt < max_attempts:
                logger.info("Waiting 30 seconds before next attempt...")
                time.sleep(30)
        
        logger.warning("All execution attempts exhausted")
        return False

def main():
    """Main execution function"""
    initiator = ActiveTraderInitiator()
    
    logger.info("=" * 60)
    logger.info("ACTIVE TRADING INITIATION SEQUENCE")
    logger.info("=" * 60)
    
    # Single immediate attempt
    success = initiator.force_immediate_trade()
    
    if success:
        logger.info("✅ IMMEDIATE EXECUTION SUCCESSFUL")
        logger.info("🚀 AUTONOMOUS TRADING NOW ACTIVE")
    else:
        logger.warning("❌ IMMEDIATE EXECUTION FAILED")
        logger.info("Initiating continuous attempts...")
        initiator.run_continuous_attempts()

if __name__ == "__main__":
    main()