#!/usr/bin/env python3
"""
Autonomous Live Trading Engine - Fixed Context Issues
"""
import os
import time
import json
import requests
import hmac
import hashlib
import base64
from datetime import datetime
import threading
from typing import Dict, List, Any, Optional

class AutonomousLiveTrader:
    """Standalone autonomous trading engine with live execution"""
    
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
        
        # Enhanced trading parameters
        self.max_position_size = 0.25  # 25% of balance per trade
        self.stop_loss_pct = 0.03      # 3% stop loss
        self.take_profit_pct = 0.06    # 6% take profit
        self.confidence_threshold = 0.65  # 65% confidence minimum
        
        # Performance tracking
        self.total_trades = 0
        self.successful_trades = 0
        self.total_profit = 0.0
        self.last_trade_time = None
        self.is_running = False
        
        print("Autonomous Live Trading Engine Initialized")
        print(f"Monitoring {len(self.trading_pairs)} pairs")
        print(f"Risk: {self.stop_loss_pct*100}% SL, {self.take_profit_pct*100}% TP")

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
                total_equity = 0.0
                for balance_info in data['data'][0]['details']:
                    currency = balance_info['ccy']
                    available = float(balance_info['availBal'])
                    equity = float(balance_info['eq'])
                    if available > 0:
                        balances[currency] = available
                    total_equity += equity
                balances['TOTAL_EQUITY'] = total_equity
                return balances
            return {}
        except Exception as e:
            print(f"Balance fetch error: {e}")
            return {}

    def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive market data for symbol"""
        try:
            # Get ticker data
            ticker_response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}')
            ticker_data = ticker_response.json()
            
            if ticker_data.get('data'):
                ticker = ticker_data['data'][0]
                
                # Get 24h candle data for trend analysis
                candle_response = requests.get(f'{self.base_url}/api/v5/market/candles?instId={symbol}&bar=1H&limit=24')
                candle_data = candle_response.json()
                
                candles = candle_data.get('data', [])
                
                return {
                    'symbol': symbol,
                    'price': float(ticker['last']),
                    'bid': float(ticker['bidPx']),
                    'ask': float(ticker['askPx']),
                    'volume_24h': float(ticker['vol24h']),
                    'change_24h': float(ticker.get('chg24h', '0')),
                    'high_24h': float(ticker['high24h']),
                    'low_24h': float(ticker['low24h']),
                    'candles': candles,
                    'timestamp': datetime.now()
                }
        except Exception as e:
            print(f"Market data error for {symbol}: {e}")
        return None

    def calculate_technical_indicators(self, candles: List[List[str]]) -> Dict[str, float]:
        """Calculate technical indicators from candle data"""
        if len(candles) < 14:
            return {}
        
        try:
            # Extract closing prices (index 4 in OHLCV)
            closes = [float(candle[4]) for candle in candles]
            highs = [float(candle[2]) for candle in candles]
            lows = [float(candle[3]) for candle in candles]
            volumes = [float(candle[5]) for candle in candles]
            
            # Simple Moving Averages
            sma_5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else closes[-1]
            sma_10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else closes[-1]
            sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
            
            # RSI calculation
            gains = []
            losses = []
            for i in range(1, len(closes)):
                change = closes[i] - closes[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains[-14:]) / 14 if len(gains) >= 14 else 0
            avg_loss = sum(losses[-14:]) / 14 if len(losses) >= 14 else 1
            
            rs = avg_gain / avg_loss if avg_loss > 0 else 0
            rsi = 100 - (100 / (1 + rs))
            
            # Volume trend
            volume_trend = sum(volumes[-5:]) / sum(volumes[-10:-5]) if len(volumes) >= 10 else 1
            
            # Price momentum
            momentum = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0
            
            return {
                'sma_5': sma_5,
                'sma_10': sma_10,
                'sma_20': sma_20,
                'rsi': rsi,
                'volume_trend': volume_trend,
                'momentum': momentum,
                'current_price': closes[-1]
            }
        except Exception as e:
            print(f"Technical indicator error: {e}")
            return {}

    def analyze_trading_opportunity(self, symbol: str) -> Dict[str, Any]:
        """Advanced trading opportunity analysis"""
        market_data = self.get_market_data(symbol)
        if not market_data:
            return {'action': 'hold', 'reason': 'No market data', 'confidence': 0.0}
        
        indicators = self.calculate_technical_indicators(market_data.get('candles', []))
        if not indicators:
            return {'action': 'hold', 'reason': 'Insufficient data for analysis', 'confidence': 0.0}
        
        signals = []
        confidence = 0.0
        
        # Technical Analysis Signals
        current_price = indicators['current_price']
        rsi = indicators['rsi']
        
        # RSI signals
        if rsi < 30:
            signals.append("RSI oversold - strong buy signal")
            confidence += 0.35
        elif rsi < 40:
            signals.append("RSI approaching oversold")
            confidence += 0.15
        elif rsi > 70:
            signals.append("RSI overbought - avoid buying")
            confidence -= 0.2
        
        # Moving average signals
        if current_price > indicators['sma_5'] > indicators['sma_10']:
            signals.append("Bullish MA alignment")
            confidence += 0.25
        elif current_price < indicators['sma_5'] < indicators['sma_10']:
            signals.append("Bearish MA alignment")
            confidence -= 0.15
        
        # Volume confirmation
        if indicators['volume_trend'] > 1.2:
            signals.append("Strong volume confirmation")
            confidence += 0.2
        elif indicators['volume_trend'] > 1.0:
            signals.append("Moderate volume support")
            confidence += 0.1
        
        # Momentum signals
        if indicators['momentum'] > 2.0:
            signals.append("Strong upward momentum")
            confidence += 0.2
        elif indicators['momentum'] > 0.5:
            signals.append("Positive momentum")
            confidence += 0.1
        
        # Price position analysis
        price_position = (current_price - market_data['low_24h']) / (market_data['high_24h'] - market_data['low_24h'])
        if price_position < 0.3:
            signals.append("Near 24h low - potential bounce")
            confidence += 0.2
        elif price_position > 0.8:
            signals.append("Near 24h high - potential resistance")
            confidence -= 0.1
        
        # 24h change consideration
        if market_data['change_24h'] < -3.0:
            signals.append("Oversold on 24h chart")
            confidence += 0.15
        
        # Volume analysis
        if market_data['volume_24h'] > 5000000:  # High volume threshold
            signals.append("High trading volume")
            confidence += 0.1
        
        # Final decision
        if confidence >= self.confidence_threshold and len(signals) >= 3:
            return {
                'action': 'buy',
                'confidence': min(confidence, 1.0),
                'signals': signals,
                'price': current_price,
                'symbol': symbol,
                'technical_data': indicators
            }
        
        return {
            'action': 'hold',
            'confidence': confidence,
            'signals': signals,
            'reason': f"Confidence {confidence:.2f} below threshold {self.confidence_threshold}"
        }

    def execute_buy_order(self, symbol: str, usdt_amount: float) -> Dict[str, Any]:
        """Execute a buy order with proper validation"""
        try:
            market_data = self.get_market_data(symbol)
            if not market_data:
                return {'success': False, 'error': 'No market data available'}
            
            current_price = market_data['price']
            quantity = usdt_amount / current_price
            
            # Get instrument specifications
            instrument_response = requests.get(f'{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}')
            if instrument_response.status_code == 200:
                instrument_data = instrument_response.json()
                if instrument_data.get('data'):
                    instrument = instrument_data['data'][0]
                    min_size = float(instrument.get('minSz', '0'))
                    lot_size = float(instrument.get('lotSz', '0'))
                    
                    # Adjust quantity to lot size
                    if lot_size > 0:
                        quantity = round(quantity / lot_size) * lot_size
                    
                    # Validate minimum size
                    if quantity < min_size:
                        return {'success': False, 'error': f'Quantity {quantity:.8f} below minimum {min_size}'}
            
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
                self.last_trade_time = datetime.now()
                
                print(f"TRADE EXECUTED: {symbol}")
                print(f"Order ID: {order_id}")
                print(f"Quantity: {quantity:.6f}")
                print(f"Price: ${current_price:.6f}")
                print(f"Value: ${quantity * current_price:.2f}")
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': current_price,
                    'value': quantity * current_price
                }
            else:
                error_msg = result.get('msg', 'Unknown error')
                if 'data' in result and result['data']:
                    error_detail = result['data'][0].get('sMsg', '')
                    error_msg = f"{error_msg}: {error_detail}"
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def run_trading_cycle(self) -> Dict[str, Any]:
        """Execute one complete autonomous trading cycle"""
        cycle_start = datetime.now()
        print(f"\n=== Trading Cycle {cycle_start.strftime('%H:%M:%S')} ===")
        
        # Get account balance
        balances = self.get_account_balance()
        usdt_balance = balances.get('USDT', 0)
        total_equity = balances.get('TOTAL_EQUITY', 0)
        
        print(f"Portfolio: ${total_equity:.2f} | Available USDT: ${usdt_balance:.2f}")
        
        if usdt_balance < 1.0:
            print("Insufficient USDT for trading")
            return {'trades': 0, 'message': 'Insufficient balance'}
        
        # Calculate position size
        max_trade_amount = min(usdt_balance * self.max_position_size, usdt_balance - 0.5)
        
        # Analyze all trading pairs
        best_opportunity = None
        best_confidence = 0
        
        print("Analyzing markets...")
        for symbol in self.trading_pairs:
            try:
                analysis = self.analyze_trading_opportunity(symbol)
                print(f"{symbol}: {analysis['action']} (confidence: {analysis.get('confidence', 0):.2f})")
                
                if analysis['action'] == 'buy' and analysis['confidence'] > best_confidence:
                    best_opportunity = analysis
                    best_confidence = analysis['confidence']
                    
            except Exception as e:
                print(f"{symbol}: Analysis error - {e}")
        
        # Execute best opportunity
        if best_opportunity and best_confidence >= self.confidence_threshold:
            symbol = best_opportunity['symbol']
            trade_amount = min(max_trade_amount, 3.0)  # Max $3 per trade
            
            print(f"\nExecuting trade: {symbol}")
            print(f"Confidence: {best_confidence:.2f}")
            print(f"Signals: {', '.join(best_opportunity['signals'][:3])}")
            
            trade_result = self.execute_buy_order(symbol, trade_amount)
            
            if trade_result['success']:
                self.successful_trades += 1
                return {
                    'trades': 1,
                    'symbol': symbol,
                    'confidence': best_confidence,
                    'order_id': trade_result['order_id'],
                    'message': 'Trade executed successfully'
                }
            else:
                print(f"Trade failed: {trade_result['error']}")
                return {'trades': 0, 'message': f"Trade failed: {trade_result['error']}"}
        else:
            print("No high-confidence opportunities found")
            return {'trades': 0, 'message': 'Waiting for better opportunities'}

    def start_autonomous_trading(self):
        """Start continuous autonomous trading"""
        print("\n" + "="*60)
        print("AUTONOMOUS LIVE TRADING ACTIVATED")
        print("="*60)
        print("Real money execution enabled")
        print("Monitoring markets for profitable opportunities")
        print("Press Ctrl+C to stop")
        print("="*60)
        
        self.is_running = True
        cycle_count = 0
        
        try:
            while self.is_running:
                cycle_count += 1
                print(f"\n[Cycle {cycle_count}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Execute trading cycle
                results = self.run_trading_cycle()
                
                # Print summary
                print(f"Result: {results['message']}")
                if self.total_trades > 0:
                    success_rate = (self.successful_trades / self.total_trades) * 100
                    print(f"Stats: {self.total_trades} trades, {success_rate:.1f}% success rate")
                
                # Wait before next cycle
                print("Next cycle in 90 seconds...")
                time.sleep(90)
                
        except KeyboardInterrupt:
            print(f"\n\nTrading stopped by user")
            print(f"Executed {cycle_count} cycles")
            print(f"Total trades: {self.total_trades}")
            if self.total_trades > 0:
                success_rate = (self.successful_trades / self.total_trades) * 100
                print(f"Success rate: {success_rate:.1f}%")
        finally:
            self.is_running = False

def main():
    """Start the autonomous trading engine"""
    trader = AutonomousLiveTrader()
    trader.start_autonomous_trading()

if __name__ == "__main__":
    main()