import requests
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import random

class MarketAnalyzer:
    def __init__(self):
        self.base_url = "https://www.okx.com"
        
    def analyze_market(self, symbol: str = "BTC-USDT") -> Optional[Dict[str, Any]]:
        """
        Perform comprehensive market analysis
        
        Returns:
            Dictionary containing market analysis data
        """
        try:
            # Get current price data
            ticker = self._get_ticker(symbol)
            if not ticker:
                return None
            
            # Get historical data for technical analysis
            candles = self._get_candles(symbol)
            if not candles:
                logging.warning("Using simulated data for market analysis")
                return self._get_simulated_analysis(symbol, ticker)
            
            # Calculate technical indicators
            indicators = self._calculate_indicators(candles)
            
            # Analyze market conditions
            market_conditions = self._analyze_market_conditions(candles, ticker)
            
            return {
                'symbol': symbol,
                'timestamp': datetime.utcnow().isoformat(),
                'current_price': float(ticker.get('last', 0)),
                'indicators': indicators,
                'market_conditions': market_conditions,
                'analysis_quality': 'real_data'
            }
            
        except Exception as e:
            logging.error(f"Error in market analysis: {e}")
            return None
    
    def _get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current ticker data"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v5/market/ticker?instId={symbol}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0' and data.get('data'):
                    return data['data'][0]
            
            return None
            
        except Exception as e:
            logging.error(f"Error getting ticker: {e}")
            return None
    
    def _get_candles(self, symbol: str, limit: int = 100) -> Optional[List[List[str]]]:
        """Get historical candlestick data"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v5/market/candles",
                params={
                    'instId': symbol,
                    'bar': '1H',  # 1-hour candles
                    'limit': limit
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0' and data.get('data'):
                    return data['data']
            
            return None
            
        except Exception as e:
            logging.error(f"Error getting candles: {e}")
            return None
    
    def _calculate_indicators(self, candles: List[List[str]]) -> Dict[str, Any]:
        """Calculate technical indicators from candlestick data"""
        try:
            # Extract price data
            closes = [float(candle[4]) for candle in candles]  # Close prices
            highs = [float(candle[2]) for candle in candles]   # High prices
            lows = [float(candle[3]) for candle in candles]    # Low prices
            volumes = [float(candle[5]) for candle in candles] # Volumes
            
            if len(closes) < 26:
                logging.warning("Insufficient data for indicator calculation")
                return {}
            
            # Calculate EMAs
            ema_12 = self._calculate_ema(closes, 12)
            ema_26 = self._calculate_ema(closes, 26)
            
            # Calculate RSI
            rsi = self._calculate_rsi(closes, 14)
            
            # Calculate MACD
            macd = ema_12 - ema_26 if ema_12 and ema_26 else 0
            
            # Calculate ATR (Average True Range)
            atr = self._calculate_atr(highs, lows, closes, 14)
            
            return {
                'ema_12': round(ema_12, 2) if ema_12 else None,
                'ema_26': round(ema_26, 2) if ema_26 else None,
                'rsi': round(rsi, 2) if rsi else None,
                'macd': round(macd, 4) if macd else None,
                'atr': round(atr, 2) if atr else None,
                'current_price': closes[-1],
                'price_change_24h': ((closes[-1] - closes[-24]) / closes[-24] * 100) if len(closes) >= 24 else 0
            }
            
        except Exception as e:
            logging.error(f"Error calculating indicators: {e}")
            return {}
    
    def _analyze_market_conditions(self, candles: List[List[str]], ticker: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current market conditions"""
        try:
            volumes = [float(candle[5]) for candle in candles]
            closes = [float(candle[4]) for candle in candles]
            
            # Volume analysis
            current_volume = float(ticker.get('vol24h', 0))
            avg_volume = statistics.mean(volumes) if volumes else 0
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Volatility analysis (using price changes)
            price_changes = []
            for i in range(1, len(closes)):
                change = abs(closes[i] - closes[i-1]) / closes[i-1] * 100
                price_changes.append(change)
            
            current_volatility = statistics.mean(price_changes[-10:]) if len(price_changes) >= 10 else 0
            avg_volatility = statistics.mean(price_changes) if price_changes else 0
            
            # Calculate volatility percentile
            volatility_percentile = 50  # Default
            if price_changes:
                sorted_changes = sorted(price_changes)
                current_rank = len([x for x in sorted_changes if x <= current_volatility])
                volatility_percentile = (current_rank / len(sorted_changes)) * 100
            
            # Market trend analysis
            short_term_trend = self._calculate_trend(closes[-10:]) if len(closes) >= 10 else 0
            long_term_trend = self._calculate_trend(closes[-30:]) if len(closes) >= 30 else 0
            
            return {
                'volume_ratio': round(volume_ratio, 2),
                'current_volatility': round(current_volatility, 2),
                'avg_volatility': round(avg_volatility, 2),
                'volatility_percentile': round(volatility_percentile, 1),
                'short_term_trend': round(short_term_trend, 4),
                'long_term_trend': round(long_term_trend, 4),
                'atr': self._calculate_atr(
                    [float(c[2]) for c in candles],
                    [float(c[3]) for c in candles],
                    [float(c[4]) for c in candles],
                    14
                )
            }
            
        except Exception as e:
            logging.error(f"Error analyzing market conditions: {e}")
            return {}
    
    def _calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = prices[0]  # Start with first price
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [delta if delta > 0 else 0 for delta in deltas]
        losses = [-delta if delta < 0 else 0 for delta in deltas]
        
        avg_gain = statistics.mean(gains[-period:])
        avg_loss = statistics.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        if len(highs) < period + 1:
            return None
        
        true_ranges = []
        for i in range(1, len(highs)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            true_ranges.append(max(tr1, tr2, tr3))
        
        return statistics.mean(true_ranges[-period:])
    
    def _calculate_trend(self, prices: List[float]) -> float:
        """Calculate trend slope using linear regression"""
        if len(prices) < 2:
            return 0
        
        n = len(prices)
        x_values = list(range(n))
        
        # Calculate slope using least squares method
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(prices)
        
        numerator = sum((x_values[i] - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0
        
        slope = numerator / denominator
        return slope / y_mean  # Normalize by price level
    
    def _get_simulated_analysis(self, symbol: str, ticker: Dict[str, Any]) -> Dict[str, Any]:
        """Generate simulated market analysis for testing"""
        current_price = float(ticker.get('last', 45000))
        
        # Generate realistic-looking indicators
        ema_12 = current_price * random.uniform(0.998, 1.002)
        ema_26 = current_price * random.uniform(0.995, 1.005)
        rsi = random.uniform(30, 70)
        atr = current_price * random.uniform(0.01, 0.03)
        
        return {
            'symbol': symbol,
            'timestamp': datetime.utcnow().isoformat(),
            'current_price': current_price,
            'indicators': {
                'ema_12': round(ema_12, 2),
                'ema_26': round(ema_26, 2),
                'rsi': round(rsi, 2),
                'macd': round(ema_12 - ema_26, 4),
                'atr': round(atr, 2),
                'price_change_24h': random.uniform(-5, 5)
            },
            'market_conditions': {
                'volume_ratio': random.uniform(0.8, 1.5),
                'current_volatility': random.uniform(1, 4),
                'volatility_percentile': random.uniform(20, 80),
                'short_term_trend': random.uniform(-0.001, 0.001),
                'long_term_trend': random.uniform(-0.0005, 0.0005),
                'atr': round(atr, 2)
            },
            'analysis_quality': 'simulated'
        }
