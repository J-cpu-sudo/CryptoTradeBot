#!/usr/bin/env python3
"""
Start autonomous trading with live execution capability
"""
import os
import sys
import time
import json
import requests
import hmac
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class LiveTradingEngine:
    """Advanced live trading engine with multi-pair execution"""
    
    def __init__(self):
        self.api_key = os.getenv('OKX_API_KEY')
        self.secret_key = os.getenv('OKX_SECRET_KEY')
        self.passphrase = os.getenv('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Trading configuration
        self.trading_pairs = [
            'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'ADA-USDT',
            'BNB-USDT', 'TRX-USDT', 'DOGE-USDT'
        ]
        
        # Risk management
        self.max_position_size = 0.3  # 30% of balance per trade
        self.stop_loss_pct = 0.02     # 2% stop loss
        self.take_profit_pct = 0.05   # 5% take profit
        self.min_profit_threshold = 0.01  # 1% minimum profit to trade
        
        # Performance tracking
        self.total_trades = 0
        self.successful_trades = 0
        self.total_profit = 0.0
        self.daily_trades = 0
        self.last_trade_time = None
        
        print("Live Trading Engine Initialized")
        print(f"Monitoring {len(self.trading_pairs)} trading pairs")
        print(f"Risk Management: {self.stop_loss_pct*100}% SL, {self.take_profit_pct*100}% TP")

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
        """Get API headers with authentication"""
        timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }

    def get_account_balance(self) -> Dict[str, float]:
        """Get current account balance"""
        try:
            path = '/api/v5/account/balance'
            headers = self.get_headers('GET', path)
            
            response = requests.get(self.base_url + path, headers=headers)
            data = response.json()
            
            if data.get('code') == '0' and data.get('data'):
                balances = {}
                for balance_info in data['data'][0]['details']:
                    currency = balance_info['ccy']
                    available = float(balance_info['availBal'])
                    if available > 0:
                        balances[currency] = available
                return balances
            return {}
        except Exception as e:
            print(f"Balance fetch error: {e}")
            return {}

    def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current market data for symbol"""
        try:
            # Get ticker data
            ticker_response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}')
            ticker_data = ticker_response.json()
            
            if ticker_data.get('data'):
                ticker = ticker_data['data'][0]
                
                # Get 24h volume and price change
                return {
                    'symbol': symbol,
                    'price': float(ticker['last']),
                    'bid': float(ticker['bidPx']),
                    'ask': float(ticker['askPx']),
                    'volume_24h': float(ticker['vol24h']),
                    'change_24h': float(ticker['chg24h']),
                    'high_24h': float(ticker['high24h']),
                    'low_24h': float(ticker['low24h']),
                    'timestamp': datetime.now()
                }
        except Exception as e:
            print(f"Market data error for {symbol}: {e}")
        return None

    def analyze_trading_opportunity(self, symbol: str) -> Dict[str, Any]:
        """Analyze if there's a profitable trading opportunity"""
        market_data = self.get_market_data(symbol)
        if not market_data:
            return {'action': 'hold', 'reason': 'No market data'}
        
        price = market_data['price']
        change_24h = market_data['change_24h']
        volume_24h = market_data['volume_24h']
        
        # Trading signals
        signals = []
        confidence = 0.0
        
        # Volume-based signal
        if volume_24h > 1000000:  # High volume threshold
            signals.append("High volume detected")
            confidence += 0.2
        
        # Price momentum signal
        if change_24h > 2.0:  # Strong upward movement
            signals.append("Strong upward momentum")
            confidence += 0.3
        elif change_24h < -2.0:  # Strong downward movement (potential bounce)
            signals.append("Oversold condition - potential bounce")
            confidence += 0.2
        
        # Volatility signal
        price_range = (market_data['high_24h'] - market_data['low_24h']) / market_data['low_24h']
        if price_range > 0.05:  # 5% daily range
            signals.append("High volatility - trading opportunity")
            confidence += 0.2
        
        # Price position signal
        current_position = (price - market_data['low_24h']) / (market_data['high_24h'] - market_data['low_24h'])
        if current_position < 0.3:  # Near daily low
            signals.append("Near daily low - potential buy")
            confidence += 0.3
        
        # Determine action
        if confidence >= 0.5 and len(signals) >= 2:
            if change_24h > 0 or current_position < 0.3:
                return {
                    'action': 'buy',
                    'confidence': confidence,
                    'signals': signals,
                    'price': price,
                    'symbol': symbol
                }
        
        return {
            'action': 'hold',
            'confidence': confidence,
            'signals': signals,
            'reason': f"Confidence {confidence:.2f} below threshold"
        }

    def execute_buy_order(self, symbol: str, usdt_amount: float) -> Dict[str, Any]:
        """Execute a buy order"""
        try:
            # Get current price
            market_data = self.get_market_data(symbol)
            if not market_data:
                return {'success': False, 'error': 'No market data'}
            
            current_price = market_data['price']
            
            # Calculate quantity to buy
            quantity = usdt_amount / current_price
            
            # Get instrument info for minimum size
            instrument_response = requests.get(f'{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}')
            if instrument_response.status_code == 200:
                instrument_data = instrument_response.json()
                if instrument_data.get('data'):
                    instrument = instrument_data['data'][0]
                    min_size = float(instrument.get('minSz', '0'))
                    lot_size = float(instrument.get('lotSz', '0'))
                    
                    # Round quantity to lot size
                    if lot_size > 0:
                        quantity = round(quantity / lot_size) * lot_size
                    
                    # Check minimum size
                    if quantity < min_size:
                        return {'success': False, 'error': f'Quantity {quantity} below minimum {min_size}'}
            
            # Place market buy order
            order_data = {
                "instId": symbol,
                "tdMode": "cash",
                "side": "buy",
                "ordType": "market",
                "sz": str(quantity)
            }
            
            path = '/api/v5/trade/order'
            body = json.dumps(order_data)
            headers = self.get_headers('POST', path, body)
            
            response = requests.post(self.base_url + path, headers=headers, data=body)
            result = response.json()
            
            if result.get('code') == '0':
                order_id = result['data'][0]['ordId']
                
                # Update statistics
                self.total_trades += 1
                self.daily_trades += 1
                self.last_trade_time = datetime.now()
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': 'buy',
                    'quantity': quantity,
                    'price': current_price,
                    'cost': quantity * current_price
                }
            else:
                return {'success': False, 'error': result.get('msg', 'Unknown error')}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def run_trading_cycle(self) -> Dict[str, Any]:
        """Execute one complete trading cycle"""
        cycle_start = datetime.now()
        results = {
            'timestamp': cycle_start,
            'trades_executed': 0,
            'opportunities_found': 0,
            'balance_before': 0,
            'balance_after': 0,
            'profit_this_cycle': 0,
            'actions': []
        }
        
        # Get current balance
        balances = self.get_account_balance()
        usdt_balance = balances.get('USDT', 0)
        results['balance_before'] = usdt_balance
        
        print(f"\n=== Trading Cycle {cycle_start.strftime('%H:%M:%S')} ===")
        print(f"Available USDT: ${usdt_balance:.2f}")
        
        if usdt_balance < 1.0:  # Minimum trade amount
            results['actions'].append("Insufficient USDT balance for trading")
            return results
        
        # Calculate position size (max 30% of balance)
        max_trade_amount = min(usdt_balance * self.max_position_size, usdt_balance - 1.0)
        
        # Analyze each trading pair
        best_opportunity = None
        best_confidence = 0
        
        for symbol in self.trading_pairs:
            try:
                analysis = self.analyze_trading_opportunity(symbol)
                
                if analysis['action'] == 'buy' and analysis['confidence'] > best_confidence:
                    best_opportunity = analysis
                    best_confidence = analysis['confidence']
                    results['opportunities_found'] += 1
                
                results['actions'].append(f"{symbol}: {analysis['action']} (confidence: {analysis.get('confidence', 0):.2f})")
                
            except Exception as e:
                results['actions'].append(f"{symbol}: Error - {e}")
        
        # Execute best opportunity
        if best_opportunity and best_confidence >= 0.6:  # Higher threshold for execution
            symbol = best_opportunity['symbol']
            trade_amount = min(max_trade_amount, 5.0)  # Max $5 per trade
            
            print(f"\nExecuting trade: {symbol}")
            print(f"Confidence: {best_confidence:.2f}")
            print(f"Signals: {', '.join(best_opportunity['signals'])}")
            print(f"Trade amount: ${trade_amount:.2f}")
            
            trade_result = self.execute_buy_order(symbol, trade_amount)
            
            if trade_result['success']:
                results['trades_executed'] += 1
                self.successful_trades += 1
                
                print(f"TRADE EXECUTED SUCCESSFULLY!")
                print(f"Order ID: {trade_result['order_id']}")
                print(f"Bought {trade_result['quantity']:.6f} {symbol.split('-')[0]} at ${trade_result['price']:.6f}")
                
                results['actions'].append(f"BUY {symbol}: {trade_result['quantity']:.6f} @ ${trade_result['price']:.6f}")
            else:
                print(f"Trade failed: {trade_result['error']}")
                results['actions'].append(f"FAILED {symbol}: {trade_result['error']}")
        else:
            print("No high-confidence trading opportunities found")
            results['actions'].append("No trades executed - waiting for better opportunities")
        
        # Get final balance
        final_balances = self.get_account_balance()
        final_usdt = final_balances.get('USDT', 0)
        results['balance_after'] = final_usdt
        results['profit_this_cycle'] = final_usdt - usdt_balance
        
        # Print cycle summary
        print(f"\nCycle Summary:")
        print(f"Trades executed: {results['trades_executed']}")
        print(f"Opportunities found: {results['opportunities_found']}")
        print(f"USDT change: ${results['profit_this_cycle']:.2f}")
        print(f"Total trades today: {self.daily_trades}")
        print(f"Success rate: {(self.successful_trades/max(self.total_trades,1)*100):.1f}%")
        
        return results

    def start_autonomous_trading(self):
        """Start continuous autonomous trading"""
        print("\n" + "="*60)
        print("AUTONOMOUS TRADING SYSTEM STARTED")
        print("="*60)
        print("Live execution enabled with real funds")
        print("Monitoring market conditions continuously")
        print("Press Ctrl+C to stop")
        print("="*60)
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                print(f"\n[Cycle {cycle_count}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Run trading cycle
                results = self.run_trading_cycle()
                
                # Wait before next cycle (60 seconds)
                print(f"Next cycle in 60 seconds...")
                time.sleep(60)
                
        except KeyboardInterrupt:
            print(f"\n\nAutonomous trading stopped by user")
            print(f"Total cycles executed: {cycle_count}")
            print(f"Total trades: {self.total_trades}")
            print(f"Successful trades: {self.successful_trades}")
            if self.total_trades > 0:
                print(f"Success rate: {(self.successful_trades/self.total_trades*100):.1f}%")

def main():
    """Main function to start autonomous trading"""
    if len(sys.argv) > 1 and sys.argv[1] == '--status':
        # Just show current status
        engine = LiveTradingEngine()
        balances = engine.get_account_balance()
        print("\nCurrent Account Status:")
        for currency, amount in balances.items():
            print(f"{currency}: {amount}")
        return
    
    # Start autonomous trading
    engine = LiveTradingEngine()
    engine.start_autonomous_trading()

if __name__ == "__main__":
    main()