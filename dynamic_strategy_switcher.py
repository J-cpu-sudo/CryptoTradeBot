import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import threading

class MarketRegime(Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"

class StrategyType(Enum):
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    SCALPING = "scalping"
    MOMENTUM = "momentum"
    DEFENSIVE = "defensive"

@dataclass
class MarketAnalysis:
    regime: MarketRegime
    confidence: float
    volatility: float
    trend_strength: float
    volume_profile: str
    support_resistance: Dict[str, float]
    recommended_strategy: StrategyType
    analysis_timestamp: datetime

@dataclass
class StrategyConfig:
    strategy_type: StrategyType
    parameters: Dict[str, Any]
    market_regimes: List[MarketRegime]
    min_confidence: float
    performance_weight: float
    active: bool

class DynamicStrategySwitcher:
    """Intelligent strategy switching based on market regime detection"""
    
    def __init__(self):
        self.current_strategy: Optional[StrategyType] = None
        self.strategy_configs: Dict[StrategyType, StrategyConfig] = {}
        self.market_history: List[MarketAnalysis] = []
        self.strategy_performance: Dict[StrategyType, Dict[str, float]] = {}
        
        # Market analysis parameters
        self.analysis_window = 50  # Number of periods for analysis
        self.regime_stability_threshold = 0.7
        self.strategy_switch_cooldown = timedelta(minutes=30)
        self.last_strategy_switch = None
        
        # Performance tracking
        self.strategy_trade_history: Dict[StrategyType, List[Dict[str, Any]]] = {}
        self.regime_accuracy: Dict[MarketRegime, float] = {}
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Initialize default strategies
        self._initialize_default_strategies()
        
        logging.info("Dynamic strategy switcher initialized")
    
    def _initialize_default_strategies(self):
        """Initialize default strategy configurations"""
        
        # Trend Following Strategy
        self.strategy_configs[StrategyType.TREND_FOLLOWING] = StrategyConfig(
            strategy_type=StrategyType.TREND_FOLLOWING,
            parameters={
                'ema_fast': 12,
                'ema_slow': 26,
                'trend_strength_threshold': 0.6,
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.04,
                'trailing_stop': True,
                'position_size_multiplier': 1.0
            },
            market_regimes=[MarketRegime.TRENDING],
            min_confidence=0.7,
            performance_weight=1.0,
            active=True
        )
        
        # Mean Reversion Strategy
        self.strategy_configs[StrategyType.MEAN_REVERSION] = StrategyConfig(
            strategy_type=StrategyType.MEAN_REVERSION,
            parameters={
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'bollinger_period': 20,
                'bollinger_std': 2,
                'stop_loss_pct': 0.015,
                'take_profit_pct': 0.025,
                'trailing_stop': False,
                'position_size_multiplier': 0.8
            },
            market_regimes=[MarketRegime.RANGING],
            min_confidence=0.6,
            performance_weight=1.0,
            active=True
        )
        
        # Breakout Strategy
        self.strategy_configs[StrategyType.BREAKOUT] = StrategyConfig(
            strategy_type=StrategyType.BREAKOUT,
            parameters={
                'lookback_period': 20,
                'breakout_threshold': 0.02,
                'volume_confirmation': True,
                'min_volume_ratio': 1.5,
                'stop_loss_pct': 0.025,
                'take_profit_pct': 0.05,
                'trailing_stop': True,
                'position_size_multiplier': 1.2
            },
            market_regimes=[MarketRegime.BREAKOUT, MarketRegime.VOLATILE],
            min_confidence=0.8,
            performance_weight=1.0,
            active=True
        )
        
        # Scalping Strategy
        self.strategy_configs[StrategyType.SCALPING] = StrategyConfig(
            strategy_type=StrategyType.SCALPING,
            parameters={
                'timeframe_minutes': 1,
                'quick_profit_target': 0.005,
                'quick_stop_loss': 0.003,
                'max_trade_duration': 15,
                'volume_threshold': 2.0,
                'spread_threshold': 0.001,
                'position_size_multiplier': 0.5
            },
            market_regimes=[MarketRegime.LOW_VOLATILITY],
            min_confidence=0.5,
            performance_weight=0.8,
            active=True
        )
        
        # Momentum Strategy
        self.strategy_configs[StrategyType.MOMENTUM] = StrategyConfig(
            strategy_type=StrategyType.MOMENTUM,
            parameters={
                'momentum_period': 10,
                'momentum_threshold': 0.01,
                'rsi_momentum_threshold': 60,
                'volume_momentum': True,
                'stop_loss_pct': 0.03,
                'take_profit_pct': 0.06,
                'trailing_stop': True,
                'position_size_multiplier': 1.1
            },
            market_regimes=[MarketRegime.TRENDING, MarketRegime.BREAKOUT],
            min_confidence=0.75,
            performance_weight=1.0,
            active=True
        )
        
        # Defensive Strategy
        self.strategy_configs[StrategyType.DEFENSIVE] = StrategyConfig(
            strategy_type=StrategyType.DEFENSIVE,
            parameters={
                'conservative_signals_only': True,
                'min_confluence_score': 0.9,
                'reduced_position_size': 0.3,
                'tight_stop_loss': 0.01,
                'quick_profit_target': 0.02,
                'max_trades_per_day': 3,
                'avoid_high_volatility': True
            },
            market_regimes=[MarketRegime.VOLATILE, MarketRegime.REVERSAL],
            min_confidence=0.9,
            performance_weight=0.6,
            active=True
        )
        
        # Initialize performance tracking
        for strategy_type in self.strategy_configs:
            self.strategy_performance[strategy_type] = {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl': 0.0,
                'max_drawdown': 0.0,
                'avg_trade_duration': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'sharpe_ratio': 0.0,
                'last_used': None
            }
            self.strategy_trade_history[strategy_type] = []
    
    def analyze_market_regime(self, price_data: List[float], volume_data: List[float], 
                            current_price: float) -> MarketAnalysis:
        """Analyze current market regime and recommend strategy"""
        try:
            if len(price_data) < self.analysis_window:
                return self._create_default_analysis(current_price)
            
            prices = np.array(price_data[-self.analysis_window:])
            volumes = np.array(volume_data[-self.analysis_window:]) if volume_data else np.ones(len(prices))
            
            # Calculate market metrics
            volatility = self._calculate_volatility(prices)
            trend_strength = self._calculate_trend_strength(prices)
            volume_profile = self._analyze_volume_profile(volumes)
            range_analysis = self._analyze_range_conditions(prices)
            breakout_potential = self._detect_breakout_conditions(prices, volumes)
            
            # Determine market regime
            regime, confidence = self._determine_market_regime(
                volatility, trend_strength, volume_profile, range_analysis, breakout_potential
            )
            
            # Get support/resistance levels
            support_resistance = self._calculate_support_resistance(prices, current_price)
            
            # Recommend strategy based on regime
            recommended_strategy = self._recommend_strategy(regime, confidence)
            
            analysis = MarketAnalysis(
                regime=regime,
                confidence=confidence,
                volatility=volatility,
                trend_strength=trend_strength,
                volume_profile=volume_profile,
                support_resistance=support_resistance,
                recommended_strategy=recommended_strategy,
                analysis_timestamp=datetime.utcnow()
            )
            
            # Store analysis history
            self.market_history.append(analysis)
            if len(self.market_history) > 1000:
                self.market_history = self.market_history[-500:]
            
            return analysis
            
        except Exception as e:
            logging.error(f"Error analyzing market regime: {e}")
            return self._create_default_analysis(current_price)
    
    def _calculate_volatility(self, prices: np.ndarray) -> float:
        """Calculate normalized volatility"""
        try:
            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns) * np.sqrt(24 * 365)  # Annualized volatility
            return min(volatility, 2.0)  # Cap at 200%
        except:
            return 0.5  # Default moderate volatility
    
    def _calculate_trend_strength(self, prices: np.ndarray) -> float:
        """Calculate trend strength using multiple methods"""
        try:
            # Linear regression slope
            x = np.arange(len(prices))
            slope = np.polyfit(x, prices, 1)[0]
            slope_strength = abs(slope) / prices[-1]
            
            # Moving average crossover strength
            ema_short = self._calculate_ema(prices, 12)
            ema_long = self._calculate_ema(prices, 26)
            if ema_short and ema_long:
                ma_strength = abs(ema_short[-1] - ema_long[-1]) / prices[-1]
            else:
                ma_strength = 0
            
            # Directional movement
            highs = prices * 1.001  # Approximate highs
            lows = prices * 0.999   # Approximate lows
            
            dm_plus = np.mean([max(highs[i] - highs[i-1], 0) for i in range(1, len(highs))])
            dm_minus = np.mean([max(lows[i-1] - lows[i], 0) for i in range(1, len(lows))])
            
            if dm_plus + dm_minus > 0:
                directional_strength = abs(dm_plus - dm_minus) / (dm_plus + dm_minus)
            else:
                directional_strength = 0
            
            # Combine measures
            trend_strength = (slope_strength * 0.4 + ma_strength * 0.3 + directional_strength * 0.3)
            return min(trend_strength * 10, 1.0)  # Normalize to 0-1
            
        except:
            return 0.0
    
    def _analyze_volume_profile(self, volumes: np.ndarray) -> str:
        """Analyze volume characteristics"""
        try:
            recent_avg = np.mean(volumes[-10:])
            overall_avg = np.mean(volumes)
            volume_trend = recent_avg / overall_avg
            
            if volume_trend > 1.5:
                return "increasing"
            elif volume_trend < 0.7:
                return "decreasing"
            else:
                return "stable"
        except:
            return "stable"
    
    def _analyze_range_conditions(self, prices: np.ndarray) -> Dict[str, float]:
        """Analyze if market is range-bound"""
        try:
            # Calculate recent range
            recent_high = np.max(prices[-20:])
            recent_low = np.min(prices[-20:])
            range_size = (recent_high - recent_low) / recent_low
            
            # Calculate price position within range
            current_position = (prices[-1] - recent_low) / (recent_high - recent_low)
            
            # Count touches of support/resistance
            tolerance = range_size * 0.05  # 5% tolerance
            support_touches = sum(1 for p in prices[-20:] if abs(p - recent_low) / recent_low < tolerance)
            resistance_touches = sum(1 for p in prices[-20:] if abs(p - recent_high) / recent_high < tolerance)
            
            return {
                'range_size': range_size,
                'position_in_range': current_position,
                'support_touches': support_touches,
                'resistance_touches': resistance_touches,
                'is_ranging': range_size < 0.1 and (support_touches >= 2 or resistance_touches >= 2)
            }
        except:
            return {'range_size': 0.05, 'position_in_range': 0.5, 'is_ranging': False}
    
    def _detect_breakout_conditions(self, prices: np.ndarray, volumes: np.ndarray) -> Dict[str, Any]:
        """Detect potential breakout conditions"""
        try:
            # Recent consolidation
            recent_volatility = np.std(prices[-10:]) / np.mean(prices[-10:])
            overall_volatility = np.std(prices[-30:]) / np.mean(prices[-30:])
            
            consolidation = recent_volatility < overall_volatility * 0.7
            
            # Volume buildup
            recent_volume = np.mean(volumes[-5:])
            baseline_volume = np.mean(volumes[-20:-5])
            volume_buildup = recent_volume > baseline_volume * 1.2
            
            # Price compression
            recent_range = (np.max(prices[-10:]) - np.min(prices[-10:])) / np.mean(prices[-10:])
            price_compression = recent_range < 0.03  # Less than 3% range
            
            # Breakout probability
            breakout_score = 0
            if consolidation:
                breakout_score += 0.3
            if volume_buildup:
                breakout_score += 0.4
            if price_compression:
                breakout_score += 0.3
            
            return {
                'consolidation': consolidation,
                'volume_buildup': volume_buildup,
                'price_compression': price_compression,
                'breakout_probability': breakout_score,
                'imminent_breakout': breakout_score > 0.7
            }
        except:
            return {'breakout_probability': 0.0, 'imminent_breakout': False}
    
    def _determine_market_regime(self, volatility: float, trend_strength: float, 
                               volume_profile: str, range_analysis: Dict[str, Any],
                               breakout_analysis: Dict[str, Any]) -> Tuple[MarketRegime, float]:
        """Determine market regime with confidence score"""
        try:
            scores = {}
            
            # Trending regime
            if trend_strength > 0.6 and volatility > 0.3:
                scores[MarketRegime.TRENDING] = trend_strength * 0.7 + (volatility / 2) * 0.3
            
            # Ranging regime
            if range_analysis.get('is_ranging', False) and trend_strength < 0.4:
                range_score = 0.8 if range_analysis['range_size'] < 0.08 else 0.6
                scores[MarketRegime.RANGING] = range_score
            
            # Volatile regime
            if volatility > 0.8:
                scores[MarketRegime.VOLATILE] = volatility * 0.9
            
            # Low volatility regime
            if volatility < 0.2 and trend_strength < 0.3:
                scores[MarketRegime.LOW_VOLATILITY] = (1 - volatility) * 0.8
            
            # Breakout regime
            if breakout_analysis.get('imminent_breakout', False):
                scores[MarketRegime.BREAKOUT] = breakout_analysis['breakout_probability']
            
            # Reversal regime (detect potential reversals)
            if trend_strength > 0.5 and volatility > 0.6:
                # Look for divergence or exhaustion signals
                reversal_score = volatility * 0.3 + (1 - trend_strength) * 0.2
                if reversal_score > 0.4:
                    scores[MarketRegime.REVERSAL] = reversal_score
            
            if not scores:
                return MarketRegime.RANGING, 0.5  # Default
            
            # Get regime with highest score
            best_regime = max(scores, key=scores.get)
            confidence = scores[best_regime]
            
            return best_regime, min(confidence, 1.0)
            
        except Exception as e:
            logging.error(f"Error determining market regime: {e}")
            return MarketRegime.RANGING, 0.5
    
    def _calculate_support_resistance(self, prices: np.ndarray, current_price: float) -> Dict[str, float]:
        """Calculate key support and resistance levels"""
        try:
            # Find local highs and lows
            highs = []
            lows = []
            
            for i in range(2, len(prices) - 2):
                if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                    if prices[i] > prices[i-2] and prices[i] > prices[i+2]:
                        highs.append(prices[i])
                
                if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                    if prices[i] < prices[i-2] and prices[i] < prices[i+2]:
                        lows.append(prices[i])
            
            # Find nearest levels
            resistance = min([h for h in highs if h > current_price], default=current_price * 1.05)
            support = max([l for l in lows if l < current_price], default=current_price * 0.95)
            
            return {
                'support': support,
                'resistance': resistance,
                'support_strength': len([l for l in lows if abs(l - support) / support < 0.01]),
                'resistance_strength': len([h for h in highs if abs(h - resistance) / resistance < 0.01])
            }
        except:
            return {
                'support': current_price * 0.98,
                'resistance': current_price * 1.02,
                'support_strength': 1,
                'resistance_strength': 1
            }
    
    def _recommend_strategy(self, regime: MarketRegime, confidence: float) -> StrategyType:
        """Recommend optimal strategy for current market regime"""
        try:
            # Get strategies suitable for this regime
            suitable_strategies = []
            
            for strategy_type, config in self.strategy_configs.items():
                if (config.active and 
                    regime in config.market_regimes and 
                    confidence >= config.min_confidence):
                    
                    # Calculate strategy score based on performance and suitability
                    performance = self.strategy_performance.get(strategy_type, {})
                    performance_score = performance.get('win_rate', 0.5) * performance.get('profit_factor', 1.0)
                    
                    total_score = (confidence * 0.6 + performance_score * 0.4) * config.performance_weight
                    
                    suitable_strategies.append((strategy_type, total_score))
            
            if suitable_strategies:
                # Sort by score and return best strategy
                suitable_strategies.sort(key=lambda x: x[1], reverse=True)
                return suitable_strategies[0][0]
            
            # Fallback to defensive strategy
            return StrategyType.DEFENSIVE
            
        except Exception as e:
            logging.error(f"Error recommending strategy: {e}")
            return StrategyType.DEFENSIVE
    
    def should_switch_strategy(self, current_analysis: MarketAnalysis) -> Tuple[bool, Optional[StrategyType]]:
        """Determine if strategy should be switched"""
        try:
            with self.lock:
                recommended_strategy = current_analysis.recommended_strategy
                
                # Check if already using recommended strategy
                if self.current_strategy == recommended_strategy:
                    return False, None
                
                # Check cooldown period
                if (self.last_strategy_switch and 
                    datetime.utcnow() - self.last_strategy_switch < self.strategy_switch_cooldown):
                    return False, None
                
                # Check regime stability (avoid switching on noise)
                if len(self.market_history) >= 3:
                    recent_regimes = [analysis.regime for analysis in self.market_history[-3:]]
                    regime_consistency = sum(1 for r in recent_regimes if r == current_analysis.regime) / len(recent_regimes)
                    
                    if regime_consistency < self.regime_stability_threshold:
                        return False, None
                
                # Check confidence threshold
                if current_analysis.confidence < 0.6:
                    return False, None
                
                # Check if new strategy has better expected performance
                current_performance = self.strategy_performance.get(self.current_strategy, {})
                new_performance = self.strategy_performance.get(recommended_strategy, {})
                
                current_score = current_performance.get('win_rate', 0.5) * current_performance.get('profit_factor', 1.0)
                new_score = new_performance.get('win_rate', 0.5) * new_performance.get('profit_factor', 1.0)
                
                # Only switch if new strategy is significantly better or current is performing poorly
                if new_score > current_score * 1.1 or current_score < 0.3:
                    return True, recommended_strategy
                
                return False, None
                
        except Exception as e:
            logging.error(f"Error checking strategy switch: {e}")
            return False, None
    
    def switch_strategy(self, new_strategy: StrategyType, reason: str = "regime_change") -> Dict[str, Any]:
        """Switch to new trading strategy"""
        try:
            with self.lock:
                old_strategy = self.current_strategy
                self.current_strategy = new_strategy
                self.last_strategy_switch = datetime.utcnow()
                
                # Update strategy usage tracking
                if new_strategy in self.strategy_performance:
                    self.strategy_performance[new_strategy]['last_used'] = datetime.utcnow()
                
                # Get new strategy parameters
                new_config = self.strategy_configs.get(new_strategy)
                
                switch_info = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'old_strategy': old_strategy.value if old_strategy else None,
                    'new_strategy': new_strategy.value,
                    'reason': reason,
                    'new_parameters': new_config.parameters if new_config else {},
                    'success': True
                }
                
                logging.info(f"Strategy switched: {old_strategy} → {new_strategy} ({reason})")
                return switch_info
                
        except Exception as e:
            logging.error(f"Error switching strategy: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_current_strategy_config(self) -> Optional[Dict[str, Any]]:
        """Get current strategy configuration"""
        try:
            if not self.current_strategy:
                return None
            
            config = self.strategy_configs.get(self.current_strategy)
            if not config:
                return None
            
            performance = self.strategy_performance.get(self.current_strategy, {})
            
            return {
                'strategy_type': config.strategy_type.value,
                'parameters': config.parameters,
                'market_regimes': [regime.value for regime in config.market_regimes],
                'min_confidence': config.min_confidence,
                'performance': performance,
                'active_since': self.last_strategy_switch.isoformat() if self.last_strategy_switch else None
            }
            
        except Exception as e:
            logging.error(f"Error getting current strategy config: {e}")
            return None
    
    def update_strategy_performance(self, strategy_type: StrategyType, trade_result: Dict[str, Any]):
        """Update strategy performance metrics"""
        try:
            with self.lock:
                if strategy_type not in self.strategy_performance:
                    return
                
                perf = self.strategy_performance[strategy_type]
                trade_pnl = trade_result.get('pnl', 0.0)
                
                # Update basic metrics
                perf['total_trades'] += 1
                perf['total_pnl'] += trade_pnl
                
                if trade_pnl > 0:
                    perf['winning_trades'] += 1
                
                # Update derived metrics
                if perf['total_trades'] > 0:
                    perf['win_rate'] = perf['winning_trades'] / perf['total_trades']
                
                # Store trade for detailed analysis
                trade_record = {
                    'timestamp': trade_result.get('timestamp', datetime.utcnow()),
                    'pnl': trade_pnl,
                    'duration': trade_result.get('duration', 0),
                    'market_regime': trade_result.get('market_regime')
                }
                
                self.strategy_trade_history[strategy_type].append(trade_record)
                
                # Keep only recent trades
                if len(self.strategy_trade_history[strategy_type]) > 100:
                    self.strategy_trade_history[strategy_type] = self.strategy_trade_history[strategy_type][-50:]
                
                # Calculate profit factor
                wins = [t['pnl'] for t in self.strategy_trade_history[strategy_type] if t['pnl'] > 0]
                losses = [abs(t['pnl']) for t in self.strategy_trade_history[strategy_type] if t['pnl'] < 0]
                
                if wins and losses:
                    perf['profit_factor'] = sum(wins) / sum(losses)
                
                logging.debug(f"Updated performance for {strategy_type.value}: {perf['win_rate']:.2%} win rate")
                
        except Exception as e:
            logging.error(f"Error updating strategy performance: {e}")
    
    def get_strategy_rankings(self) -> List[Dict[str, Any]]:
        """Get strategies ranked by performance"""
        try:
            rankings = []
            
            for strategy_type, config in self.strategy_configs.items():
                if not config.active:
                    continue
                
                performance = self.strategy_performance.get(strategy_type, {})
                
                # Calculate composite score
                win_rate = performance.get('win_rate', 0)
                profit_factor = performance.get('profit_factor', 1)
                total_trades = performance.get('total_trades', 0)
                
                # Confidence factor based on sample size
                confidence_factor = min(total_trades / 20, 1.0) if total_trades > 0 else 0.1
                
                composite_score = (win_rate * profit_factor * confidence_factor) * config.performance_weight
                
                rankings.append({
                    'strategy': strategy_type.value,
                    'composite_score': composite_score,
                    'win_rate': win_rate,
                    'profit_factor': profit_factor,
                    'total_trades': total_trades,
                    'total_pnl': performance.get('total_pnl', 0),
                    'suitable_regimes': [regime.value for regime in config.market_regimes],
                    'last_used': performance.get('last_used'),
                    'currently_active': strategy_type == self.current_strategy
                })
            
            # Sort by composite score
            rankings.sort(key=lambda x: x['composite_score'], reverse=True)
            
            return rankings
            
        except Exception as e:
            logging.error(f"Error getting strategy rankings: {e}")
            return []
    
    def _create_default_analysis(self, current_price: float) -> MarketAnalysis:
        """Create default market analysis when insufficient data"""
        return MarketAnalysis(
            regime=MarketRegime.RANGING,
            confidence=0.5,
            volatility=0.3,
            trend_strength=0.0,
            volume_profile="stable",
            support_resistance={
                'support': current_price * 0.98,
                'resistance': current_price * 1.02
            },
            recommended_strategy=StrategyType.DEFENSIVE,
            analysis_timestamp=datetime.utcnow()
        )
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> Optional[List[float]]:
        """Calculate EMA for given period"""
        try:
            if len(prices) < period:
                return None
            
            multiplier = 2 / (period + 1)
            ema_values = [np.mean(prices[:period])]
            
            for i in range(period, len(prices)):
                ema = prices[i] * multiplier + ema_values[-1] * (1 - multiplier)
                ema_values.append(ema)
            
            return ema_values
        except:
            return None
    
    def export_system_data(self) -> Dict[str, Any]:
        """Export comprehensive system data"""
        try:
            with self.lock:
                return {
                    'export_timestamp': datetime.utcnow().isoformat(),
                    'current_strategy': self.current_strategy.value if self.current_strategy else None,
                    'strategy_configs': {
                        strategy.value: {
                            'parameters': config.parameters,
                            'market_regimes': [r.value for r in config.market_regimes],
                            'active': config.active,
                            'performance': self.strategy_performance.get(strategy, {})
                        }
                        for strategy, config in self.strategy_configs.items()
                    },
                    'recent_market_analysis': [
                        {
                            'regime': analysis.regime.value,
                            'confidence': analysis.confidence,
                            'volatility': analysis.volatility,
                            'trend_strength': analysis.trend_strength,
                            'timestamp': analysis.analysis_timestamp.isoformat()
                        }
                        for analysis in self.market_history[-20:]  # Last 20 analyses
                    ],
                    'strategy_rankings': self.get_strategy_rankings()
                }
        except Exception as e:
            logging.error(f"Error exporting system data: {e}")
            return {'error': str(e)}