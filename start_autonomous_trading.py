#!/usr/bin/env python3
"""
Start Autonomous Trading - Continuous Live Trading Engine
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
from typing import Dict, List, Any
import numpy as np

class LiveTradingBot:
    """Simplified autonomous trading bot with proven execution capability"""
    
    def __init__(self):
        self.api_key = os.getenv('OKX_API_KEY')
        self.secret_key = os.getenv('OKX_SECRET_KEY')
        self.passphrase = os.getenv('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
        # Trading configuration
        self.active_pairs = ['TRX-USDT', 'DOGE-USDT', 'ADA-USDT', 'BNB-USDT', 'SOL-USDT']
        self.max_trade_amount = 3.0  # Maximum $3 per trade
        self.min_confidence = 0.70   # 70% confidence threshold
        
        # Performance tracking
        self.trades_executed = 0
        self.last_trade_time = None
        self.running = False
        
        print("Live Trading Bot Initialized")
        print(f"Max trade: ${self.max_trade_amount}")
        print(f"Confidence threshold: {self.min_confidence*100}%")

    def generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """Generate OKX API signature"""
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.secret_key or '', encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()

    def get_headers(self, method: str, request_path: str, body: str = '') -> Dict[str, str]:
        """Get authenticated headers"""
        timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
        signature = self.generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key or '',
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase or '',
            'Content-Type': 'application/json'
        }

    def get_account_balance(self) -> float:
        """Get available USDT balance"""
        try:
            path = '/api/v5/account/balance'
            headers = self.get_headers('GET', path)
            
            response = requests.get(self.base_url + path, headers=headers)
            data = response.json()
            
            if data.get('code') == '0':
                for detail in data['data'][0]['details']:
                    if detail['ccy'] == 'USDT':
                        return float(detail['availBal'])
            return 0.0
        except Exception as e:
            print(f"Balance error: {e}")
            return 0.0

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for symbol"""
        try:
            # Get ticker
            ticker_response = requests.get(f'{self.base_url}/api/v5/market/ticker?instId={symbol}')
            ticker_data = ticker_response.json()
            
            if not ticker_data.get('data'):
                return {}
                
            ticker = ticker_data['data'][0]
            
            # Get candles for analysis
            candle_response = requests.get(f'{self.base_url}/api/v5/market/candles?instId={symbol}&bar=1H&limit=20')
            candle_data = candle_response.json()
            
            candles = candle_data.get('data', [])
            
            return {
                'symbol': symbol,
                'price': float(ticker['last']),
                'volume_24h': float(ticker['vol24h']),
                'change_24h': float(ticker.get('chg24h', '0')),
                'high_24h': float(ticker['high24h']),
                'low_24h': float(ticker['low24h']),
                'candles': candles
            }
        except Exception as e:
            print(f"Market data error for {symbol}: {e}")
            return {}

    def analyze_opportunity(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trading opportunity with simplified but effective signals"""
        if not market_data or not market_data.get('candles'):
            return {'action': 'hold', 'confidence': 0.0, 'reason': 'No data'}
        
        symbol = market_data['symbol']
        current_price = market_data['price']
        change_24h = market_data['change_24h']
        volume_24h = market_data['volume_24h']
        
        # Extract closing prices from candles
        closes = [float(candle[4]) for candle in market_data['candles']]
        if len(closes) < 10:
            return {'action': 'hold', 'confidence': 0.0, 'reason': 'Insufficient candle data'}
        
        # Calculate simple moving averages
        sma_5 = sum(closes[-5:]) / 5
        sma_10 = sum(closes[-10:]) / 10
        
        # Calculate RSI
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
        
        avg_gain = sum(gains[-14:]) / 14 if len(gains) >= 14 else sum(gains) / len(gains)
        avg_loss = sum(losses[-14:]) / 14 if len(losses) >= 14 else sum(losses) / len(losses)
        
        rsi = 100 - (100 / (1 + (avg_gain / max(avg_loss, 0.001))))
        
        # Scoring system
        signals = []
        confidence = 0.0
        
        # RSI oversold signal (strong)
        if rsi < 30:
            signals.append("RSI oversold")
            confidence += 0.4
        elif rsi < 40:
            signals.append("RSI approaching oversold")
            confidence += 0.2
        
        # Moving average bullish alignment
        if current_price > sma_5 > sma_10:
            signals.append("Bullish MA trend")
            confidence += 0.3
        
        # 24h decline (potential bounce)
        if change_24h < -3.0:
            signals.append("24h decline recovery")
            confidence += 0.2
        elif change_24h < -1.0:
            signals.append("Minor decline")
            confidence += 0.1
        
        # Volume confirmation
        if volume_24h > 1000000:  # Minimum volume threshold
            signals.append("Good volume")
            confidence += 0.1
        
        # Price position in 24h range
        price_position = (current_price - market_data['low_24h']) / (market_data['high_24h'] - market_data['low_24h'])
        if price_position < 0.3:
            signals.append("Near 24h low")
            confidence += 0.2
        
        # Final decision
        if confidence >= self.min_confidence and len(signals) >= 2:
            return {
                'action': 'buy',
                'confidence': min(confidence, 1.0),
                'signals': signals,
                'symbol': symbol,
                'price': current_price,
                'rsi': rsi
            }
        
        return {
            'action': 'hold',
            'confidence': confidence,
            'signals': signals,
            'reason': f"Confidence {confidence:.2f} below {self.min_confidence}"
        }

    def execute_trade(self, symbol: str, amount: float) -> bool:
        """Execute a buy trade"""
        try:
            # Get current price for quantity calculation
            market_data = self.get_market_data(symbol)
            if not market_data:
                return False
            
            current_price = market_data['price']
            quantity = amount / current_price
            
            # Get instrument info for lot size
            instrument_response = requests.get(f'{self.base_url}/api/v5/public/instruments?instType=SPOT&instId={symbol}')
            if instrument_response.status_code == 200:
                instrument_data = instrument_response.json()
                if instrument_data.get('data'):
                    instrument = instrument_data['data'][0]
                    min_size = float(instrument.get('minSz', '0'))
                    lot_size = float(instrument.get('lotSz', '0'))
                    
                    # Adjust quantity
                    if lot_size > 0:
                        quantity = round(quantity / lot_size) * lot_size
                    
                    if quantity < min_size:
                        print(f"Quantity {quantity:.8f} below minimum {min_size}")
                        return False
            
            # Place order
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
                self.trades_executed += 1
                self.last_trade_time = datetime.now()
                
                print(f"\n🎯 TRADE EXECUTED: {symbol}")
                print(f"Order ID: {order_id}")
                print(f"Quantity: {quantity:.6f}")
                print(f"Price: ${current_price:.6f}")
                print(f"Value: ${amount:.2f}")
                print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
                
                return True
            else:
                error_msg = result.get('msg', 'Unknown error')
                print(f"Trade failed: {error_msg}")
                return False
                
        except Exception as e:
            print(f"Trade execution error: {e}")
            return False

    def run_trading_cycle(self):
        """Execute one trading cycle"""
        try:
            print(f"\n--- Trading Cycle {datetime.now().strftime('%H:%M:%S')} ---")
            
            # Check balance
            balance = self.get_account_balance()
            print(f"Available USDT: ${balance:.2f}")
            
            if balance < 0.5:
                print("Insufficient balance for trading")
                return
            
            # Calculate trade amount
            trade_amount = min(balance * 0.3, self.max_trade_amount, balance - 0.2)
            
            # Analyze all pairs
            best_opportunity = None
            best_confidence = 0
            
            for symbol in self.active_pairs:
                try:
                    market_data = self.get_market_data(symbol)
                    if market_data:
                        analysis = self.analyze_opportunity(market_data)
                        
                        print(f"{symbol}: {analysis['action']} (conf: {analysis.get('confidence', 0):.2f})")
                        
                        if analysis['action'] == 'buy' and analysis['confidence'] > best_confidence:
                            best_opportunity = analysis
                            best_confidence = analysis['confidence']
                            
                except Exception as e:
                    print(f"{symbol}: Error - {e}")
            
            # Execute best opportunity
            if best_opportunity and best_confidence >= self.min_confidence:
                symbol = best_opportunity['symbol']
                print(f"\nBest opportunity: {symbol}")
                print(f"Confidence: {best_confidence:.2f}")
                print(f"Signals: {', '.join(best_opportunity['signals'][:3])}")
                
                if self.execute_trade(symbol, trade_amount):
                    print(f"Total trades executed: {self.trades_executed}")
                else:
                    print("Trade execution failed")
            else:
                print("No high-confidence opportunities found")
                
        except Exception as e:
            print(f"Cycle error: {e}")

    def start_continuous_trading(self):
        """Start continuous autonomous trading"""
        print("\n" + "="*50)
        print("AUTONOMOUS LIVE TRADING STARTED")
        print("="*50)
        print("Real money execution enabled")
        print("Press Ctrl+C to stop")
        print("="*50)
        
        self.running = True
        cycle_count = 0
        
        try:
            while self.running:
                cycle_count += 1
                print(f"\n[Cycle {cycle_count}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                self.run_trading_cycle()
                
                # Wait before next cycle
                print("Next cycle in 60 seconds...")
                time.sleep(60)
                
        except KeyboardInterrupt:
            print(f"\n\nTrading stopped")
            print(f"Cycles completed: {cycle_count}")
            print(f"Trades executed: {self.trades_executed}")
        finally:
            self.running = False

def main():
    """Start the trading bot"""
    bot = LiveTradingBot()
    bot.start_continuous_trading()

if __name__ == "__main__":
    main()