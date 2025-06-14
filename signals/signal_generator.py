import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from market_analyzer import MarketAnalyzer
from advanced_market_filter import AdvancedMarketFilter

class SignalGenerator:
    def __init__(self, market_analyzer: MarketAnalyzer):
        self.market_analyzer = market_analyzer
        self.market_filter = AdvancedMarketFilter(market_analyzer)
        self.min_signal_strength = 0.6
        
    def get_signal(self, symbol: str = "BTC-USDT") -> Dict[str, Any]:
        """
        Generate trading signal based on comprehensive market analysis
        Returns: {
            'action': 'buy'|'sell'|'hold',
            'strength': float (0-1),
            'confidence': float (0-1),
            'reasons': list of strings,
            'stop_loss': float,
            'take_profit': float,
            'market_filter': dict with market conditions
        }
        """
        try:
            # First, check if market conditions are favorable
            market_filter_result = self.market_filter.is_market_favorable(symbol)
            
            # If market conditions are not favorable, return hold signal
            if not market_filter_result['favorable']:
                return {
                    'action': 'hold',
                    'strength': 0.0,
                    'confidence': 0.0,
                    'reasons': ['Market conditions unfavorable'] + market_filter_result['reasons'][:3],
                    'market_filter': market_filter_result,
                    'market_grade': market_filter_result['market_grade'],
                    'recommended_action': market_filter_result['recommended_action']
                }
            
            # Get market analysis
            analysis = self.market_analyzer.analyze_market(symbol)
            if not analysis:
                return self._no_signal("Failed to get market analysis", market_filter_result)
            
            # Get technical indicators
            indicators = analysis.get('indicators', {})
            market_conditions = analysis.get('market_conditions', {})
            
            # Calculate signal components with enhanced weighting based on market quality
            market_quality_multiplier = market_filter_result['overall_score']
            
            trend_signal = self._analyze_trend(indicators)
            momentum_signal = self._analyze_momentum(indicators)
            volatility_signal = self._analyze_volatility(market_conditions)
            volume_signal = self._analyze_volume(market_conditions)
            
            # Combine signals with market quality adjustment
            signal = self._combine_signals(
                trend_signal, momentum_signal, 
                volatility_signal, volume_signal,
                market_quality_multiplier
            )
            
            # Add market filter information to signal
            signal['market_filter'] = market_filter_result
            signal['market_grade'] = market_filter_result['market_grade']
            signal['market_quality'] = market_quality_multiplier
            
            # Add stop loss and take profit levels
            current_price = analysis.get('current_price', 0)
            if current_price and signal['action'] != 'hold':
                signal.update(self._calculate_levels(signal['action'], current_price))
            
            # Enhance signal strength based on market conditions
            if signal['action'] != 'hold':
                signal['strength'] *= market_quality_multiplier
                signal['confidence'] *= market_quality_multiplier
                
                # Add market quality context to reasons
                signal['reasons'].insert(0, f"Market grade: {market_filter_result['market_grade']} ({market_filter_result['overall_score']:.1f}/1.0)")
            
            logging.info(f"Generated signal: {signal['action']} (strength: {signal['strength']:.2f}, market grade: {market_filter_result['market_grade']})")
            return signal
            
        except Exception as e:
            logging.error(f"Error generating signal: {e}")
            return self._no_signal(f"Error: {str(e)}")
    
    def _analyze_trend(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trend using EMA crossover"""
        ema_12 = indicators.get('ema_12')
        ema_26 = indicators.get('ema_26')
        
        if not ema_12 or not ema_26:
            return {'signal': 0, 'strength': 0, 'reason': 'No EMA data'}
        
        # EMA crossover signal
        if ema_12 > ema_26:
            strength = min((ema_12 - ema_26) / ema_26 * 100, 1.0)
            return {
                'signal': 1,  # Bullish
                'strength': strength,
                'reason': f'EMA bullish crossover (12: {ema_12:.2f}, 26: {ema_26:.2f})'
            }
        elif ema_26 > ema_12:
            strength = min((ema_26 - ema_12) / ema_12 * 100, 1.0)
            return {
                'signal': -1,  # Bearish
                'strength': strength,
                'reason': f'EMA bearish crossover (12: {ema_12:.2f}, 26: {ema_26:.2f})'
            }
        else:
            return {'signal': 0, 'strength': 0, 'reason': 'EMAs are equal'}
    
    def _analyze_momentum(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze momentum using RSI and MACD"""
        rsi = indicators.get('rsi')
        macd = indicators.get('macd')
        
        signals = []
        total_strength = 0
        reasons = []
        
        # RSI analysis
        if rsi:
            if rsi < 30:  # Oversold
                signals.append(1)
                strength = (30 - rsi) / 30
                total_strength += strength
                reasons.append(f'RSI oversold ({rsi:.1f})')
            elif rsi > 70:  # Overbought
                signals.append(-1)
                strength = (rsi - 70) / 30
                total_strength += strength
                reasons.append(f'RSI overbought ({rsi:.1f})')
        
        # MACD analysis
        if macd:
            if macd > 0:
                signals.append(1)
                total_strength += min(abs(macd) * 0.1, 0.5)
                reasons.append(f'MACD bullish ({macd:.4f})')
            elif macd < 0:
                signals.append(-1)
                total_strength += min(abs(macd) * 0.1, 0.5)
                reasons.append(f'MACD bearish ({macd:.4f})')
        
        if not signals:
            return {'signal': 0, 'strength': 0, 'reason': 'No momentum data'}
        
        # Average signal
        avg_signal = sum(signals) / len(signals)
        final_signal = 1 if avg_signal > 0 else -1 if avg_signal < 0 else 0
        
        return {
            'signal': final_signal,
            'strength': min(total_strength / len(signals), 1.0),
            'reason': '; '.join(reasons)
        }
    
    def _analyze_volatility(self, market_conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze volatility using ATR"""
        atr = market_conditions.get('atr')
        volatility_percentile = market_conditions.get('volatility_percentile', 50)
        
        if not atr:
            return {'signal': 0, 'strength': 0, 'reason': 'No volatility data'}
        
        # High volatility reduces signal strength (more risk)
        # Low volatility increases signal strength (safer conditions)
        if volatility_percentile > 80:
            return {
                'signal': -1,  # Reduce trading in high volatility
                'strength': 0.8,
                'reason': f'High volatility (ATR: {atr:.2f}, percentile: {volatility_percentile})'
            }
        elif volatility_percentile < 20:
            return {
                'signal': 1,  # Favor trading in low volatility
                'strength': 0.6,
                'reason': f'Low volatility (ATR: {atr:.2f}, percentile: {volatility_percentile})'
            }
        else:
            return {
                'signal': 0,
                'strength': 0.3,
                'reason': f'Normal volatility (ATR: {atr:.2f})'
            }
    
    def _analyze_volume(self, market_conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze volume conditions"""
        volume_ratio = market_conditions.get('volume_ratio', 1.0)
        
        if volume_ratio > 1.5:
            return {
                'signal': 1,  # High volume supports signals
                'strength': min((volume_ratio - 1) * 0.5, 0.8),
                'reason': f'High volume ({volume_ratio:.1f}x average)'
            }
        elif volume_ratio < 0.5:
            return {
                'signal': -1,  # Low volume weakens signals
                'strength': 0.6,
                'reason': f'Low volume ({volume_ratio:.1f}x average)'
            }
        else:
            return {
                'signal': 0,
                'strength': 0.2,
                'reason': f'Normal volume ({volume_ratio:.1f}x average)'
            }
    
    def _combine_signals(self, trend, momentum, volatility, volume, market_quality_multiplier=1.0) -> Dict[str, Any]:
        """Combine all signal components into final signal with market quality adjustment"""
        
        # Weight the signals (enhanced weighting based on market quality)
        base_weights = {
            'trend': 0.4,
            'momentum': 0.3,
            'volatility': 0.2,
            'volume': 0.1
        }
        
        # Adjust weights based on market quality - higher quality markets get more aggressive weighting
        quality_factor = market_quality_multiplier
        weights = {
            'trend': base_weights['trend'] * (1 + quality_factor * 0.2),
            'momentum': base_weights['momentum'] * (1 + quality_factor * 0.1),
            'volatility': base_weights['volatility'] * (1 - quality_factor * 0.1),  # Less weight on volatility in good markets
            'volume': base_weights['volume'] * (1 + quality_factor * 0.1)
        }
        
        # Normalize weights
        total_weight = sum(weights.values())
        weights = {k: v/total_weight for k, v in weights.items()}
        
        # Calculate weighted signal
        weighted_signal = (
            trend['signal'] * weights['trend'] +
            momentum['signal'] * weights['momentum'] +
            volatility['signal'] * weights['volatility'] +
            volume['signal'] * weights['volume']
        )
        
        # Calculate combined strength
        combined_strength = (
            trend['strength'] * weights['trend'] +
            momentum['strength'] * weights['momentum'] +
            volatility['strength'] * weights['volatility'] +
            volume['strength'] * weights['volume']
        )
        
        # Adjust signal thresholds based on market quality
        buy_threshold = 0.3 - (quality_factor * 0.1)  # Lower threshold for better markets
        sell_threshold = -0.3 + (quality_factor * 0.1)
        min_strength_threshold = self.min_signal_strength - (quality_factor * 0.1)
        
        # Determine action
        if weighted_signal > buy_threshold and combined_strength >= min_strength_threshold:
            action = 'buy'
        elif weighted_signal < sell_threshold and combined_strength >= min_strength_threshold:
            action = 'sell'
        else:
            action = 'hold'
        
        # Compile reasons
        reasons = [
            trend['reason'],
            momentum['reason'],
            volatility['reason'],
            volume['reason']
        ]
        reasons = [r for r in reasons if r and 'No' not in r]
        
        return {
            'action': action,
            'strength': combined_strength,
            'confidence': min(combined_strength * 1.2, 1.0),
            'reasons': reasons,
            'weighted_signal': weighted_signal,
            'adjusted_thresholds': {
                'buy_threshold': buy_threshold,
                'sell_threshold': sell_threshold,
                'min_strength': min_strength_threshold
            }
        }
    
    def _calculate_levels(self, action: str, current_price: float) -> Dict[str, float]:
        """Calculate stop loss and take profit levels"""
        if action == 'buy':
            stop_loss = current_price * 0.98  # 2% stop loss
            take_profit = current_price * 1.04  # 4% take profit
        else:  # sell
            stop_loss = current_price * 1.02  # 2% stop loss
            take_profit = current_price * 0.96  # 4% take profit
        
        return {
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2)
        }
    
    def _no_signal(self, reason: str, market_filter_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """Return a no-signal response"""
        response = {
            'action': 'hold',
            'strength': 0.0,
            'confidence': 0.0,
            'reasons': [reason],
            'weighted_signal': 0.0
        }
        
        if market_filter_result:
            response['market_filter'] = market_filter_result
            response['market_grade'] = market_filter_result.get('market_grade', 'F')
            response['recommended_action'] = market_filter_result.get('recommended_action', 'AVOID')
        
        return response

# Convenience function for backward compatibility
def get_signal(symbol: str = "BTC-USDT") -> str:
    """Simple signal function that returns 'buy', 'sell', or 'hold'"""
    from market_analyzer import MarketAnalyzer
    
    analyzer = MarketAnalyzer()
    generator = SignalGenerator(analyzer)
    signal = generator.get_signal(symbol)
    
    return signal['action']
