import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class StrategyMode(Enum):
    PRECISION = "precision"      # High confluence, low frequency
    AGGRESSIVE = "aggressive"    # Higher risk, more signals
    CONSERVATIVE = "conservative" # Minimum risk, max filters

class SignalQuality(Enum):
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4

@dataclass
class StrategySignal:
    action: str  # 'buy', 'sell', 'hold'
    quality: SignalQuality
    strength: float  # 0-1
    confidence: float  # 0-1
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    confluence_components: Dict[str, Any]
    volume_confirmation: bool
    volatility_check: bool
    reasons: List[str]
    timestamp: datetime

class AdvancedStrategyEngine:
    """Advanced strategy engine with RSI/EMA confluence and volume filters"""
    
    def __init__(self, mode: StrategyMode = StrategyMode.PRECISION):
        self.mode = mode
        self.setup_mode_parameters()
        
        # Real-time data tracking
        self.price_buffer = []
        self.volume_buffer = []
        self.last_signal_time = None
        self.signal_cooldown = timedelta(minutes=15)
        
        logging.info(f"Advanced strategy engine initialized in {mode.value} mode")
    
    def setup_mode_parameters(self):
        """Setup parameters based on strategy mode"""
        if self.mode == StrategyMode.PRECISION:
            self.min_confluence_score = 0.8
            self.min_volume_ratio = 2.0
            self.max_volatility_percentile = 70
            self.min_risk_reward = 2.0
            self.rsi_oversold = 25
            self.rsi_overbought = 75
            
        elif self.mode == StrategyMode.AGGRESSIVE:
            self.min_confluence_score = 0.6
            self.min_volume_ratio = 1.5
            self.max_volatility_percentile = 85
            self.min_risk_reward = 1.5
            self.rsi_oversold = 30
            self.rsi_overbought = 70
            
        else:  # CONSERVATIVE
            self.min_confluence_score = 0.9
            self.min_volume_ratio = 3.0
            self.max_volatility_percentile = 60
            self.min_risk_reward = 2.5
            self.rsi_oversold = 20
            self.rsi_overbought = 80
    
    def analyze_market_entry(self, market_data: Dict[str, Any], 
                           price_history: List[float],
                           volume_history: List[float]) -> StrategySignal:
        """
        Analyze market for high-quality entry signals with confluence filters
        
        Args:
            market_data: Current market data from WebSocket
            price_history: Recent price history
            volume_history: Recent volume history
            
        Returns:
            StrategySignal with detailed analysis
        """
        try:
            # Check signal cooldown
            if self._is_in_cooldown():
                return self._no_signal("Signal cooldown active")
            
            # Update buffers with latest data
            self._update_buffers(market_data, price_history, volume_history)
            
            current_price = market_data.get('price', 0)
            
            if not self._has_sufficient_data():
                return self._no_signal("Insufficient data for analysis")
            
            # Step 1: RSI/EMA Confluence Analysis
            rsi_ema_confluence = self._analyze_rsi_ema_confluence()
            
            # Step 2: MACD Momentum Confirmation
            macd_confirmation = self._analyze_macd_momentum()
            
            # Step 3: Volume Filter
            volume_analysis = self._analyze_volume_conditions(market_data)
            
            # Step 4: Volatility Threshold Check
            volatility_check = self._check_volatility_threshold()
            
            # Step 5: Price Action Quality
            price_action = self._analyze_price_action_quality()
            
            # Step 6: Market Structure Analysis
            market_structure = self._analyze_market_structure()
            
            # Combine all components
            confluence_score = self._calculate_confluence_score({
                'rsi_ema': rsi_ema_confluence,
                'macd': macd_confirmation,
                'volume': volume_analysis,
                'volatility': volatility_check,
                'price_action': price_action,
                'market_structure': market_structure
            })
            
            # Generate final signal
            signal = self._generate_final_signal(
                confluence_score, current_price, market_data
            )
            
            return signal
            
        except Exception as e:
            logging.error(f"Strategy analysis error: {e}")
            return self._no_signal(f"Analysis error: {str(e)}")
    
    def _analyze_rsi_ema_confluence(self) -> Dict[str, Any]:
        """Analyze RSI and EMA confluence for entry signals"""
        try:
            if len(self.price_buffer) < 50:
                return {'score': 0, 'signal': 'neutral', 'reason': 'Insufficient data'}
            
            prices = np.array(self.price_buffer[-50:])
            
            # Calculate RSI
            rsi = self._calculate_rsi(prices, 14)
            if not rsi or len(rsi) < 3:
                return {'score': 0, 'signal': 'neutral', 'reason': 'RSI calculation failed'}
            
            current_rsi = rsi[-1]
            rsi_trend = rsi[-1] - rsi[-3]  # 3-period RSI trend
            
            # Calculate EMAs
            ema_12 = self._calculate_ema(prices, 12)
            ema_26 = self._calculate_ema(prices, 26)
            ema_50 = self._calculate_ema(prices, 50)
            
            if not all([ema_12, ema_26, ema_50]):
                return {'score': 0, 'signal': 'neutral', 'reason': 'EMA calculation failed'}
            
            current_price = prices[-1]
            
            # EMA confluence analysis
            ema_12_val = ema_12[-1]
            ema_26_val = ema_26[-1]
            ema_50_val = ema_50[-1]
            
            # Bullish confluence conditions
            bullish_ema_stack = ema_12_val > ema_26_val > ema_50_val
            price_above_emas = current_price > ema_12_val
            rsi_oversold_recovery = current_rsi < self.rsi_oversold and rsi_trend > 2
            rsi_bullish_momentum = 40 < current_rsi < 60 and rsi_trend > 1
            
            # Bearish confluence conditions
            bearish_ema_stack = ema_12_val < ema_26_val < ema_50_val
            price_below_emas = current_price < ema_12_val
            rsi_overbought_decline = current_rsi > self.rsi_overbought and rsi_trend < -2
            rsi_bearish_momentum = 40 < current_rsi < 60 and rsi_trend < -1
            
            # Score calculation
            if bullish_ema_stack and price_above_emas and (rsi_oversold_recovery or rsi_bullish_momentum):
                score = 0.9 if rsi_oversold_recovery else 0.7
                signal = 'bullish'
                reason = f"Strong bullish confluence: RSI {current_rsi:.1f}, EMA stack aligned"
                
            elif bearish_ema_stack and price_below_emas and (rsi_overbought_decline or rsi_bearish_momentum):
                score = 0.9 if rsi_overbought_decline else 0.7
                signal = 'bearish'
                reason = f"Strong bearish confluence: RSI {current_rsi:.1f}, EMA stack aligned"
                
            else:
                score = 0.3
                signal = 'neutral'
                reason = f"No clear confluence: RSI {current_rsi:.1f}"
            
            return {
                'score': score,
                'signal': signal,
                'reason': reason,
                'rsi': current_rsi,
                'rsi_trend': rsi_trend,
                'ema_12': ema_12_val,
                'ema_26': ema_26_val,
                'ema_50': ema_50_val,
                'bullish_stack': bullish_ema_stack,
                'bearish_stack': bearish_ema_stack
            }
            
        except Exception as e:
            logging.error(f"RSI/EMA confluence analysis error: {e}")
            return {'score': 0, 'signal': 'neutral', 'reason': f'Error: {str(e)}'}
    
    def _analyze_macd_momentum(self) -> Dict[str, Any]:
        """Analyze MACD for momentum confirmation"""
        try:
            if len(self.price_buffer) < 40:
                return {'score': 0, 'confirmation': False, 'reason': 'Insufficient data'}
            
            prices = np.array(self.price_buffer[-40:])
            
            # Calculate MACD components
            ema_12 = self._calculate_ema(prices, 12)
            ema_26 = self._calculate_ema(prices, 26)
            
            if not ema_12 or not ema_26 or len(ema_12) < 10:
                return {'score': 0, 'confirmation': False, 'reason': 'MACD calculation failed'}
            
            # MACD line
            macd_line = np.array(ema_12) - np.array(ema_26)
            
            # Signal line (9-period EMA of MACD)
            signal_line = self._calculate_ema(macd_line, 9)
            
            if not signal_line or len(signal_line) < 3:
                return {'score': 0, 'confirmation': False, 'reason': 'Signal line calculation failed'}
            
            # Histogram
            histogram = macd_line[-len(signal_line):] - signal_line
            
            current_macd = macd_line[-1]
            current_signal = signal_line[-1]
            current_histogram = histogram[-1]
            
            # Momentum analysis
            macd_momentum = current_macd - macd_line[-3]
            histogram_increasing = histogram[-1] > histogram[-2] > histogram[-3]
            histogram_decreasing = histogram[-1] < histogram[-2] < histogram[-3]
            
            # Crossover detection
            bullish_crossover = (current_macd > current_signal and 
                               macd_line[-2] <= signal_line[-2])
            bearish_crossover = (current_macd < current_signal and 
                               macd_line[-2] >= signal_line[-2])
            
            # Zero line analysis
            above_zero = current_macd > 0
            macd_trend = "bullish" if macd_momentum > 0 else "bearish"
            
            # Scoring
            if bullish_crossover and histogram_increasing and macd_momentum > 0:
                score = 0.9
                confirmation = True
                reason = "Strong bullish MACD crossover with momentum"
                
            elif bearish_crossover and histogram_decreasing and macd_momentum < 0:
                score = 0.9
                confirmation = True
                reason = "Strong bearish MACD crossover with momentum"
                
            elif histogram_increasing and above_zero and macd_momentum > 0:
                score = 0.6
                confirmation = True
                reason = "MACD bullish momentum confirmed"
                
            elif histogram_decreasing and not above_zero and macd_momentum < 0:
                score = 0.6
                confirmation = True
                reason = "MACD bearish momentum confirmed"
                
            else:
                score = 0.2
                confirmation = False
                reason = f"MACD momentum unclear: {macd_trend}"
            
            return {
                'score': score,
                'confirmation': confirmation,
                'reason': reason,
                'macd': current_macd,
                'signal_line': current_signal,
                'histogram': current_histogram,
                'momentum': macd_momentum,
                'trend': macd_trend,
                'bullish_crossover': bullish_crossover,
                'bearish_crossover': bearish_crossover
            }
            
        except Exception as e:
            logging.error(f"MACD momentum analysis error: {e}")
            return {'score': 0, 'confirmation': False, 'reason': f'Error: {str(e)}'}
    
    def _analyze_volume_conditions(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze volume conditions for entry confirmation"""
        try:
            current_volume = market_data.get('volume_24h', 0)
            volume_spike = market_data.get('volume_spike', {})
            
            if len(self.volume_buffer) < 10:
                return {'score': 0.3, 'confirmed': False, 'reason': 'Insufficient volume data'}
            
            # Calculate volume metrics
            avg_volume = np.mean(self.volume_buffer[-20:]) if len(self.volume_buffer) >= 20 else np.mean(self.volume_buffer)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Volume spike analysis
            spike_detected = volume_spike.get('detected', False)
            spike_ratio = volume_spike.get('ratio', 1.0)
            
            # Buy/sell pressure from market data
            trade_flow = market_data.get('buy_sell_ratio', {})
            buy_ratio = trade_flow.get('buy_ratio', 0.5)
            net_flow = trade_flow.get('net_flow', 0)
            
            # Volume confirmation scoring
            if spike_detected and spike_ratio >= self.min_volume_ratio:
                if buy_ratio > 0.6:  # Strong buying pressure
                    score = 0.9
                    confirmed = True
                    reason = f"Strong volume spike with buying pressure (ratio: {spike_ratio:.1f}x)"
                elif buy_ratio < 0.4:  # Strong selling pressure
                    score = 0.9
                    confirmed = True
                    reason = f"Strong volume spike with selling pressure (ratio: {spike_ratio:.1f}x)"
                else:
                    score = 0.6
                    confirmed = True
                    reason = f"Volume spike detected but mixed pressure (ratio: {spike_ratio:.1f}x)"
            
            elif volume_ratio >= self.min_volume_ratio * 0.7:  # Above average volume
                score = 0.7
                confirmed = True
                reason = f"Above average volume (ratio: {volume_ratio:.1f}x)"
            
            else:  # Low volume
                score = 0.2
                confirmed = False
                reason = f"Low volume conditions (ratio: {volume_ratio:.1f}x)"
            
            return {
                'score': score,
                'confirmed': confirmed,
                'reason': reason,
                'volume_ratio': volume_ratio,
                'spike_detected': spike_detected,
                'spike_ratio': spike_ratio,
                'buy_ratio': buy_ratio,
                'net_flow': net_flow
            }
            
        except Exception as e:
            logging.error(f"Volume analysis error: {e}")
            return {'score': 0.2, 'confirmed': False, 'reason': f'Error: {str(e)}'}
    
    def _check_volatility_threshold(self) -> Dict[str, Any]:
        """Check if volatility is within acceptable trading range"""
        try:
            if len(self.price_buffer) < 20:
                return {'score': 0.5, 'acceptable': True, 'reason': 'Insufficient data for volatility check'}
            
            prices = np.array(self.price_buffer[-20:])
            
            # Calculate ATR (Average True Range)
            highs = prices * 1.002  # Approximate high
            lows = prices * 0.998   # Approximate low
            closes = prices
            
            atr = self._calculate_atr(highs, lows, closes, 14)
            
            if not atr:
                return {'score': 0.5, 'acceptable': True, 'reason': 'ATR calculation failed'}
            
            current_atr = atr[-1]
            avg_atr = np.mean(atr[-10:]) if len(atr) >= 10 else current_atr
            
            # Volatility percentile calculation
            volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
            
            # Convert to percentile (simplified)
            volatility_percentile = min(volatility_ratio * 50, 100)
            
            if volatility_percentile <= self.max_volatility_percentile:
                score = 1.0 - (volatility_percentile / 100)
                acceptable = True
                reason = f"Volatility acceptable ({volatility_percentile:.0f}th percentile)"
            else:
                score = 0.1
                acceptable = False
                reason = f"High volatility warning ({volatility_percentile:.0f}th percentile)"
            
            return {
                'score': score,
                'acceptable': acceptable,
                'reason': reason,
                'atr': current_atr,
                'volatility_percentile': volatility_percentile,
                'threshold': self.max_volatility_percentile
            }
            
        except Exception as e:
            logging.error(f"Volatility check error: {e}")
            return {'score': 0.5, 'acceptable': True, 'reason': f'Error: {str(e)}'}
    
    def _analyze_price_action_quality(self) -> Dict[str, Any]:
        """Analyze price action quality and breakout potential"""
        try:
            if len(self.price_buffer) < 30:
                return {'score': 0.5, 'quality': 'unknown', 'reason': 'Insufficient data'}
            
            prices = np.array(self.price_buffer[-30:])
            current_price = prices[-1]
            
            # Price momentum
            short_momentum = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] > 0 else 0
            medium_momentum = (prices[-1] - prices[-10]) / prices[-10] if prices[-10] > 0 else 0
            
            # Support/resistance levels
            recent_highs = np.max(prices[-10:])
            recent_lows = np.min(prices[-10:])
            price_range = recent_highs - recent_lows
            
            # Position within range
            range_position = (current_price - recent_lows) / price_range if price_range > 0 else 0.5
            
            # Breakout detection
            breakout_above = current_price > recent_highs * 1.001
            breakout_below = current_price < recent_lows * 0.999
            
            # Price action quality scoring
            if breakout_above and short_momentum > 0.005:
                score = 0.8
                quality = 'bullish_breakout'
                reason = f"Bullish breakout above resistance with momentum"
                
            elif breakout_below and short_momentum < -0.005:
                score = 0.8
                quality = 'bearish_breakout'
                reason = f"Bearish breakdown below support with momentum"
                
            elif range_position < 0.2 and short_momentum > 0:  # Near support with upward momentum
                score = 0.7
                quality = 'support_bounce'
                reason = f"Potential support bounce"
                
            elif range_position > 0.8 and short_momentum < 0:  # Near resistance with downward momentum
                score = 0.7
                quality = 'resistance_rejection'
                reason = f"Potential resistance rejection"
                
            elif abs(short_momentum) < 0.001:  # Sideways/choppy
                score = 0.2
                quality = 'choppy'
                reason = f"Choppy/sideways price action"
                
            else:
                score = 0.5
                quality = 'neutral'
                reason = f"Neutral price action"
            
            return {
                'score': score,
                'quality': quality,
                'reason': reason,
                'short_momentum': short_momentum,
                'medium_momentum': medium_momentum,
                'range_position': range_position,
                'breakout_above': breakout_above,
                'breakout_below': breakout_below
            }
            
        except Exception as e:
            logging.error(f"Price action analysis error: {e}")
            return {'score': 0.5, 'quality': 'unknown', 'reason': f'Error: {str(e)}'}
    
    def _analyze_market_structure(self) -> Dict[str, Any]:
        """Analyze overall market structure health"""
        try:
            if len(self.price_buffer) < 50:
                return {'score': 0.5, 'structure': 'unknown', 'reason': 'Insufficient data'}
            
            prices = np.array(self.price_buffer[-50:])
            
            # Trend analysis using multiple timeframes
            short_trend = self._calculate_trend_slope(prices[-10:])
            medium_trend = self._calculate_trend_slope(prices[-20:])
            long_trend = self._calculate_trend_slope(prices[-50:])
            
            # Trend consistency
            trends_aligned = (short_trend > 0 and medium_trend > 0 and long_trend > 0) or \
                           (short_trend < 0 and medium_trend < 0 and long_trend < 0)
            
            # Market structure scoring
            if trends_aligned and abs(long_trend) > 0.001:
                if long_trend > 0:
                    score = 0.8
                    structure = 'strong_uptrend'
                    reason = f"Strong uptrend across all timeframes"
                else:
                    score = 0.8
                    structure = 'strong_downtrend'
                    reason = f"Strong downtrend across all timeframes"
            
            elif not trends_aligned:
                score = 0.3
                structure = 'conflicted'
                reason = f"Conflicting trends across timeframes"
            
            else:
                score = 0.5
                structure = 'neutral'
                reason = f"Neutral market structure"
            
            return {
                'score': score,
                'structure': structure,
                'reason': reason,
                'short_trend': short_trend,
                'medium_trend': medium_trend,
                'long_trend': long_trend,
                'trends_aligned': trends_aligned
            }
            
        except Exception as e:
            logging.error(f"Market structure analysis error: {e}")
            return {'score': 0.5, 'structure': 'unknown', 'reason': f'Error: {str(e)}'}
    
    def _calculate_confluence_score(self, components: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate weighted confluence score"""
        weights = {
            'rsi_ema': 0.30,
            'macd': 0.25,
            'volume': 0.20,
            'volatility': 0.10,
            'price_action': 0.10,
            'market_structure': 0.05
        }
        
        total_score = 0
        valid_components = 0
        bullish_signals = 0
        bearish_signals = 0
        
        for component_name, component_data in components.items():
            weight = weights.get(component_name, 0)
            component_score = component_data.get('score', 0)
            
            if component_score > 0:
                total_score += component_score * weight
                valid_components += 1
                
                # Count signal direction
                signal = component_data.get('signal', component_data.get('quality', 'neutral'))
                if 'bullish' in str(signal).lower() or signal == 'buy':
                    bullish_signals += 1
                elif 'bearish' in str(signal).lower() or signal == 'sell':
                    bearish_signals += 1
        
        # Normalize score
        normalized_score = total_score if valid_components > 0 else 0
        
        # Determine overall direction
        if bullish_signals > bearish_signals and bullish_signals >= 3:
            direction = 'bullish'
        elif bearish_signals > bullish_signals and bearish_signals >= 3:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        return {
            'total_score': normalized_score,
            'direction': direction,
            'bullish_count': bullish_signals,
            'bearish_count': bearish_signals,
            'valid_components': valid_components,
            'components': components
        }
    
    def _generate_final_signal(self, confluence_data: Dict[str, Any], 
                             current_price: float, market_data: Dict[str, Any]) -> StrategySignal:
        """Generate final trading signal based on confluence analysis"""
        try:
            total_score = confluence_data['total_score']
            direction = confluence_data['direction']
            
            # Check minimum confluence threshold
            if total_score < self.min_confluence_score:
                return self._no_signal(f"Confluence score too low: {total_score:.2f}")
            
            # Volume confirmation check
            volume_analysis = confluence_data['components'].get('volume', {})
            volume_confirmed = volume_analysis.get('confirmed', False)
            
            if not volume_confirmed and self.mode != StrategyMode.AGGRESSIVE:
                return self._no_signal("Volume confirmation required")
            
            # Volatility check
            volatility_check = confluence_data['components'].get('volatility', {})
            volatility_acceptable = volatility_check.get('acceptable', True)
            
            if not volatility_acceptable:
                return self._no_signal("Volatility too high for safe trading")
            
            # Generate signal based on direction
            if direction == 'bullish':
                action = 'buy'
                # Calculate levels for long position
                stop_loss = current_price * 0.98  # 2% stop loss
                take_profit = current_price * 1.04  # 4% take profit
                
            elif direction == 'bearish':
                action = 'sell'
                # Calculate levels for short position
                stop_loss = current_price * 1.02  # 2% stop loss
                take_profit = current_price * 0.96  # 4% take profit
                
            else:
                return self._no_signal("No clear directional signal")
            
            # Calculate risk-reward ratio
            risk = abs(current_price - stop_loss)
            reward = abs(take_profit - current_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            if risk_reward_ratio < self.min_risk_reward:
                return self._no_signal(f"Poor risk-reward ratio: {risk_reward_ratio:.2f}")
            
            # Determine signal quality
            if total_score >= 0.9:
                quality = SignalQuality.VERY_STRONG
            elif total_score >= 0.8:
                quality = SignalQuality.STRONG
            elif total_score >= 0.7:
                quality = SignalQuality.MODERATE
            else:
                quality = SignalQuality.WEAK
            
            # Generate reasons
            reasons = []
            for component_name, component_data in confluence_data['components'].items():
                reason = component_data.get('reason', '')
                if reason and component_data.get('score', 0) > 0.5:
                    reasons.append(f"{component_name}: {reason}")
            
            # Update signal timing
            self.last_signal_time = datetime.utcnow()
            
            return StrategySignal(
                action=action,
                quality=quality,
                strength=total_score,
                confidence=min(total_score * 1.1, 1.0),
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=risk_reward_ratio,
                confluence_components=confluence_data['components'],
                volume_confirmation=volume_confirmed,
                volatility_check=volatility_acceptable,
                reasons=reasons,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logging.error(f"Signal generation error: {e}")
            return self._no_signal(f"Signal generation error: {str(e)}")
    
    def _update_buffers(self, market_data: Dict[str, Any], 
                       price_history: List[float], volume_history: List[float]):
        """Update internal data buffers"""
        # Update price buffer
        if price_history:
            self.price_buffer = price_history[-100:]  # Keep last 100 prices
        
        # Update volume buffer
        if volume_history:
            self.volume_buffer = volume_history[-50:]  # Keep last 50 volume points
        
        # Add current data point
        current_price = market_data.get('price')
        current_volume = market_data.get('volume_24h')
        
        if current_price:
            self.price_buffer.append(current_price)
            if len(self.price_buffer) > 100:
                self.price_buffer.pop(0)
        
        if current_volume:
            self.volume_buffer.append(current_volume)
            if len(self.volume_buffer) > 50:
                self.volume_buffer.pop(0)
    
    def _has_sufficient_data(self) -> bool:
        """Check if we have sufficient data for analysis"""
        return len(self.price_buffer) >= 50 and len(self.volume_buffer) >= 10
    
    def _is_in_cooldown(self) -> bool:
        """Check if signal is in cooldown period"""
        if not self.last_signal_time:
            return False
        return datetime.utcnow() - self.last_signal_time < self.signal_cooldown
    
    def _no_signal(self, reason: str) -> StrategySignal:
        """Create no-signal response"""
        return StrategySignal(
            action='hold',
            quality=SignalQuality.WEAK,
            strength=0.0,
            confidence=0.0,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            risk_reward_ratio=0.0,
            confluence_components={},
            volume_confirmation=False,
            volatility_check=True,
            reasons=[reason],
            timestamp=datetime.utcnow()
        )
    
    # Technical indicator calculation methods
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> Optional[List[float]]:
        """Calculate RSI with numpy for better performance"""
        if len(prices) < period + 1:
            return None
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = []
        avg_losses = []
        
        # Initial values
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            avg_gains.append(avg_gain)
            avg_losses.append(avg_loss)
        
        rsi_values = []
        for avg_gain, avg_loss in zip(avg_gains, avg_losses):
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)
        
        return rsi_values
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> Optional[List[float]]:
        """Calculate EMA with numpy"""
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema_values = [np.mean(prices[:period])]  # Start with SMA
        
        for i in range(period, len(prices)):
            ema = prices[i] * multiplier + ema_values[-1] * (1 - multiplier)
            ema_values.append(ema)
        
        return ema_values
    
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, 
                      closes: np.ndarray, period: int = 14) -> Optional[List[float]]:
        """Calculate Average True Range"""
        if len(highs) < period + 1:
            return None
        
        true_ranges = []
        for i in range(1, len(highs)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            tr = max(tr1, tr2, tr3)
            true_ranges.append(tr)
        
        atr_values = []
        for i in range(period - 1, len(true_ranges)):
            atr = np.mean(true_ranges[i-period+1:i+1])
            atr_values.append(atr)
        
        return atr_values
    
    def _calculate_trend_slope(self, prices: np.ndarray) -> float:
        """Calculate trend slope using linear regression"""
        if len(prices) < 3:
            return 0.0
        
        x = np.arange(len(prices))
        y = prices
        
        try:
            slope = np.polyfit(x, y, 1)[0]
            return slope / prices[-1] if prices[-1] > 0 else 0  # Normalize by price
        except:
            return 0.0
    
    def set_mode(self, mode: StrategyMode):
        """Change strategy mode"""
        self.mode = mode
        self.setup_mode_parameters()
        logging.info(f"Strategy mode changed to {mode.value}")
    
    def get_mode_info(self) -> Dict[str, Any]:
        """Get current mode parameters"""
        return {
            'mode': self.mode.value,
            'min_confluence_score': self.min_confluence_score,
            'min_volume_ratio': self.min_volume_ratio,
            'max_volatility_percentile': self.max_volatility_percentile,
            'min_risk_reward': self.min_risk_reward,
            'rsi_oversold': self.rsi_oversold,
            'rsi_overbought': self.rsi_overbought
        }