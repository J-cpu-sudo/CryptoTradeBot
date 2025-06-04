import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
import json

class RiskLevel(Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"

class MarketCondition(Enum):
    BULL_MARKET = "bull_market"
    BEAR_MARKET = "bear_market"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"

@dataclass
class RiskMetrics:
    portfolio_risk: float
    market_risk: float
    volatility_risk: float
    correlation_risk: float
    liquidity_risk: float
    drawdown_risk: float
    overall_risk_score: float
    risk_level: RiskLevel
    recommended_position_size: float
    max_exposure: float

@dataclass
class MarketRiskAssessment:
    condition: MarketCondition
    volatility_percentile: float
    trend_strength: float
    market_stress_indicator: float
    fear_greed_index: float
    volume_analysis: Dict[str, float]
    correlation_matrix: Dict[str, float]
    timestamp: datetime

class RiskIntelligenceEngine:
    """Advanced risk intelligence with automated position sizing and exposure management"""
    
    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        # Risk parameters
        self.base_position_size = 0.02  # 2% base position size
        self.max_total_exposure = 0.20  # 20% maximum total exposure
        self.max_single_position = 0.05  # 5% maximum single position
        self.volatility_lookback = 30  # Days for volatility calculation
        self.correlation_threshold = 0.7  # High correlation threshold
        
        # Dynamic risk adjustment parameters
        self.risk_adjustment_factors = {
            'volatility_multiplier': 1.0,
            'trend_multiplier': 1.0,
            'correlation_multiplier': 1.0,
            'drawdown_multiplier': 1.0,
            'market_condition_multiplier': 1.0
        }
        
        # Historical data tracking
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.portfolio_history: List[Dict[str, Any]] = []
        self.risk_assessments: List[MarketRiskAssessment] = []
        
        # Current positions and exposure
        self.current_positions: Dict[str, Dict[str, Any]] = {}
        self.total_exposure = 0.0
        self.correlation_matrix = {}
        
        # Performance tracking
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0
        self.peak_capital = initial_capital
        self.risk_adjusted_returns = []
        
        # Thread safety
        self.lock = threading.Lock()
        
        logging.info(f"Risk Intelligence Engine initialized with ${initial_capital:,.2f}")
    
    def assess_market_risk(self, market_data: Dict[str, Any]) -> MarketRiskAssessment:
        """Comprehensive market risk assessment"""
        try:
            # Extract market data
            current_price = market_data.get('price', 0)
            volume_24h = market_data.get('volume_24h', 0)
            price_change_24h = market_data.get('price_change_24h', 0)
            
            # Calculate volatility
            volatility = self._calculate_market_volatility(market_data)
            volatility_percentile = self._calculate_volatility_percentile(volatility)
            
            # Assess trend strength
            trend_strength = self._assess_trend_strength(market_data)
            
            # Calculate market stress indicators
            market_stress = self._calculate_market_stress(market_data)
            
            # Estimate fear/greed index
            fear_greed = self._estimate_fear_greed_index(market_data)
            
            # Volume analysis
            volume_analysis = self._analyze_volume_patterns(market_data)
            
            # Update correlation matrix
            self._update_correlation_matrix(market_data)
            
            # Determine market condition
            market_condition = self._determine_market_condition(
                volatility, trend_strength, price_change_24h
            )
            
            assessment = MarketRiskAssessment(
                condition=market_condition,
                volatility_percentile=volatility_percentile,
                trend_strength=trend_strength,
                market_stress_indicator=market_stress,
                fear_greed_index=fear_greed,
                volume_analysis=volume_analysis,
                correlation_matrix=self.correlation_matrix.copy(),
                timestamp=datetime.utcnow()
            )
            
            # Store assessment
            self.risk_assessments.append(assessment)
            if len(self.risk_assessments) > 1000:
                self.risk_assessments = self.risk_assessments[-500:]
            
            return assessment
            
        except Exception as e:
            logging.error(f"Error assessing market risk: {e}")
            return self._create_default_risk_assessment()
    
    def calculate_portfolio_risk(self, positions: Dict[str, Dict[str, Any]]) -> RiskMetrics:
        """Calculate comprehensive portfolio risk metrics"""
        try:
            with self.lock:
                self.current_positions = positions.copy()
                
                # Calculate individual risk components
                portfolio_risk = self._calculate_portfolio_concentration_risk()
                market_risk = self._calculate_market_beta_risk()
                volatility_risk = self._calculate_volatility_risk()
                correlation_risk = self._calculate_correlation_risk()
                liquidity_risk = self._calculate_liquidity_risk()
                drawdown_risk = self._calculate_drawdown_risk()
                
                # Calculate overall risk score (0-1 scale)
                overall_risk_score = self._calculate_overall_risk_score(
                    portfolio_risk, market_risk, volatility_risk,
                    correlation_risk, liquidity_risk, drawdown_risk
                )
                
                # Determine risk level
                risk_level = self._determine_risk_level(overall_risk_score)
                
                # Calculate recommended position sizing
                recommended_size = self._calculate_recommended_position_size(overall_risk_score)
                max_exposure = self._calculate_max_exposure(overall_risk_score)
                
                return RiskMetrics(
                    portfolio_risk=portfolio_risk,
                    market_risk=market_risk,
                    volatility_risk=volatility_risk,
                    correlation_risk=correlation_risk,
                    liquidity_risk=liquidity_risk,
                    drawdown_risk=drawdown_risk,
                    overall_risk_score=overall_risk_score,
                    risk_level=risk_level,
                    recommended_position_size=recommended_size,
                    max_exposure=max_exposure
                )
                
        except Exception as e:
            logging.error(f"Error calculating portfolio risk: {e}")
            return self._create_default_risk_metrics()
    
    def adjust_position_size(self, base_size: float, symbol: str, 
                           market_assessment: MarketRiskAssessment,
                           portfolio_risk: RiskMetrics) -> float:
        """Dynamically adjust position size based on risk assessment"""
        try:
            adjusted_size = base_size
            
            # Market condition adjustment
            condition_multiplier = self._get_condition_multiplier(market_assessment.condition)
            adjusted_size *= condition_multiplier
            
            # Volatility adjustment
            if market_assessment.volatility_percentile > 80:
                adjusted_size *= 0.5  # Reduce size in high volatility
            elif market_assessment.volatility_percentile < 20:
                adjusted_size *= 1.2  # Increase size in low volatility
            
            # Trend strength adjustment
            if market_assessment.trend_strength > 0.8:
                adjusted_size *= 1.1  # Slightly increase for strong trends
            elif market_assessment.trend_strength < 0.3:
                adjusted_size *= 0.8  # Reduce for weak/choppy markets
            
            # Market stress adjustment
            if market_assessment.market_stress_indicator > 0.7:
                adjusted_size *= 0.6  # Significant reduction under stress
            
            # Portfolio risk adjustment
            if portfolio_risk.overall_risk_score > 0.7:
                adjusted_size *= 0.7  # Reduce when portfolio risk is high
            elif portfolio_risk.overall_risk_score < 0.3:
                adjusted_size *= 1.1  # Slightly increase when risk is low
            
            # Drawdown adjustment
            if self.current_drawdown > 0.10:  # 10% drawdown
                adjusted_size *= max(0.3, 1 - (self.current_drawdown * 2))
            
            # Correlation adjustment (reduce if highly correlated with existing positions)
            correlation_penalty = self._calculate_correlation_penalty(symbol)
            adjusted_size *= (1 - correlation_penalty)
            
            # Apply absolute limits
            adjusted_size = min(adjusted_size, self.max_single_position)
            adjusted_size = max(adjusted_size, 0.001)  # Minimum 0.1%
            
            # Check total exposure limit
            if self.total_exposure + adjusted_size > portfolio_risk.max_exposure:
                adjusted_size = max(0, portfolio_risk.max_exposure - self.total_exposure)
            
            logging.info(f"Position size adjusted: {base_size:.3f} → {adjusted_size:.3f} for {symbol}")
            
            return adjusted_size
            
        except Exception as e:
            logging.error(f"Error adjusting position size: {e}")
            return base_size * 0.5  # Conservative fallback
    
    def should_reduce_exposure(self, current_conditions: MarketRiskAssessment) -> Tuple[bool, str]:
        """Determine if exposure should be reduced based on market conditions"""
        try:
            reasons = []
            
            # Check volatility spike
            if current_conditions.volatility_percentile > 90:
                reasons.append("Extreme volatility detected")
            
            # Check market stress
            if current_conditions.market_stress_indicator > 0.8:
                reasons.append("High market stress")
            
            # Check fear/greed extremes
            if current_conditions.fear_greed_index < 10 or current_conditions.fear_greed_index > 90:
                reasons.append("Extreme market sentiment")
            
            # Check for bear market conditions
            if current_conditions.condition == MarketCondition.BEAR_MARKET:
                reasons.append("Bear market conditions")
            
            # Check current drawdown
            if self.current_drawdown > 0.15:  # 15% drawdown
                reasons.append(f"High drawdown: {self.current_drawdown:.1%}")
            
            # Check correlation risk
            if len(self.current_positions) > 1:
                avg_correlation = np.mean(list(self.correlation_matrix.values()))
                if avg_correlation > self.correlation_threshold:
                    reasons.append("High portfolio correlation")
            
            should_reduce = len(reasons) >= 2  # Require multiple risk factors
            
            return should_reduce, "; ".join(reasons)
            
        except Exception as e:
            logging.error(f"Error checking exposure reduction: {e}")
            return False, ""
    
    def update_portfolio_performance(self, new_capital: float):
        """Update portfolio performance and risk metrics"""
        try:
            with self.lock:
                old_capital = self.current_capital
                self.current_capital = new_capital
                
                # Update peak capital
                if new_capital > self.peak_capital:
                    self.peak_capital = new_capital
                
                # Update drawdown
                self.current_drawdown = (self.peak_capital - new_capital) / self.peak_capital
                self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
                
                # Calculate return
                if old_capital > 0:
                    period_return = (new_capital - old_capital) / old_capital
                    self.risk_adjusted_returns.append({
                        'timestamp': datetime.utcnow(),
                        'return': period_return,
                        'capital': new_capital,
                        'drawdown': self.current_drawdown
                    })
                
                # Store portfolio snapshot
                self.portfolio_history.append({
                    'timestamp': datetime.utcnow(),
                    'capital': new_capital,
                    'positions': self.current_positions.copy(),
                    'total_exposure': self.total_exposure,
                    'drawdown': self.current_drawdown
                })
                
                # Limit history size
                if len(self.portfolio_history) > 1000:
                    self.portfolio_history = self.portfolio_history[-500:]
                
                if len(self.risk_adjusted_returns) > 1000:
                    self.risk_adjusted_returns = self.risk_adjusted_returns[-500:]
                
        except Exception as e:
            logging.error(f"Error updating portfolio performance: {e}")
    
    def _calculate_market_volatility(self, market_data: Dict[str, Any]) -> float:
        """Calculate current market volatility"""
        try:
            # Use price change data to estimate volatility
            price_change = abs(market_data.get('price_change_24h', 0))
            current_price = market_data.get('price', 1)
            
            if current_price > 0:
                volatility = price_change / current_price
            else:
                volatility = 0.02  # Default 2%
            
            return min(volatility, 0.5)  # Cap at 50%
            
        except:
            return 0.02  # Default volatility
    
    def _calculate_volatility_percentile(self, current_volatility: float) -> float:
        """Calculate volatility percentile based on historical data"""
        try:
            # Simulate historical volatility data
            historical_volatilities = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.07, 0.1, 0.15]
            
            percentile = sum(1 for v in historical_volatilities if v <= current_volatility) / len(historical_volatilities)
            return percentile * 100
            
        except:
            return 50.0  # Default 50th percentile
    
    def _assess_trend_strength(self, market_data: Dict[str, Any]) -> float:
        """Assess current trend strength"""
        try:
            price_change_24h = market_data.get('price_change_24h', 0)
            price_change_7d = market_data.get('price_change_7d', price_change_24h * 3)
            
            # Normalize trend strength
            trend_strength = abs(price_change_7d) / 100  # Assume percentage change
            return min(trend_strength, 1.0)
            
        except:
            return 0.5  # Default moderate trend
    
    def _calculate_market_stress(self, market_data: Dict[str, Any]) -> float:
        """Calculate market stress indicator"""
        try:
            volatility = self._calculate_market_volatility(market_data)
            volume_change = market_data.get('volume_change_24h', 0)
            
            # Market stress increases with volatility and unusual volume
            stress_score = (volatility * 2) + (abs(volume_change) / 100)
            return min(stress_score, 1.0)
            
        except:
            return 0.3  # Default moderate stress
    
    def _estimate_fear_greed_index(self, market_data: Dict[str, Any]) -> float:
        """Estimate fear/greed index from available data"""
        try:
            price_change = market_data.get('price_change_24h', 0)
            volatility = self._calculate_market_volatility(market_data)
            
            # Simple fear/greed estimation
            if price_change > 5:
                base_index = 70  # Greed
            elif price_change < -5:
                base_index = 30  # Fear
            else:
                base_index = 50  # Neutral
            
            # Adjust for volatility
            if volatility > 0.05:
                base_index -= 10  # High volatility = more fear
            
            return max(0, min(100, base_index))
            
        except:
            return 50.0  # Default neutral
    
    def _analyze_volume_patterns(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Analyze volume patterns for risk assessment"""
        try:
            volume_24h = market_data.get('volume_24h', 0)
            volume_change = market_data.get('volume_change_24h', 0)
            
            return {
                'volume_24h': volume_24h,
                'volume_change_pct': volume_change,
                'volume_spike': 1 if abs(volume_change) > 50 else 0,
                'liquidity_score': min(volume_24h / 1000000, 1.0)  # Normalize by $1M
            }
            
        except:
            return {'volume_24h': 0, 'volume_change_pct': 0, 'volume_spike': 0, 'liquidity_score': 0.5}
    
    def _update_correlation_matrix(self, market_data: Dict[str, Any]):
        """Update correlation matrix with new market data"""
        try:
            symbol = market_data.get('symbol', 'BTC-USDT')
            price = market_data.get('price', 0)
            
            # Store price data
            if symbol not in self.price_history:
                self.price_history[symbol] = []
            
            self.price_history[symbol].append((datetime.utcnow(), price))
            
            # Keep only recent data
            cutoff_time = datetime.utcnow() - timedelta(days=self.volatility_lookback)
            self.price_history[symbol] = [
                (ts, p) for ts, p in self.price_history[symbol] if ts > cutoff_time
            ]
            
            # Calculate correlations (simplified)
            if len(self.price_history) >= 2:
                symbols = list(self.price_history.keys())
                for i, sym1 in enumerate(symbols):
                    for sym2 in symbols[i+1:]:
                        correlation = self._calculate_price_correlation(sym1, sym2)
                        self.correlation_matrix[f"{sym1}_{sym2}"] = correlation
            
        except Exception as e:
            logging.error(f"Error updating correlation matrix: {e}")
    
    def _calculate_price_correlation(self, symbol1: str, symbol2: str) -> float:
        """Calculate price correlation between two symbols"""
        try:
            prices1 = [p for _, p in self.price_history.get(symbol1, [])]
            prices2 = [p for _, p in self.price_history.get(symbol2, [])]
            
            if len(prices1) < 10 or len(prices2) < 10:
                return 0.5  # Default moderate correlation
            
            # Calculate returns
            returns1 = [(prices1[i] - prices1[i-1]) / prices1[i-1] for i in range(1, len(prices1))]
            returns2 = [(prices2[i] - prices2[i-1]) / prices2[i-1] for i in range(1, len(prices2))]
            
            # Take minimum length
            min_len = min(len(returns1), len(returns2))
            returns1 = returns1[:min_len]
            returns2 = returns2[:min_len]
            
            if min_len < 5:
                return 0.5
            
            # Calculate correlation
            correlation = np.corrcoef(returns1, returns2)[0, 1]
            return correlation if not np.isnan(correlation) else 0.5
            
        except:
            return 0.5
    
    def _determine_market_condition(self, volatility: float, trend_strength: float, 
                                  price_change: float) -> MarketCondition:
        """Determine current market condition"""
        try:
            if volatility > 0.08:
                return MarketCondition.HIGH_VOLATILITY
            elif volatility < 0.02:
                return MarketCondition.LOW_VOLATILITY
            elif price_change > 5 and trend_strength > 0.6:
                return MarketCondition.BULL_MARKET
            elif price_change < -5 and trend_strength > 0.6:
                return MarketCondition.BEAR_MARKET
            else:
                return MarketCondition.SIDEWAYS
                
        except:
            return MarketCondition.SIDEWAYS
    
    def _calculate_portfolio_concentration_risk(self) -> float:
        """Calculate portfolio concentration risk"""
        try:
            if not self.current_positions:
                return 0.0
            
            position_sizes = [pos.get('size', 0) for pos in self.current_positions.values()]
            total_size = sum(position_sizes)
            
            if total_size == 0:
                return 0.0
            
            # Calculate Herfindahl index for concentration
            weights = [size / total_size for size in position_sizes]
            herfindahl_index = sum(w**2 for w in weights)
            
            # Convert to risk score (higher concentration = higher risk)
            concentration_risk = (herfindahl_index - (1/len(weights))) / (1 - (1/len(weights)))
            return max(0, min(1, concentration_risk))
            
        except:
            return 0.5
    
    def _calculate_market_beta_risk(self) -> float:
        """Calculate market beta risk"""
        try:
            # Simplified beta calculation
            if len(self.risk_adjusted_returns) < 10:
                return 0.5  # Default moderate market risk
            
            portfolio_returns = [r['return'] for r in self.risk_adjusted_returns[-20:]]
            market_returns = [r * 0.8 for r in portfolio_returns]  # Simulate market returns
            
            if len(portfolio_returns) < 5:
                return 0.5
            
            portfolio_var = np.var(portfolio_returns)
            market_var = np.var(market_returns)
            covariance = np.cov(portfolio_returns, market_returns)[0, 1]
            
            if market_var > 0:
                beta = covariance / market_var
                # Convert beta to risk score
                beta_risk = abs(beta - 1) / 2  # Distance from market beta of 1
                return min(beta_risk, 1.0)
            
            return 0.5
            
        except:
            return 0.5
    
    def _calculate_volatility_risk(self) -> float:
        """Calculate portfolio volatility risk"""
        try:
            if len(self.risk_adjusted_returns) < 5:
                return 0.3
            
            returns = [r['return'] for r in self.risk_adjusted_returns[-20:]]
            volatility = np.std(returns) * np.sqrt(252)  # Annualized volatility
            
            # Normalize volatility to risk score
            risk_score = min(volatility / 0.5, 1.0)  # 50% volatility = maximum risk
            return risk_score
            
        except:
            return 0.3
    
    def _calculate_correlation_risk(self) -> float:
        """Calculate correlation risk from position correlations"""
        try:
            if not self.correlation_matrix:
                return 0.2
            
            correlations = list(self.correlation_matrix.values())
            avg_correlation = np.mean([abs(c) for c in correlations])
            
            # High correlation = high risk
            risk_score = avg_correlation
            return min(risk_score, 1.0)
            
        except:
            return 0.2
    
    def _calculate_liquidity_risk(self) -> float:
        """Calculate liquidity risk"""
        try:
            # Simplified liquidity risk based on position sizes
            if not self.current_positions:
                return 0.1
            
            large_positions = sum(1 for pos in self.current_positions.values() 
                                if pos.get('size', 0) > 0.03)
            
            liquidity_risk = large_positions / len(self.current_positions)
            return liquidity_risk
            
        except:
            return 0.1
    
    def _calculate_drawdown_risk(self) -> float:
        """Calculate drawdown-based risk"""
        try:
            # Current drawdown contributes to risk
            drawdown_risk = self.current_drawdown * 2  # Double weight on drawdown
            
            # Add historical drawdown patterns
            if len(self.portfolio_history) > 10:
                recent_drawdowns = [h['drawdown'] for h in self.portfolio_history[-10:]]
                avg_recent_drawdown = np.mean(recent_drawdowns)
                drawdown_risk += avg_recent_drawdown
            
            return min(drawdown_risk, 1.0)
            
        except:
            return self.current_drawdown
    
    def _calculate_overall_risk_score(self, portfolio_risk: float, market_risk: float,
                                    volatility_risk: float, correlation_risk: float,
                                    liquidity_risk: float, drawdown_risk: float) -> float:
        """Calculate weighted overall risk score"""
        try:
            weights = {
                'portfolio': 0.20,
                'market': 0.15,
                'volatility': 0.25,
                'correlation': 0.15,
                'liquidity': 0.10,
                'drawdown': 0.15
            }
            
            overall_score = (
                portfolio_risk * weights['portfolio'] +
                market_risk * weights['market'] +
                volatility_risk * weights['volatility'] +
                correlation_risk * weights['correlation'] +
                liquidity_risk * weights['liquidity'] +
                drawdown_risk * weights['drawdown']
            )
            
            return min(overall_score, 1.0)
            
        except:
            return 0.5
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Determine risk level from score"""
        if risk_score < 0.2:
            return RiskLevel.VERY_LOW
        elif risk_score < 0.4:
            return RiskLevel.LOW
        elif risk_score < 0.6:
            return RiskLevel.MODERATE
        elif risk_score < 0.8:
            return RiskLevel.HIGH
        else:
            return RiskLevel.EXTREME
    
    def _calculate_recommended_position_size(self, risk_score: float) -> float:
        """Calculate recommended position size based on risk"""
        try:
            # Inverse relationship with risk
            risk_multiplier = max(0.2, 1 - risk_score)
            recommended_size = self.base_position_size * risk_multiplier
            
            return min(recommended_size, self.max_single_position)
            
        except:
            return self.base_position_size * 0.5
    
    def _calculate_max_exposure(self, risk_score: float) -> float:
        """Calculate maximum allowed exposure based on risk"""
        try:
            # Reduce max exposure as risk increases
            risk_multiplier = max(0.3, 1 - (risk_score * 0.5))
            max_exposure = self.max_total_exposure * risk_multiplier
            
            return max(0.05, max_exposure)  # Minimum 5% exposure
            
        except:
            return self.max_total_exposure * 0.5
    
    def _get_condition_multiplier(self, condition: MarketCondition) -> float:
        """Get position size multiplier for market condition"""
        multipliers = {
            MarketCondition.BULL_MARKET: 1.1,
            MarketCondition.BEAR_MARKET: 0.6,
            MarketCondition.SIDEWAYS: 0.9,
            MarketCondition.HIGH_VOLATILITY: 0.5,
            MarketCondition.LOW_VOLATILITY: 1.2
        }
        return multipliers.get(condition, 1.0)
    
    def _calculate_correlation_penalty(self, symbol: str) -> float:
        """Calculate correlation penalty for new position"""
        try:
            if not self.current_positions or not self.correlation_matrix:
                return 0.0
            
            max_correlation = 0.0
            for existing_symbol in self.current_positions.keys():
                correlation_key = f"{symbol}_{existing_symbol}"
                reverse_key = f"{existing_symbol}_{symbol}"
                
                correlation = self.correlation_matrix.get(correlation_key, 
                            self.correlation_matrix.get(reverse_key, 0.0))
                max_correlation = max(max_correlation, abs(correlation))
            
            # Penalty increases with correlation
            if max_correlation > self.correlation_threshold:
                return (max_correlation - self.correlation_threshold) * 0.5
            
            return 0.0
            
        except:
            return 0.0
    
    def _create_default_risk_assessment(self) -> MarketRiskAssessment:
        """Create default risk assessment when calculation fails"""
        return MarketRiskAssessment(
            condition=MarketCondition.SIDEWAYS,
            volatility_percentile=50.0,
            trend_strength=0.5,
            market_stress_indicator=0.3,
            fear_greed_index=50.0,
            volume_analysis={'volume_24h': 0, 'volume_change_pct': 0, 'liquidity_score': 0.5},
            correlation_matrix={},
            timestamp=datetime.utcnow()
        )
    
    def _create_default_risk_metrics(self) -> RiskMetrics:
        """Create default risk metrics when calculation fails"""
        return RiskMetrics(
            portfolio_risk=0.5,
            market_risk=0.5,
            volatility_risk=0.5,
            correlation_risk=0.3,
            liquidity_risk=0.3,
            drawdown_risk=self.current_drawdown,
            overall_risk_score=0.5,
            risk_level=RiskLevel.MODERATE,
            recommended_position_size=self.base_position_size * 0.5,
            max_exposure=self.max_total_exposure * 0.5
        )
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary"""
        try:
            with self.lock:
                return {
                    'current_capital': self.current_capital,
                    'peak_capital': self.peak_capital,
                    'current_drawdown': self.current_drawdown,
                    'max_drawdown': self.max_drawdown,
                    'total_exposure': self.total_exposure,
                    'position_count': len(self.current_positions),
                    'correlation_summary': {
                        'avg_correlation': np.mean(list(self.correlation_matrix.values())) if self.correlation_matrix else 0,
                        'max_correlation': max(self.correlation_matrix.values()) if self.correlation_matrix else 0,
                        'correlation_pairs': len(self.correlation_matrix)
                    },
                    'recent_performance': {
                        'total_return': (self.current_capital - self.initial_capital) / self.initial_capital,
                        'recent_volatility': np.std([r['return'] for r in self.risk_adjusted_returns[-20:]]) if len(self.risk_adjusted_returns) >= 5 else 0
                    },
                    'risk_parameters': {
                        'base_position_size': self.base_position_size,
                        'max_single_position': self.max_single_position,
                        'max_total_exposure': self.max_total_exposure,
                        'correlation_threshold': self.correlation_threshold
                    }
                }
                
        except Exception as e:
            logging.error(f"Error getting risk summary: {e}")
            return {'error': str(e)}
    
    def export_risk_data(self) -> Dict[str, Any]:
        """Export comprehensive risk intelligence data"""
        try:
            with self.lock:
                return {
                    'export_timestamp': datetime.utcnow().isoformat(),
                    'risk_summary': self.get_risk_summary(),
                    'recent_assessments': [
                        {
                            'condition': assessment.condition.value,
                            'volatility_percentile': assessment.volatility_percentile,
                            'market_stress': assessment.market_stress_indicator,
                            'timestamp': assessment.timestamp.isoformat()
                        }
                        for assessment in self.risk_assessments[-10:]
                    ],
                    'correlation_matrix': self.correlation_matrix,
                    'portfolio_history': self.portfolio_history[-20:],
                    'risk_adjusted_returns': self.risk_adjusted_returns[-20:]
                }
                
        except Exception as e:
            logging.error(f"Error exporting risk data: {e}")
            return {'error': str(e)}