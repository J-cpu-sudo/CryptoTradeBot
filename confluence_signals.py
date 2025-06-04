import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class SignalStrength(Enum):
    VERY_WEAK = 1
    WEAK = 2
    MODERATE = 3
    STRONG = 4
    VERY_STRONG = 5

class TrendDirection(Enum):
    BEARISH = -1
    NEUTRAL = 0
    BULLISH = 1

@dataclass
class ConfluenceResult:
    signal: str  # 'buy', 'sell', 'hold'
    strength: float  # 0-1
    confidence: float  # 0-1
    components: Dict[str, Any]
    confluence_score: float
    risk_reward_ratio: float
    entry_price: float
    stop_loss: float
    take_profit: float

class AdvancedConfluenceAnalyzer:
    """Advanced confluence signal analysis with multiple technical indicators"""
    
    def __init__(self):
        self.min_confluence_score = 0.6
        self.min_risk_reward = 1.5
        
        # Indicator weights for confluence
        self.weights = {
            'trend_slope': 0.25,
            'rsi_divergence': 0.20,
            'macd_confluence': 0.20,
            'volume_confirmation': 0.15,
            'support_resistance': 0.10,
            'momentum_acceleration': 0.10
        }
        
        logging.info("Advanced confluence analyzer initialized")
    
    def analyze_confluence(self, candles: List[List[str]], current_price: float) -> ConfluenceResult:
        """
        Perform comprehensive confluence analysis
        
        Args:
            candles: OHLCV candlestick data
            current_price: Current market price
            
        Returns:
            ConfluenceResult with detailed analysis
        """
        try:
            if len(candles) < 50:
                return self._no_signal("Insufficient data for confluence analysis", current_price)
            
            # Extract price data
            closes = [float(candle[4]) for candle in candles]
            highs = [float(candle[2]) for candle in candles]
            lows = [float(candle[3]) for candle in candles]
            volumes = [float(candle[5]) for candle in candles]
            
            # Calculate all confluence components
            trend_analysis = self._analyze_trend_slope(closes)
            rsi_analysis = self._analyze_rsi_confluence(closes)
            macd_analysis = self._analyze_macd_confluence(closes)
            volume_analysis = self._analyze_volume_confluence(closes, volumes)
            support_resistance = self._analyze_support_resistance(highs, lows, closes, current_price)
            momentum_analysis = self._analyze_momentum_acceleration(closes)
            
            # Calculate confluence score
            confluence_score = self._calculate_confluence_score({
                'trend_slope': trend_analysis,
                'rsi_divergence': rsi_analysis,
                'macd_confluence': macd_analysis,
                'volume_confirmation': volume_analysis,
                'support_resistance': support_resistance,
                'momentum_acceleration': momentum_analysis
            })
            
            # Determine signal based on confluence
            signal_result = self._determine_confluence_signal(
                confluence_score, 
                current_price,
                trend_analysis,
                support_resistance
            )
            
            return signal_result
            
        except Exception as e:
            logging.error(f"Confluence analysis error: {e}")
            return self._no_signal(f"Analysis error: {str(e)}", current_price)
    
    def _analyze_trend_slope(self, closes: List[float]) -> Dict[str, Any]:
        """Analyze trend using linear regression slope and trend strength"""
        try:
            # Multiple timeframe trend analysis
            short_term = closes[-20:]  # 20 periods
            medium_term = closes[-50:]  # 50 periods
            
            # Calculate slopes
            short_slope = self._calculate_slope(short_term)
            medium_slope = self._calculate_slope(medium_term)
            
            # Trend acceleration (slope of slopes)
            recent_slopes = []
            for i in range(5, 21):  # Last 15 slope calculations
                if len(closes) >= i + 10:
                    period_data = closes[-(i+10):-i]
                    recent_slopes.append(self._calculate_slope(period_data))
            
            trend_acceleration = self._calculate_slope(recent_slopes) if len(recent_slopes) > 5 else 0
            
            # Trend consistency (R-squared)
            short_r2 = self._calculate_r_squared(short_term)
            medium_r2 = self._calculate_r_squared(medium_term)
            
            # Determine trend direction and strength
            if short_slope > 0.001 and medium_slope > 0.0005:
                direction = TrendDirection.BULLISH
                strength = min((short_slope * 1000 + medium_slope * 2000) / 2, 1.0)
            elif short_slope < -0.001 and medium_slope < -0.0005:
                direction = TrendDirection.BEARISH
                strength = min((abs(short_slope) * 1000 + abs(medium_slope) * 2000) / 2, 1.0)
            else:
                direction = TrendDirection.NEUTRAL
                strength = 0.0
            
            return {
                'direction': direction,
                'strength': strength,
                'short_slope': short_slope,
                'medium_slope': medium_slope,
                'acceleration': trend_acceleration,
                'consistency': (short_r2 + medium_r2) / 2,
                'score': strength * ((short_r2 + medium_r2) / 2)
            }
            
        except Exception as e:
            logging.error(f"Trend slope analysis error: {e}")
            return {'direction': TrendDirection.NEUTRAL, 'strength': 0, 'score': 0}
    
    def _analyze_rsi_confluence(self, closes: List[float]) -> Dict[str, Any]:
        """Advanced RSI analysis with divergence detection"""
        try:
            rsi_14 = self._calculate_rsi(closes, 14)
            rsi_21 = self._calculate_rsi(closes, 21)
            
            if not rsi_14 or not rsi_21 or len(rsi_14) < 20:
                return {'score': 0, 'signal': 'neutral'}
            
            current_rsi_14 = rsi_14[-1]
            current_rsi_21 = rsi_21[-1]
            
            # RSI divergence detection
            price_peaks, price_troughs = self._find_peaks_troughs(closes[-20:])
            rsi_peaks, rsi_troughs = self._find_peaks_troughs(rsi_14[-20:])
            
            bullish_divergence = self._detect_bullish_divergence(price_troughs, rsi_troughs)
            bearish_divergence = self._detect_bearish_divergence(price_peaks, rsi_peaks)
            
            # RSI confluence score
            score = 0
            signal = 'neutral'
            
            # Oversold/Overbought with momentum
            if current_rsi_14 < 30 and current_rsi_21 < 35 and bullish_divergence:
                score = 0.8
                signal = 'bullish'
            elif current_rsi_14 > 70 and current_rsi_21 > 65 and bearish_divergence:
                score = 0.8
                signal = 'bearish'
            elif current_rsi_14 < 40 and rsi_14[-1] > rsi_14[-2] > rsi_14[-3]:
                score = 0.6
                signal = 'bullish'
            elif current_rsi_14 > 60 and rsi_14[-1] < rsi_14[-2] < rsi_14[-3]:
                score = 0.6
                signal = 'bearish'
            
            return {
                'rsi_14': current_rsi_14,
                'rsi_21': current_rsi_21,
                'bullish_divergence': bullish_divergence,
                'bearish_divergence': bearish_divergence,
                'signal': signal,
                'score': score
            }
            
        except Exception as e:
            logging.error(f"RSI confluence analysis error: {e}")
            return {'score': 0, 'signal': 'neutral'}
    
    def _analyze_macd_confluence(self, closes: List[float]) -> Dict[str, Any]:
        """Advanced MACD analysis with histogram and signal line confluence"""
        try:
            macd_line, signal_line, histogram = self._calculate_macd(closes)
            
            if not macd_line or len(macd_line) < 10:
                return {'score': 0, 'signal': 'neutral'}
            
            current_macd = macd_line[-1]
            current_signal = signal_line[-1]
            current_histogram = histogram[-1]
            
            # MACD momentum analysis
            macd_momentum = current_macd - macd_line[-3] if len(macd_line) >= 3 else 0
            histogram_momentum = current_histogram - histogram[-3] if len(histogram) >= 3 else 0
            
            # Signal line crossover detection
            bullish_crossover = (current_macd > current_signal and 
                               macd_line[-2] <= signal_line[-2])
            bearish_crossover = (current_macd < current_signal and 
                               macd_line[-2] >= signal_line[-2])
            
            # Zero line analysis
            zero_cross_bullish = current_macd > 0 and macd_line[-2] <= 0
            zero_cross_bearish = current_macd < 0 and macd_line[-2] >= 0
            
            # Histogram divergence
            histogram_increasing = all(histogram[-i] > histogram[-(i+1)] for i in range(1, 4))
            histogram_decreasing = all(histogram[-i] < histogram[-(i+1)] for i in range(1, 4))
            
            score = 0
            signal = 'neutral'
            
            if bullish_crossover and histogram_increasing and macd_momentum > 0:
                score = 0.9
                signal = 'bullish'
            elif bearish_crossover and histogram_decreasing and macd_momentum < 0:
                score = 0.9
                signal = 'bearish'
            elif zero_cross_bullish and histogram_momentum > 0:
                score = 0.7
                signal = 'bullish'
            elif zero_cross_bearish and histogram_momentum < 0:
                score = 0.7
                signal = 'bearish'
            
            return {
                'macd': current_macd,
                'signal': current_signal,
                'histogram': current_histogram,
                'macd_momentum': macd_momentum,
                'histogram_momentum': histogram_momentum,
                'bullish_crossover': bullish_crossover,
                'bearish_crossover': bearish_crossover,
                'signal_direction': signal,
                'score': score
            }
            
        except Exception as e:
            logging.error(f"MACD confluence analysis error: {e}")
            return {'score': 0, 'signal': 'neutral'}
    
    def _analyze_volume_confluence(self, closes: List[float], volumes: List[float]) -> Dict[str, Any]:
        """Volume analysis with price-volume relationship"""
        try:
            if len(volumes) < 20:
                return {'score': 0, 'confirmation': False}
            
            # Volume moving averages
            vol_ma_10 = sum(volumes[-10:]) / 10
            vol_ma_20 = sum(volumes[-20:]) / 20
            current_volume = volumes[-1]
            
            # Price-volume relationship
            price_change = (closes[-1] - closes[-2]) / closes[-2] if len(closes) > 1 else 0
            volume_ratio = current_volume / vol_ma_20
            
            # Volume trend
            volume_increasing = vol_ma_10 > vol_ma_20
            high_volume = volume_ratio > 1.5
            
            # On-Balance Volume (OBV)
            obv = self._calculate_obv(closes, volumes)
            obv_trend = obv[-1] > obv[-5] if len(obv) >= 5 else False
            
            # Volume confirmation scoring
            score = 0
            confirmation = False
            
            if price_change > 0.01 and high_volume and obv_trend:  # Bullish volume confirmation
                score = 0.8
                confirmation = True
            elif price_change < -0.01 and high_volume and not obv_trend:  # Bearish volume confirmation
                score = 0.8
                confirmation = True
            elif volume_increasing and volume_ratio > 1.2:
                score = 0.5
                confirmation = True
            
            return {
                'current_volume': current_volume,
                'volume_ma_20': vol_ma_20,
                'volume_ratio': volume_ratio,
                'volume_increasing': volume_increasing,
                'high_volume': high_volume,
                'obv_trend': obv_trend,
                'confirmation': confirmation,
                'score': score
            }
            
        except Exception as e:
            logging.error(f"Volume confluence analysis error: {e}")
            return {'score': 0, 'confirmation': False}
    
    def _analyze_support_resistance(self, highs: List[float], lows: List[float], 
                                  closes: List[float], current_price: float) -> Dict[str, Any]:
        """Support and resistance level analysis"""
        try:
            # Find pivot points
            support_levels = self._find_support_levels(lows, closes)
            resistance_levels = self._find_resistance_levels(highs, closes)
            
            # Find nearest levels
            nearest_support = max([s for s in support_levels if s < current_price], default=0)
            nearest_resistance = min([r for r in resistance_levels if r > current_price], default=float('inf'))
            
            # Distance to levels
            support_distance = (current_price - nearest_support) / current_price if nearest_support > 0 else 1
            resistance_distance = (nearest_resistance - current_price) / current_price if nearest_resistance < float('inf') else 1
            
            # Level strength (how many times tested)
            support_strength = sum(1 for low in lows[-50:] if abs(low - nearest_support) / nearest_support < 0.01)
            resistance_strength = sum(1 for high in highs[-50:] if abs(high - nearest_resistance) / nearest_resistance < 0.01)
            
            # Scoring based on proximity and strength
            score = 0
            signal = 'neutral'
            
            if support_distance < 0.02 and support_strength >= 2:  # Near strong support
                score = 0.7
                signal = 'bullish'
            elif resistance_distance < 0.02 and resistance_strength >= 2:  # Near strong resistance
                score = 0.7
                signal = 'bearish'
            
            return {
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance,
                'support_distance': support_distance,
                'resistance_distance': resistance_distance,
                'support_strength': support_strength,
                'resistance_strength': resistance_strength,
                'signal': signal,
                'score': score
            }
            
        except Exception as e:
            logging.error(f"Support/resistance analysis error: {e}")
            return {'score': 0, 'signal': 'neutral'}
    
    def _analyze_momentum_acceleration(self, closes: List[float]) -> Dict[str, Any]:
        """Momentum acceleration analysis"""
        try:
            if len(closes) < 20:
                return {'score': 0, 'acceleration': 0}
            
            # Calculate momentum (rate of change)
            momentum_5 = [(closes[i] - closes[i-5]) / closes[i-5] for i in range(5, len(closes))]
            momentum_10 = [(closes[i] - closes[i-10]) / closes[i-10] for i in range(10, len(closes))]
            
            # Momentum acceleration (second derivative)
            if len(momentum_5) >= 3:
                recent_momentum = momentum_5[-3:]
                momentum_acceleration = (recent_momentum[-1] - recent_momentum[0]) / 2
            else:
                momentum_acceleration = 0
            
            # Momentum persistence
            momentum_direction = 1 if momentum_5[-1] > 0 else -1
            momentum_persistence = sum(1 for m in momentum_5[-5:] if (m > 0) == (momentum_direction > 0)) / 5
            
            # Scoring
            score = min(abs(momentum_acceleration) * 100 * momentum_persistence, 1.0)
            
            return {
                'momentum_5': momentum_5[-1] if momentum_5 else 0,
                'momentum_10': momentum_10[-1] if momentum_10 else 0,
                'acceleration': momentum_acceleration,
                'persistence': momentum_persistence,
                'direction': momentum_direction,
                'score': score
            }
            
        except Exception as e:
            logging.error(f"Momentum acceleration analysis error: {e}")
            return {'score': 0, 'acceleration': 0}
    
    def _calculate_confluence_score(self, components: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall confluence score"""
        total_score = 0
        bullish_signals = 0
        bearish_signals = 0
        
        for component_name, component_data in components.items():
            weight = self.weights.get(component_name, 0)
            component_score = component_data.get('score', 0)
            
            weighted_score = component_score * weight
            total_score += weighted_score
            
            # Count signal direction
            signal = component_data.get('signal', 'neutral')
            if signal == 'bullish':
                bullish_signals += 1
            elif signal == 'bearish':
                bearish_signals += 1
        
        # Determine overall direction
        if bullish_signals > bearish_signals:
            direction = 'bullish'
        elif bearish_signals > bullish_signals:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        return {
            'total_score': total_score,
            'direction': direction,
            'bullish_count': bullish_signals,
            'bearish_count': bearish_signals,
            'components': components
        }
    
    def _determine_confluence_signal(self, confluence_data: Dict[str, Any], 
                                   current_price: float, trend_analysis: Dict[str, Any],
                                   support_resistance: Dict[str, Any]) -> ConfluenceResult:
        """Determine final signal based on confluence analysis"""
        total_score = confluence_data['total_score']
        direction = confluence_data['direction']
        
        if total_score < self.min_confluence_score:
            return self._no_signal("Insufficient confluence", current_price)
        
        # Calculate risk-reward based on support/resistance
        if direction == 'bullish':
            entry_price = current_price
            stop_loss = max(support_resistance.get('nearest_support', current_price * 0.98), 
                          current_price * 0.98)
            take_profit = min(support_resistance.get('nearest_resistance', current_price * 1.04),
                            current_price * 1.04)
            signal = 'buy'
        elif direction == 'bearish':
            entry_price = current_price
            stop_loss = min(support_resistance.get('nearest_resistance', current_price * 1.02),
                          current_price * 1.02)
            take_profit = max(support_resistance.get('nearest_support', current_price * 0.96),
                            current_price * 0.96)
            signal = 'sell'
        else:
            return self._no_signal("Neutral confluence", current_price)
        
        # Calculate risk-reward ratio
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        if risk_reward_ratio < self.min_risk_reward:
            return self._no_signal(f"Poor risk-reward ratio: {risk_reward_ratio:.2f}", current_price)
        
        # Calculate confidence based on trend alignment
        trend_alignment = 1.0
        if trend_analysis['direction'] == TrendDirection.BULLISH and direction == 'bullish':
            trend_alignment = 1.2
        elif trend_analysis['direction'] == TrendDirection.BEARISH and direction == 'bearish':
            trend_alignment = 1.2
        elif trend_analysis['direction'] != TrendDirection.NEUTRAL:
            trend_alignment = 0.8
        
        confidence = min(total_score * trend_alignment, 1.0)
        
        return ConfluenceResult(
            signal=signal,
            strength=total_score,
            confidence=confidence,
            components=confluence_data['components'],
            confluence_score=total_score,
            risk_reward_ratio=risk_reward_ratio,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    def _no_signal(self, reason: str, current_price: float) -> ConfluenceResult:
        """Return no signal result"""
        return ConfluenceResult(
            signal='hold',
            strength=0.0,
            confidence=0.0,
            components={},
            confluence_score=0.0,
            risk_reward_ratio=0.0,
            entry_price=current_price,
            stop_loss=current_price,
            take_profit=current_price
        )
    
    # Technical indicator calculation methods
    def _calculate_slope(self, data: List[float]) -> float:
        """Calculate linear regression slope"""
        if len(data) < 2:
            return 0
        x = np.arange(len(data))
        y = np.array(data)
        return np.polyfit(x, y, 1)[0]
    
    def _calculate_r_squared(self, data: List[float]) -> float:
        """Calculate R-squared for trend consistency"""
        if len(data) < 3:
            return 0
        x = np.arange(len(data))
        y = np.array(data)
        try:
            correlation_matrix = np.corrcoef(x, y)
            correlation = correlation_matrix[0, 1]
            return correlation ** 2
        except:
            return 0
    
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> List[float]:
        """Calculate RSI"""
        if len(closes) < period + 1:
            return []
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        rsi_values = []
        for i in range(period - 1, len(gains)):
            avg_gain = sum(gains[i-period+1:i+1]) / period
            avg_loss = sum(losses[i-period+1:i+1]) / period
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            rsi_values.append(rsi)
        
        return rsi_values
    
    def _calculate_macd(self, closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
        """Calculate MACD line, signal line, and histogram"""
        if len(closes) < slow + signal:
            return [], [], []
        
        # Calculate EMAs
        ema_fast = self._calculate_ema(closes, fast)
        ema_slow = self._calculate_ema(closes, slow)
        
        # MACD line
        macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]
        
        # Signal line (EMA of MACD)
        signal_line = self._calculate_ema(macd_line, signal)
        
        # Histogram
        histogram = [macd_line[i] - signal_line[i] for i in range(len(signal_line))]
        
        return macd_line[-len(histogram):], signal_line, histogram
    
    def _calculate_ema(self, data: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return []
        
        multiplier = 2 / (period + 1)
        ema_values = [sum(data[:period]) / period]  # First SMA
        
        for i in range(period, len(data)):
            ema = data[i] * multiplier + ema_values[-1] * (1 - multiplier)
            ema_values.append(ema)
        
        return ema_values
    
    def _calculate_obv(self, closes: List[float], volumes: List[float]) -> List[float]:
        """Calculate On-Balance Volume"""
        if len(closes) != len(volumes) or len(closes) < 2:
            return []
        
        obv = [volumes[0]]
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                obv.append(obv[-1] + volumes[i])
            elif closes[i] < closes[i-1]:
                obv.append(obv[-1] - volumes[i])
            else:
                obv.append(obv[-1])
        
        return obv
    
    def _find_peaks_troughs(self, data: List[float]) -> Tuple[List[int], List[int]]:
        """Find peaks and troughs in data"""
        peaks = []
        troughs = []
        
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                peaks.append(i)
            elif data[i] < data[i-1] and data[i] < data[i+1]:
                troughs.append(i)
        
        return peaks, troughs
    
    def _detect_bullish_divergence(self, price_troughs: List[int], rsi_troughs: List[int]) -> bool:
        """Detect bullish divergence between price and RSI"""
        if len(price_troughs) < 2 or len(rsi_troughs) < 2:
            return False
        
        # Check if recent price made lower low but RSI made higher low
        recent_price_trough = price_troughs[-1]
        prev_price_trough = price_troughs[-2]
        
        for rsi_trough in rsi_troughs[-2:]:
            if abs(rsi_trough - recent_price_trough) <= 2:  # Allow some offset
                return True
        
        return False
    
    def _detect_bearish_divergence(self, price_peaks: List[int], rsi_peaks: List[int]) -> bool:
        """Detect bearish divergence between price and RSI"""
        if len(price_peaks) < 2 or len(rsi_peaks) < 2:
            return False
        
        # Check if recent price made higher high but RSI made lower high
        recent_price_peak = price_peaks[-1]
        prev_price_peak = price_peaks[-2]
        
        for rsi_peak in rsi_peaks[-2:]:
            if abs(rsi_peak - recent_price_peak) <= 2:  # Allow some offset
                return True
        
        return False
    
    def _find_support_levels(self, lows: List[float], closes: List[float]) -> List[float]:
        """Find support levels from price data"""
        support_levels = []
        
        # Find significant lows
        for i in range(2, len(lows) - 2):
            if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
                lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                support_levels.append(lows[i])
        
        # Remove duplicate levels (within 1%)
        filtered_levels = []
        for level in sorted(support_levels):
            if not any(abs(level - existing) / existing < 0.01 for existing in filtered_levels):
                filtered_levels.append(level)
        
        return filtered_levels
    
    def _find_resistance_levels(self, highs: List[float], closes: List[float]) -> List[float]:
        """Find resistance levels from price data"""
        resistance_levels = []
        
        # Find significant highs
        for i in range(2, len(highs) - 2):
            if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
                highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                resistance_levels.append(highs[i])
        
        # Remove duplicate levels (within 1%)
        filtered_levels = []
        for level in sorted(resistance_levels, reverse=True):
            if not any(abs(level - existing) / existing < 0.01 for existing in filtered_levels):
                filtered_levels.append(level)
        
        return filtered_levels