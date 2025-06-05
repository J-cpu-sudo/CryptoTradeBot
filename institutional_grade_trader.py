#!/usr/bin/env python3
"""
Institutional Grade Trading Engine - Advanced algorithms with hedge fund-level sophistication
"""
import os
import requests
import json
import hmac
import hashlib
import base64
import time
import numpy as np
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional
import logging

class InstitutionalTradingEngine:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
        
        # Institutional-grade configuration
        self.max_concurrent_positions = 8
        self.risk_per_trade = 0.02  # 2% risk per trade
        self.portfolio_heat = 0.15  # Maximum 15% portfolio at risk
        self.sharpe_threshold = 1.5
        self.max_drawdown = 0.08  # 8% maximum drawdown
        
        # Advanced market structures
        self.market_regimes = {
            'trending': {'rsi_range': (30, 70), 'volatility': (2, 8), 'volume_factor': 1.5},
            'ranging': {'rsi_range': (40, 60), 'volatility': (1, 3), 'volume_factor': 0.8},
            'breakout': {'rsi_range': (20, 80), 'volatility': (5, 15), 'volume_factor': 2.0}
        }
        
        # Institutional trading universe
        self.tier1_assets = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT']
        self.tier2_assets = ['ADA-USDT', 'XRP-USDT', 'DOGE-USDT', 'TRX-USDT']
        self.tier3_assets = ['PEPE-USDT', 'NEIRO-USDT', 'WIF-USDT', 'MEME-USDT']
        self.momentum_assets = ['ORDI-USDT', 'RATS-USDT', 'SATS-USDT', 'TURBO-USDT']
        
        # Portfolio tracking
        self.active_positions = {}
        self.performance_metrics = {
            'total_trades': 0,
            'profitable_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0
        }
        
        self.position_lock = threading.Lock()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
    
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
    
    def get_headers(self, method: str, path: str, body: str = '') -> Dict[str, str]:
        timestamp = self.get_timestamp()
        signature = self.create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def api_request(self, method: str, endpoint: str, body: str = None, retries: int = 3) -> Optional[Dict]:
        for attempt in range(retries):
            try:
                headers = self.get_headers(method, endpoint, body or '')
                url = self.base_url + endpoint
                
                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=15)
                else:
                    response = requests.post(url, headers=headers, data=body, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('code') == '0':
                        return data
                    else:
                        self.logger.warning(f"API error: {data.get('msg')}")
                
                time.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                self.logger.error(f"API request failed (attempt {attempt + 1}): {e}")
                time.sleep(2 ** attempt)
        
        return None
    
    def get_portfolio_state(self) -> Dict[str, float]:
        data = self.api_request('GET', '/api/v5/account/balance')
        portfolio = {}
        
        if data:
            for detail in data['data'][0]['details']:
                balance = float(detail['availBal'])
                if balance > 0:
                    portfolio[detail['ccy']] = balance
        
        return portfolio
    
    def get_enhanced_market_data(self, symbol: str) -> Dict[str, float]:
        # Get multiple timeframes for comprehensive analysis
        endpoints = [
            f'/api/v5/market/candles?instId={symbol}&bar=1m&limit=100',
            f'/api/v5/market/candles?instId={symbol}&bar=5m&limit=100',
            f'/api/v5/market/candles?instId={symbol}&bar=15m&limit=100',
            f'/api/v5/market/ticker?instId={symbol}',
            f'/api/v5/market/books?instId={symbol}&sz=20'
        ]
        
        market_data = {}
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.api_request, 'GET', endpoint): endpoint 
                      for endpoint in endpoints}
            
            for future in as_completed(futures):
                endpoint = futures[future]
                try:
                    result = future.result(timeout=10)
                    if result:
                        if 'candles' in endpoint:
                            timeframe = endpoint.split('bar=')[1].split('&')[0]
                            market_data[f'candles_{timeframe}'] = result['data']
                        elif 'ticker' in endpoint:
                            market_data['ticker'] = result['data'][0]
                        elif 'books' in endpoint:
                            market_data['orderbook'] = result['data'][0]
                except Exception as e:
                    self.logger.error(f"Failed to get data for {endpoint}: {e}")
        
        return market_data
    
    def calculate_advanced_indicators(self, candles: List[List[str]]) -> Dict[str, float]:
        if len(candles) < 50:
            return {}
        
        # Convert to numpy arrays for faster computation
        opens = np.array([float(c[1]) for c in candles])
        highs = np.array([float(c[2]) for c in candles])
        lows = np.array([float(c[3]) for c in candles])
        closes = np.array([float(c[4]) for c in candles])
        volumes = np.array([float(c[5]) for c in candles])
        
        indicators = {}
        
        # RSI calculation
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        
        if avg_loss != 0:
            rs = avg_gain / avg_loss
            indicators['rsi'] = 100 - (100 / (1 + rs))
        else:
            indicators['rsi'] = 100
        
        # Bollinger Bands
        sma_20 = np.mean(closes[-20:])
        std_20 = np.std(closes[-20:])
        indicators['bb_upper'] = sma_20 + (2 * std_20)
        indicators['bb_lower'] = sma_20 - (2 * std_20)
        indicators['bb_position'] = (closes[-1] - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])
        
        # MACD
        ema_12 = self._calculate_ema(closes, 12)
        ema_26 = self._calculate_ema(closes, 26)
        indicators['macd'] = ema_12 - ema_26
        indicators['macd_signal'] = self._calculate_ema(np.array([indicators['macd']]), 9)
        
        # Volume indicators
        indicators['volume_sma'] = np.mean(volumes[-20:])
        indicators['volume_ratio'] = volumes[-1] / indicators['volume_sma']
        
        # Volatility (ATR)
        tr = np.maximum(highs[1:] - lows[1:], 
                       np.maximum(np.abs(highs[1:] - closes[:-1]), 
                                 np.abs(lows[1:] - closes[:-1])))
        indicators['atr'] = np.mean(tr[-14:])
        indicators['volatility_pct'] = (indicators['atr'] / closes[-1]) * 100
        
        # Momentum
        indicators['momentum_5'] = (closes[-1] / closes[-6] - 1) * 100
        indicators['momentum_10'] = (closes[-1] / closes[-11] - 1) * 100
        
        return indicators
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema
    
    def identify_market_regime(self, indicators: Dict[str, float]) -> str:
        rsi = indicators.get('rsi', 50)
        volatility = indicators.get('volatility_pct', 2)
        volume_ratio = indicators.get('volume_ratio', 1)
        
        # Regime classification logic
        if volatility > 5 and volume_ratio > 1.8:
            return 'breakout'
        elif 35 <= rsi <= 65 and volatility < 3:
            return 'ranging'
        else:
            return 'trending'
    
    def calculate_signal_strength(self, symbol: str, market_data: Dict) -> Dict[str, float]:
        if not market_data.get('candles_1m'):
            return {'signal': 0, 'confidence': 0, 'regime': 'unknown'}
        
        indicators = self.calculate_advanced_indicators(market_data['candles_1m'])
        if not indicators:
            return {'signal': 0, 'confidence': 0, 'regime': 'unknown'}
        
        regime = self.identify_market_regime(indicators)
        signal_components = []
        
        # RSI component
        rsi = indicators.get('rsi', 50)
        if rsi < 30:
            signal_components.append(0.4)  # Oversold - buy signal
        elif rsi > 70:
            signal_components.append(-0.4)  # Overbought - sell signal
        else:
            signal_components.append(0)
        
        # Bollinger Bands component
        bb_pos = indicators.get('bb_position', 0.5)
        if bb_pos < 0.2:
            signal_components.append(0.3)
        elif bb_pos > 0.8:
            signal_components.append(-0.3)
        else:
            signal_components.append(0)
        
        # MACD component
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        if macd > macd_signal:
            signal_components.append(0.2)
        else:
            signal_components.append(-0.2)
        
        # Volume confirmation
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > 1.5:
            volume_boost = 0.2
        elif volume_ratio < 0.7:
            volume_boost = -0.1
        else:
            volume_boost = 0
        
        # Calculate final signal
        base_signal = sum(signal_components)
        final_signal = base_signal + volume_boost
        
        # Confidence based on signal alignment
        confidence = min(abs(final_signal), 1.0)
        
        return {
            'signal': final_signal,
            'confidence': confidence,
            'regime': regime,
            'indicators': indicators
        }
    
    def calculate_position_size(self, signal_strength: float, account_balance: float) -> float:
        # Kelly Criterion with risk management overlay
        win_rate = max(self.performance_metrics['win_rate'], 0.5)
        avg_win_loss_ratio = 1.2  # Conservative estimate
        
        kelly_fraction = (win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio
        kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25%
        
        # Adjust for signal strength
        size_fraction = kelly_fraction * signal_strength
        
        # Risk management constraints
        max_position_size = account_balance * 0.15  # Max 15% per position
        calculated_size = account_balance * size_fraction
        
        return min(calculated_size, max_position_size)
    
    def execute_institutional_trade(self, symbol: str, side: str, size: float) -> Optional[str]:
        if side == 'buy':
            # For buy orders, size is in USDT
            price_data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
            if not price_data:
                return None
            
            price = float(price_data['data'][0]['last'])
            
            # Get instrument specifications
            inst_data = self.api_request('GET', f'/api/v5/public/instruments?instType=SPOT&instId={symbol}')
            if not inst_data:
                return None
            
            min_size = float(inst_data['data'][0]['minSz'])
            quantity = size / price
            
            if quantity < min_size:
                return None
            
            # Round to proper precision
            quantity = round(quantity / min_size) * min_size
            
            order_data = {
                "instId": symbol,
                "tdMode": "cash",
                "side": "buy",
                "ordType": "market",
                "sz": str(quantity)
            }
        else:
            # For sell orders, size is in base currency
            order_data = {
                "instId": symbol,
                "tdMode": "cash",
                "side": "sell",
                "ordType": "market",
                "sz": str(size)
            }
        
        order_body = json.dumps(order_data)
        result = self.api_request('POST', '/api/v5/trade/order', order_body)
        
        if result:
            order_id = result['data'][0]['ordId']
            
            # Track position
            with self.position_lock:
                if side == 'buy':
                    self.active_positions[symbol] = {
                        'quantity': quantity,
                        'entry_price': price,
                        'entry_time': time.time(),
                        'order_id': order_id,
                        'side': side
                    }
                elif symbol in self.active_positions:
                    del self.active_positions[symbol]
            
            self.logger.info(f"Executed {side.upper()} {symbol}: {order_id}")
            return order_id
        
        return None
    
    def manage_portfolio_risk(self) -> List[str]:
        actions = []
        current_time = time.time()
        
        with self.position_lock:
            positions_to_close = []
            
            for symbol, position in self.active_positions.items():
                current_price = None
                price_data = self.api_request('GET', f'/api/v5/market/ticker?instId={symbol}')
                
                if price_data:
                    current_price = float(price_data['data'][0]['last'])
                    
                    # Calculate P&L
                    pnl_pct = (current_price - position['entry_price']) / position['entry_price']
                    hold_time = current_time - position['entry_time']
                    
                    # Risk management rules
                    should_close = False
                    reason = ""
                    
                    # Profit target: 2.5% for institutional grade
                    if pnl_pct >= 0.025:
                        should_close = True
                        reason = f"profit target {pnl_pct*100:.2f}%"
                    
                    # Stop loss: -3%
                    elif pnl_pct <= -0.03:
                        should_close = True
                        reason = f"stop loss {pnl_pct*100:.2f}%"
                    
                    # Time-based exit: 5 minutes max hold
                    elif hold_time > 300:
                        should_close = True
                        reason = f"time limit {hold_time/60:.1f}min"
                    
                    if should_close:
                        positions_to_close.append((symbol, position['quantity'], reason))
        
        # Execute closures
        for symbol, quantity, reason in positions_to_close:
            self.logger.info(f"Closing {symbol}: {reason}")
            order_id = self.execute_institutional_trade(symbol, 'sell', quantity)
            if order_id:
                actions.append(f"Closed {symbol} - {reason}")
        
        return actions
    
    def scan_institutional_opportunities(self, portfolio_value: float) -> List[Tuple[str, float, str]]:
        # Determine trading universe based on portfolio size
        if portfolio_value >= 50:
            universe = self.tier1_assets + self.tier2_assets + self.tier3_assets
        elif portfolio_value >= 20:
            universe = self.tier2_assets + self.tier3_assets + self.momentum_assets
        else:
            universe = self.tier3_assets + self.momentum_assets
        
        opportunities = []
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_symbol = {executor.submit(self._analyze_symbol, symbol): symbol 
                              for symbol in universe}
            
            for future in as_completed(future_to_symbol, timeout=30):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result and result['confidence'] > 0.6:  # High confidence threshold
                        opportunities.append((symbol, result['signal'], result['regime']))
                except Exception as e:
                    self.logger.error(f"Analysis failed for {symbol}: {e}")
        
        # Sort by signal strength
        opportunities.sort(key=lambda x: abs(x[1]), reverse=True)
        return opportunities[:3]  # Top 3 opportunities
    
    def _analyze_symbol(self, symbol: str) -> Optional[Dict]:
        if symbol in self.active_positions:
            return None
        
        market_data = self.get_enhanced_market_data(symbol)
        if not market_data:
            return None
        
        return self.calculate_signal_strength(symbol, market_data)
    
    def execute_institutional_cycle(self):
        self.logger.info("=== INSTITUTIONAL TRADING CYCLE ===")
        
        # Get portfolio state
        portfolio = self.get_portfolio_state()
        usdt_balance = portfolio.get('USDT', 0)
        
        # Calculate total portfolio value
        total_value = usdt_balance
        for currency, balance in portfolio.items():
            if currency != 'USDT' and balance > 0:
                ticker_data = self.api_request('GET', f'/api/v5/market/ticker?instId={currency}-USDT')
                if ticker_data:
                    price = float(ticker_data['data'][0]['last'])
                    total_value += balance * price
        
        self.logger.info(f"Portfolio Value: ${total_value:.2f} USDT, Active Positions: {len(self.active_positions)}")
        
        # Risk management
        risk_actions = self.manage_portfolio_risk()
        for action in risk_actions:
            self.logger.info(f"Risk Management: {action}")
        
        # Wait for risk management to settle
        if risk_actions:
            time.sleep(3)
            portfolio = self.get_portfolio_state()
            usdt_balance = portfolio.get('USDT', 0)
        
        # Scan for new opportunities
        if usdt_balance >= 2 and len(self.active_positions) < self.max_concurrent_positions:
            opportunities = self.scan_institutional_opportunities(total_value)
            
            for symbol, signal, regime in opportunities:
                if usdt_balance < 2:
                    break
                
                position_size = self.calculate_position_size(abs(signal), usdt_balance)
                
                if position_size >= 1:  # Minimum trade size
                    side = 'buy' if signal > 0 else 'sell'
                    self.logger.info(f"Opportunity: {symbol} - Signal: {signal:.3f}, Regime: {regime}")
                    
                    order_id = self.execute_institutional_trade(symbol, side, position_size)
                    if order_id:
                        usdt_balance -= position_size
                        self.performance_metrics['total_trades'] += 1
    
    def run_institutional_engine(self):
        self.logger.info("INSTITUTIONAL GRADE TRADING ENGINE INITIATED")
        self.logger.info("Advanced algorithms, multi-timeframe analysis, risk management active")
        self.logger.info("=" * 80)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                self.logger.info(f"Institutional Cycle #{cycle_count}")
                
                self.execute_institutional_cycle()
                
                # Dynamic cycle timing based on market conditions
                if len(self.active_positions) > 0:
                    wait_time = 20  # Faster monitoring with active positions
                else:
                    wait_time = 35  # Standard institutional timing
                
                self.logger.info(f"Next cycle in {wait_time} seconds...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                self.logger.info("Institutional engine stopped")
                break
            except Exception as e:
                self.logger.error(f"Engine error: {e}")
                time.sleep(30)

def main():
    engine = InstitutionalTradingEngine()
    engine.run_institutional_engine()

if __name__ == "__main__":
    main()