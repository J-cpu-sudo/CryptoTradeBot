#!/usr/bin/env python3
"""
Precise Balance Trader - Execute trades with exact fee calculations
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PreciseBalanceTrader:
    """Execute trades with precise balance and fee calculations"""
    
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # OKX fee structure
        self.maker_fee = 0.0008  # 0.08%
        self.taker_fee = 0.001   # 0.1%
        
        logger.info("Precise Balance Trader initialized with fee calculations")
    
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
        url = self.base_url + endpoint
        headers = self.get_headers(method, endpoint, body or '')
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=15)
            
            return response
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def get_balance(self) -> float:
        """Get exact USDT balance"""
        response = self.api_request('GET', '/api/v5/account/balance')
        
        if response and response.status_code == 200:
            data = response.json()
            if data.get('code') == '0':
                for detail in data['data'][0]['details']:
                    if detail['ccy'] == 'USDT':
                        balance = float(detail['availBal'])
                        logger.info(f"Current balance: ${balance:.10f}")
                        return balance
        return 0.0
    
    def calculate_precise_order_size(self, symbol: str, balance: float) -> dict:
        """Calculate precise order size accounting for fees and minimums"""
        
        # Get instrument specifications
        inst_response = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
        if not inst_response or inst_response.status_code != 200:
            return None
        
        inst_data = inst_response.json()
        if not inst_data.get('data'):
            return None
        
        instrument = inst_data['data'][0]
        min_size = float(instrument['minSz'])
        tick_size = float(instrument['tickSz'])
        
        # Get current price
        ticker_response = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
        if not ticker_response or ticker_response.status_code != 200:
            return None
        
        ticker_data = ticker_response.json()
        if not ticker_data.get('data'):
            return None
        
        current_price = float(ticker_data['data'][0]['last'])
        
        # Calculate maximum usable balance (reserve for fees)
        fee_buffer = balance * (self.taker_fee + 0.0002)  # Extra 0.02% buffer
        usable_balance = balance - fee_buffer
        
        # Calculate quantity
        raw_quantity = usable_balance / current_price
        
        # Ensure we meet minimum size
        if raw_quantity < min_size:
            logger.warning(f"Calculated quantity {raw_quantity:.8f} below minimum {min_size}")
            return None
        
        # Round to appropriate precision
        adjusted_quantity = min_size * round(raw_quantity / min_size)
        
        # Final validation
        estimated_cost = adjusted_quantity * current_price
        estimated_fee = estimated_cost * self.taker_fee
        total_required = estimated_cost + estimated_fee
        
        if total_required > balance:
            logger.warning(f"Total required ${total_required:.8f} exceeds balance ${balance:.8f}")
            return None
        
        logger.info(f"Precise calculation for {symbol}:")
        logger.info(f"  Price: ${current_price:.8f}")
        logger.info(f"  Quantity: {adjusted_quantity:.8f}")
        logger.info(f"  Cost: ${estimated_cost:.8f}")
        logger.info(f"  Fee: ${estimated_fee:.8f}")
        logger.info(f"  Total: ${total_required:.8f}")
        
        return {
            'symbol': symbol,
            'price': current_price,
            'quantity': adjusted_quantity,
            'cost': estimated_cost,
            'fee': estimated_fee,
            'total': total_required
        }
    
    def execute_precise_buy(self, order_params: dict) -> bool:
        """Execute buy order with precise calculations"""
        symbol = order_params['symbol']
        quantity = order_params['quantity']
        
        logger.info(f"Executing precise buy order for {symbol}")
        
        # Use limit order at current market price for better control
        order_data = {
            "instId": symbol,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "limit",
            "sz": str(quantity),
            "px": str(order_params['price'])
        }
        
        order_body = json.dumps(order_data)
        response = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if response and response.status_code == 200:
            result = response.json()
            if result.get('code') == '0':
                order_id = result['data'][0]['ordId']
                logger.info(f"✓ Buy order placed successfully: {order_id}")
                
                # Wait for fill
                time.sleep(5)
                
                # Check order status
                status_response = self.api_request('GET', f'/api/v5/trade/order?instId={symbol}&ordId={order_id}')
                if status_response and status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get('code') == '0':
                        order_status = status_data['data'][0]['state']
                        logger.info(f"Order status: {order_status}")
                        
                        if order_status == 'filled':
                            logger.info("✓ Buy order filled successfully")
                            return True
                        elif order_status == 'live':
                            logger.info("Order still pending - may need price adjustment")
                
                # If not filled, cancel and try market order
                cancel_data = {"instId": symbol, "ordId": order_id}
                cancel_body = json.dumps(cancel_data)
                self.api_request('POST', '/api/v5/trade/cancel-order', cancel_body)
                
                # Try market order as fallback
                market_order_data = {
                    "instId": symbol,
                    "tdMode": "cash",
                    "side": "buy",
                    "ordType": "market",
                    "sz": str(quantity)
                }
                
                market_body = json.dumps(market_order_data)
                market_response = self.api_request('POST', '/api/v5/trade/order', market_body)
                
                if market_response and market_response.status_code == 200:
                    market_result = market_response.json()
                    if market_result.get('code') == '0':
                        logger.info("✓ Market order executed successfully")
                        return True
            
            logger.error(f"Order failed: {result.get('msg')}")
            return False
        
        logger.error("Order request failed")
        return False
    
    def find_optimal_trading_pair(self):
        """Find the optimal trading pair for current balance"""
        balance = self.get_balance()
        
        test_pairs = [
            'MEME-USDT',   # Previously had lowest minimum
            'NEIRO-USDT',  # Alternative low minimum
            'SATS-USDT',   # Bitcoin ordinals
            'CAT-USDT',    # Alternative option
        ]
        
        for symbol in test_pairs:
            order_params = self.calculate_precise_order_size(symbol, balance)
            if order_params:
                logger.info(f"✓ {symbol} is viable for precise trading")
                return order_params
            else:
                logger.info(f"✗ {symbol} not viable with current balance")
        
        return None
    
    def execute_trading_strategy(self):
        """Execute complete precision trading strategy"""
        logger.info("EXECUTING PRECISION TRADING STRATEGY")
        logger.info("=" * 50)
        
        # Find optimal pair
        order_params = self.find_optimal_trading_pair()
        if not order_params:
            logger.error("No viable trading pairs found")
            return False
        
        # Execute buy order
        success = self.execute_precise_buy(order_params)
        
        if success:
            logger.info("✓ PRECISION TRADING SUCCESSFUL")
            
            # Check new balance
            time.sleep(3)
            new_balance = self.get_balance()
            logger.info(f"Post-trade balance: ${new_balance:.8f}")
            
            return True
        else:
            logger.error("❌ PRECISION TRADING FAILED")
            return False

def main():
    """Execute precision trading"""
    trader = PreciseBalanceTrader()
    success = trader.execute_trading_strategy()
    
    if success:
        logger.info("Precision trading completed successfully")
    else:
        logger.info("Precision trading unsuccessful")

if __name__ == "__main__":
    main()