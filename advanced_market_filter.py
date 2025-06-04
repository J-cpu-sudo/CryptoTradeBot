import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from market_analyzer import MarketAnalyzer

class AdvancedMarketFilter:
    """Advanced market condition filtering to avoid poor trading environments"""
    
    def __init__(self, market_analyzer: MarketAnalyzer):
        self.market_analyzer = market_analyzer
        self.min_volume_ratio = 0.5  # Minimum volume ratio vs average
        self.max_volatility_percentile = 85  # Max volatility percentile
        self.min_liquidity_score = 0.6  # Minimum liquidity score
        
    def is_market_favorable(self, symbol: str = "BTC-USDT") -> Dict[str, Any]:
        """
        Comprehensive market condition analysis to determine if conditions are favorable for trading
        
        Returns:
            Dictionary with favorable status and detailed analysis
        """
        try:
            # Get market analysis
            analysis = self.market_analyzer.analyze_market(symbol)
            if not analysis:
                return self._create_unfavorable_response("Failed to get market analysis")
            
            indicators = analysis.get('indicators', {})
            market_conditions = analysis.get('market_conditions', {})
            current_price = analysis.get('current_price', 0)
            
            # Initialize filter results
            filter_results = {
                'volume_check': self._check_volume_conditions(market_conditions),
                'volatility_check': self._check_volatility_conditions(market_conditions, indicators),
                'liquidity_check': self._check_liquidity_conditions(market_conditions, current_price),
                'trend_clarity_check': self._check_trend_clarity(indicators),
                'price_action_check': self._check_price_action_quality(indicators, market_conditions),
                'market_structure_check': self._check_market_structure(indicators),
                'risk_environment_check': self._check_risk_environment(market_conditions)
            }
            
            # Calculate overall score
            passed_checks = sum(1 for check in filter_results.values() if check['passed'])
            total_checks = len(filter_results)
            overall_score = passed_checks / total_checks
            
            # Determine if market is favorable (need at least 70% of checks to pass)
            is_favorable = overall_score >= 0.7
            
            # Compile reasons
            reasons = []
            for check_name, check_result in filter_results.items():
                if check_result['passed']:
                    reasons.append(f"✓ {check_result['reason']}")
                else:
                    reasons.append(f"✗ {check_result['reason']}")
            
            return {
                'favorable': is_favorable,
                'overall_score': round(overall_score, 2),
                'passed_checks': passed_checks,
                'total_checks': total_checks,
                'reasons': reasons,
                'filter_results': filter_results,
                'market_grade': self._get_market_grade(overall_score),
                'recommended_action': self._get_recommended_action(overall_score, filter_results)
            }
            
        except Exception as e:
            logging.error(f"Error in market filter analysis: {e}")
            return self._create_unfavorable_response(f"Analysis error: {str(e)}")
    
    def _check_volume_conditions(self, market_conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Check if volume conditions are favorable"""
        volume_ratio = market_conditions.get('volume_ratio', 0)
        
        if volume_ratio >= self.min_volume_ratio:
            if volume_ratio >= 1.5:
                return {'passed': True, 'reason': f'High volume activity ({volume_ratio:.1f}x average)'}
            else:
                return {'passed': True, 'reason': f'Adequate volume ({volume_ratio:.1f}x average)'}
        else:
            return {'passed': False, 'reason': f'Low volume ({volume_ratio:.1f}x average, need ≥{self.min_volume_ratio}x)'}
    
    def _check_volatility_conditions(self, market_conditions: Dict[str, Any], indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Check if volatility is within acceptable range"""
        volatility_percentile = market_conditions.get('volatility_percentile', 50)
        atr = indicators.get('atr', 0)
        current_price = indicators.get('current_price', 0)
        
        # Calculate ATR as percentage of price
        atr_percent = (atr / current_price * 100) if current_price > 0 else 0
        
        if volatility_percentile <= self.max_volatility_percentile:
            if volatility_percentile <= 20:
                return {'passed': True, 'reason': f'Low volatility environment ({volatility_percentile:.0f}th percentile, ATR: {atr_percent:.1f}%)'}
            else:
                return {'passed': True, 'reason': f'Moderate volatility ({volatility_percentile:.0f}th percentile, ATR: {atr_percent:.1f}%)'}
        else:
            return {'passed': False, 'reason': f'Excessive volatility ({volatility_percentile:.0f}th percentile, ATR: {atr_percent:.1f}%)'}
    
    def _check_liquidity_conditions(self, market_conditions: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """Check market liquidity conditions"""
        volume_ratio = market_conditions.get('volume_ratio', 0)
        volatility = market_conditions.get('current_volatility', 0)
        
        # Simple liquidity score based on volume and inverse volatility
        if volume_ratio > 0 and volatility > 0:
            liquidity_score = min(volume_ratio / (1 + volatility/100), 1.0)
        else:
            liquidity_score = 0
        
        if liquidity_score >= self.min_liquidity_score:
            return {'passed': True, 'reason': f'Good liquidity conditions (score: {liquidity_score:.2f})'}
        else:
            return {'passed': False, 'reason': f'Poor liquidity conditions (score: {liquidity_score:.2f}, need ≥{self.min_liquidity_score})'}
    
    def _check_trend_clarity(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Check if market trend is clear and not choppy"""
        ema_12 = indicators.get('ema_12', 0)
        ema_26 = indicators.get('ema_26', 0)
        current_price = indicators.get('current_price', 0)
        
        if not all([ema_12, ema_26, current_price]):
            return {'passed': False, 'reason': 'Insufficient data for trend analysis'}
        
        # Calculate EMA separation as percentage
        ema_separation = abs(ema_12 - ema_26) / current_price * 100
        
        # Check if EMAs are sufficiently separated (indicating clear trend)
        min_separation = 0.5  # 0.5% minimum separation
        
        if ema_separation >= min_separation:
            direction = "uptrend" if ema_12 > ema_26 else "downtrend"
            return {'passed': True, 'reason': f'Clear {direction} (EMA separation: {ema_separation:.2f}%)'}
        else:
            return {'passed': False, 'reason': f'Choppy/sideways market (EMA separation: {ema_separation:.2f}%, need ≥{min_separation}%)'}
    
    def _check_price_action_quality(self, indicators: Dict[str, Any], market_conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Check quality of price action"""
        rsi = indicators.get('rsi', 50)
        price_change_24h = indicators.get('price_change_24h', 0)
        
        # Check for extreme RSI conditions that might indicate poor entry timing
        if rsi < 20 or rsi > 80:
            return {'passed': False, 'reason': f'Extreme RSI condition ({rsi:.1f}) - poor entry timing'}
        
        # Check for excessive 24h price movement
        if abs(price_change_24h) > 10:
            return {'passed': False, 'reason': f'Excessive 24h movement ({price_change_24h:.1f}%) - high risk environment'}
        
        # Check for healthy price action
        if 30 <= rsi <= 70 and abs(price_change_24h) <= 5:
            return {'passed': True, 'reason': f'Healthy price action (RSI: {rsi:.1f}, 24h: {price_change_24h:.1f}%)'}
        else:
            return {'passed': True, 'reason': f'Acceptable price action (RSI: {rsi:.1f}, 24h: {price_change_24h:.1f}%)'}
    
    def _check_market_structure(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Check overall market structure health"""
        ema_12 = indicators.get('ema_12', 0)
        ema_26 = indicators.get('ema_26', 0)
        current_price = indicators.get('current_price', 0)
        macd = indicators.get('macd', 0)
        
        if not current_price:
            return {'passed': False, 'reason': 'Insufficient price data'}
        
        # Check if price is not too far from EMAs (indicating structure breakdown)
        if ema_12 and ema_26:
            avg_ema = (ema_12 + ema_26) / 2
            price_deviation = abs(current_price - avg_ema) / avg_ema * 100
            
            if price_deviation > 5:  # More than 5% deviation from EMAs
                return {'passed': False, 'reason': f'Price too far from EMAs ({price_deviation:.1f}% deviation)'}
        
        # Check MACD for momentum confirmation
        if macd is not None and abs(macd) > 0.001:  # MACD showing some momentum
            return {'passed': True, 'reason': f'Good market structure with momentum (MACD: {macd:.4f})'}
        else:
            return {'passed': True, 'reason': 'Acceptable market structure'}
    
    def _check_risk_environment(self, market_conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Check overall risk environment"""
        volatility_percentile = market_conditions.get('volatility_percentile', 50)
        volume_ratio = market_conditions.get('volume_ratio', 1)
        
        # Calculate risk score (lower is better)
        risk_score = (volatility_percentile / 100) * (1 / max(volume_ratio, 0.1))
        
        if risk_score <= 0.5:
            return {'passed': True, 'reason': f'Low risk environment (risk score: {risk_score:.2f})'}
        elif risk_score <= 1.0:
            return {'passed': True, 'reason': f'Moderate risk environment (risk score: {risk_score:.2f})'}
        else:
            return {'passed': False, 'reason': f'High risk environment (risk score: {risk_score:.2f})'}
    
    def _get_market_grade(self, score: float) -> str:
        """Get letter grade for market conditions"""
        if score >= 0.9:
            return 'A+'
        elif score >= 0.8:
            return 'A'
        elif score >= 0.7:
            return 'B'
        elif score >= 0.6:
            return 'C'
        elif score >= 0.5:
            return 'D'
        else:
            return 'F'
    
    def _get_recommended_action(self, score: float, filter_results: Dict[str, Any]) -> str:
        """Get recommended action based on market conditions"""
        if score >= 0.8:
            return 'TRADE - Excellent conditions'
        elif score >= 0.7:
            return 'TRADE - Good conditions'
        elif score >= 0.6:
            return 'CAUTION - Marginal conditions, reduce position size'
        elif score >= 0.5:
            return 'WAIT - Poor conditions, wait for improvement'
        else:
            return 'AVOID - Unfavorable conditions, do not trade'
    
    def _create_unfavorable_response(self, reason: str) -> Dict[str, Any]:
        """Create standard unfavorable market response"""
        return {
            'favorable': False,
            'overall_score': 0.0,
            'passed_checks': 0,
            'total_checks': 0,
            'reasons': [f"✗ {reason}"],
            'filter_results': {},
            'market_grade': 'F',
            'recommended_action': 'AVOID - Analysis failed'
        }
    
    def get_market_session_info(self) -> Dict[str, Any]:
        """Get information about current market session"""
        now = datetime.utcnow()
        
        # Simplified market session detection (crypto markets are 24/7 but have patterns)
        hour = now.hour
        
        if 0 <= hour < 6:
            session = "Asian Late/European Pre"
            activity_level = "Low"
        elif 6 <= hour < 12:
            session = "European"
            activity_level = "Medium-High"
        elif 12 <= hour < 18:
            session = "European/US Overlap"
            activity_level = "High"
        elif 18 <= hour < 24:
            session = "US/Asian Pre"
            activity_level = "Medium"
        else:
            session = "Unknown"
            activity_level = "Unknown"
        
        return {
            'current_session': session,
            'activity_level': activity_level,
            'utc_hour': hour,
            'recommended_for_trading': activity_level in ['Medium-High', 'High']
        }
    
    def update_filter_parameters(self, **kwargs) -> bool:
        """Update filter parameters dynamically"""
        try:
            if 'min_volume_ratio' in kwargs:
                self.min_volume_ratio = float(kwargs['min_volume_ratio'])
            if 'max_volatility_percentile' in kwargs:
                self.max_volatility_percentile = float(kwargs['max_volatility_percentile'])
            if 'min_liquidity_score' in kwargs:
                self.min_liquidity_score = float(kwargs['min_liquidity_score'])
            
            logging.info(f"Market filter parameters updated: {kwargs}")
            return True
        except Exception as e:
            logging.error(f"Error updating filter parameters: {e}")
            return False