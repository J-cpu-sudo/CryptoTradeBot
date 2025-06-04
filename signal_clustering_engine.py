import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
from collections import defaultdict

class SignalType(Enum):
    RSI = "rsi"
    MACD = "macd"
    EMA_CROSS = "ema_cross"
    BOLLINGER = "bollinger"
    VOLUME = "volume"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    SUPPORT_RESISTANCE = "support_resistance"

class SignalStrength(Enum):
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4

@dataclass
class TradingSignal:
    signal_type: SignalType
    direction: str  # 'bullish', 'bearish', 'neutral'
    strength: SignalStrength
    confidence: float
    value: float
    threshold: float
    timestamp: datetime
    symbol: str
    metadata: Dict[str, Any]

@dataclass
class SignalCluster:
    cluster_id: str
    signals: List[TradingSignal]
    cluster_strength: float
    cluster_confidence: float
    dominant_direction: str
    signal_count: int
    consensus_score: float
    cross_validation_score: float
    timestamp: datetime

class SignalClusteringEngine:
    """Advanced signal clustering and ensembling for high-quality trade decisions"""
    
    def __init__(self):
        self.active_signals: Dict[str, List[TradingSignal]] = defaultdict(list)
        self.signal_clusters: List[SignalCluster] = []
        self.cluster_history: List[SignalCluster] = []
        
        # Clustering parameters
        self.min_cluster_size = 3
        self.max_cluster_size = 8
        self.cluster_time_window = timedelta(minutes=5)
        self.min_consensus_threshold = 0.7
        self.signal_correlation_threshold = 0.6
        
        # Signal weights for different types
        self.signal_weights = {
            SignalType.RSI: 1.0,
            SignalType.MACD: 1.2,
            SignalType.EMA_CROSS: 1.1,
            SignalType.BOLLINGER: 0.9,
            SignalType.VOLUME: 1.3,
            SignalType.MOMENTUM: 1.0,
            SignalType.BREAKOUT: 1.4,
            SignalType.SUPPORT_RESISTANCE: 1.2
        }
        
        # Performance tracking
        self.cluster_performance: Dict[str, Dict[str, float]] = {}
        self.false_positive_rate = 0.0
        self.signal_accuracy: Dict[SignalType, float] = {}
        
        # Thread safety
        self.lock = threading.Lock()
        
        logging.info("Signal clustering engine initialized")
    
    def add_signal(self, signal: TradingSignal) -> bool:
        """Add a new trading signal for clustering analysis"""
        try:
            with self.lock:
                symbol = signal.symbol
                
                # Add to active signals
                self.active_signals[symbol].append(signal)
                
                # Clean old signals
                self._clean_old_signals(symbol)
                
                # Check if we can form a new cluster
                cluster = self._attempt_cluster_formation(symbol)
                
                if cluster:
                    self.signal_clusters.append(cluster)
                    logging.info(f"New signal cluster formed: {cluster.cluster_id} with {cluster.signal_count} signals")
                    return True
                
                return False
                
        except Exception as e:
            logging.error(f"Error adding signal: {e}")
            return False
    
    def _clean_old_signals(self, symbol: str):
        """Remove signals outside the time window"""
        try:
            cutoff_time = datetime.utcnow() - self.cluster_time_window
            
            self.active_signals[symbol] = [
                signal for signal in self.active_signals[symbol]
                if signal.timestamp > cutoff_time
            ]
            
        except Exception as e:
            logging.error(f"Error cleaning old signals: {e}")
    
    def _attempt_cluster_formation(self, symbol: str) -> Optional[SignalCluster]:
        """Attempt to form a signal cluster from active signals"""
        try:
            signals = self.active_signals[symbol]
            
            if len(signals) < self.min_cluster_size:
                return None
            
            # Group signals by direction
            bullish_signals = [s for s in signals if s.direction == 'bullish']
            bearish_signals = [s for s in signals if s.direction == 'bearish']
            
            # Check for dominant direction
            if len(bullish_signals) >= self.min_cluster_size:
                return self._create_cluster(bullish_signals, 'bullish', symbol)
            elif len(bearish_signals) >= self.min_cluster_size:
                return self._create_cluster(bearish_signals, 'bearish', symbol)
            
            return None
            
        except Exception as e:
            logging.error(f"Error attempting cluster formation: {e}")
            return None
    
    def _create_cluster(self, signals: List[TradingSignal], direction: str, symbol: str) -> SignalCluster:
        """Create a signal cluster from compatible signals"""
        try:
            # Sort signals by timestamp (most recent first)
            signals.sort(key=lambda x: x.timestamp, reverse=True)
            
            # Take best signals up to max cluster size
            cluster_signals = signals[:self.max_cluster_size]
            
            # Calculate cluster metrics
            cluster_strength = self._calculate_cluster_strength(cluster_signals)
            cluster_confidence = self._calculate_cluster_confidence(cluster_signals)
            consensus_score = self._calculate_consensus_score(cluster_signals)
            cross_validation_score = self._calculate_cross_validation_score(cluster_signals)
            
            # Generate cluster ID
            cluster_id = f"cluster_{symbol}_{direction}_{int(datetime.utcnow().timestamp())}"
            
            cluster = SignalCluster(
                cluster_id=cluster_id,
                signals=cluster_signals,
                cluster_strength=cluster_strength,
                cluster_confidence=cluster_confidence,
                dominant_direction=direction,
                signal_count=len(cluster_signals),
                consensus_score=consensus_score,
                cross_validation_score=cross_validation_score,
                timestamp=datetime.utcnow()
            )
            
            # Remove clustered signals from active signals
            for signal in cluster_signals:
                if signal in self.active_signals[symbol]:
                    self.active_signals[symbol].remove(signal)
            
            return cluster
            
        except Exception as e:
            logging.error(f"Error creating cluster: {e}")
            return None
    
    def _calculate_cluster_strength(self, signals: List[TradingSignal]) -> float:
        """Calculate overall strength of signal cluster"""
        try:
            if not signals:
                return 0.0
            
            weighted_strength = 0.0
            total_weight = 0.0
            
            for signal in signals:
                weight = self.signal_weights.get(signal.signal_type, 1.0)
                strength_value = signal.strength.value / 4.0  # Normalize to 0-1
                
                weighted_strength += strength_value * weight
                total_weight += weight
            
            return weighted_strength / total_weight if total_weight > 0 else 0.0
            
        except Exception as e:
            logging.error(f"Error calculating cluster strength: {e}")
            return 0.0
    
    def _calculate_cluster_confidence(self, signals: List[TradingSignal]) -> float:
        """Calculate confidence based on signal quality and diversity"""
        try:
            if not signals:
                return 0.0
            
            # Average confidence of individual signals
            avg_confidence = sum(signal.confidence for signal in signals) / len(signals)
            
            # Diversity bonus (different signal types)
            unique_types = len(set(signal.signal_type for signal in signals))
            diversity_bonus = min(unique_types / len(SignalType), 1.0) * 0.2
            
            # Time consistency bonus (signals close in time)
            time_spread = (max(s.timestamp for s in signals) - min(s.timestamp for s in signals)).total_seconds()
            time_bonus = max(0, (300 - time_spread) / 300) * 0.1  # 5-minute window
            
            total_confidence = min(avg_confidence + diversity_bonus + time_bonus, 1.0)
            
            return total_confidence
            
        except Exception as e:
            logging.error(f"Error calculating cluster confidence: {e}")
            return 0.0
    
    def _calculate_consensus_score(self, signals: List[TradingSignal]) -> float:
        """Calculate how well signals agree with each other"""
        try:
            if len(signals) < 2:
                return 1.0
            
            # Check direction consensus
            directions = [signal.direction for signal in signals]
            dominant_direction = max(set(directions), key=directions.count)
            direction_consensus = directions.count(dominant_direction) / len(directions)
            
            # Check strength consensus
            strengths = [signal.strength.value for signal in signals]
            strength_std = np.std(strengths)
            strength_consensus = max(0, 1 - (strength_std / 2))  # Lower std = higher consensus
            
            # Check timing consensus
            timestamps = [signal.timestamp.timestamp() for signal in signals]
            time_std = np.std(timestamps)
            time_consensus = max(0, 1 - (time_std / 300))  # 5-minute window
            
            # Weighted average
            consensus_score = (direction_consensus * 0.5 + 
                             strength_consensus * 0.3 + 
                             time_consensus * 0.2)
            
            return consensus_score
            
        except Exception as e:
            logging.error(f"Error calculating consensus score: {e}")
            return 0.0
    
    def _calculate_cross_validation_score(self, signals: List[TradingSignal]) -> float:
        """Calculate cross-validation score using signal correlations"""
        try:
            if len(signals) < 3:
                return 0.5
            
            # Calculate pairwise correlations between signals
            correlations = []
            
            for i in range(len(signals)):
                for j in range(i + 1, len(signals)):
                    correlation = self._calculate_signal_correlation(signals[i], signals[j])
                    correlations.append(correlation)
            
            if not correlations:
                return 0.5
            
            # Average correlation as cross-validation score
            avg_correlation = sum(correlations) / len(correlations)
            
            # Normalize to 0-1 range
            normalized_score = (avg_correlation + 1) / 2
            
            return normalized_score
            
        except Exception as e:
            logging.error(f"Error calculating cross-validation score: {e}")
            return 0.5
    
    def _calculate_signal_correlation(self, signal1: TradingSignal, signal2: TradingSignal) -> float:
        """Calculate correlation between two signals"""
        try:
            # Direction correlation
            direction_corr = 1.0 if signal1.direction == signal2.direction else -1.0
            
            # Strength correlation
            strength_diff = abs(signal1.strength.value - signal2.strength.value)
            strength_corr = max(0, 1 - (strength_diff / 3))
            
            # Confidence correlation
            conf_diff = abs(signal1.confidence - signal2.confidence)
            conf_corr = max(0, 1 - conf_diff)
            
            # Time correlation (closer in time = higher correlation)
            time_diff = abs((signal1.timestamp - signal2.timestamp).total_seconds())
            time_corr = max(0, 1 - (time_diff / 300))  # 5-minute decay
            
            # Weighted correlation
            total_correlation = (direction_corr * 0.4 + 
                               strength_corr * 0.2 + 
                               conf_corr * 0.2 + 
                               time_corr * 0.2)
            
            return total_correlation
            
        except Exception as e:
            logging.error(f"Error calculating signal correlation: {e}")
            return 0.0
    
    def get_high_quality_clusters(self, min_strength: float = 0.7, 
                                 min_confidence: float = 0.6) -> List[SignalCluster]:
        """Get clusters that meet quality thresholds"""
        try:
            with self.lock:
                quality_clusters = []
                
                for cluster in self.signal_clusters:
                    if (cluster.cluster_strength >= min_strength and 
                        cluster.cluster_confidence >= min_confidence and
                        cluster.consensus_score >= self.min_consensus_threshold):
                        
                        quality_clusters.append(cluster)
                
                # Sort by combined quality score
                quality_clusters.sort(
                    key=lambda c: (c.cluster_strength * c.cluster_confidence * c.consensus_score),
                    reverse=True
                )
                
                return quality_clusters
                
        except Exception as e:
            logging.error(f"Error getting high quality clusters: {e}")
            return []
    
    def evaluate_cluster_for_trading(self, cluster: SignalCluster) -> Dict[str, Any]:
        """Evaluate a cluster for trading decision"""
        try:
            # Calculate final trading score
            quality_score = (cluster.cluster_strength * 0.3 + 
                           cluster.cluster_confidence * 0.3 + 
                           cluster.consensus_score * 0.2 + 
                           cluster.cross_validation_score * 0.2)
            
            # Check for signal diversity
            signal_types = set(signal.signal_type for signal in cluster.signals)
            diversity_score = len(signal_types) / len(SignalType)
            
            # Check for volume confirmation
            volume_signals = [s for s in cluster.signals if s.signal_type == SignalType.VOLUME]
            volume_confirmed = len(volume_signals) > 0 and any(s.strength.value >= 3 for s in volume_signals)
            
            # Check for momentum confirmation
            momentum_signals = [s for s in cluster.signals if s.signal_type == SignalType.MOMENTUM]
            momentum_confirmed = len(momentum_signals) > 0 and any(s.strength.value >= 3 for s in momentum_signals)
            
            # Calculate risk-adjusted score
            risk_adjustment = 1.0
            if cluster.cluster_strength > 0.9:
                risk_adjustment = 1.2  # High confidence boost
            elif cluster.cluster_strength < 0.6:
                risk_adjustment = 0.8  # Low confidence penalty
            
            final_score = quality_score * diversity_score * risk_adjustment
            
            # Determine recommendation
            if final_score >= 0.8 and volume_confirmed:
                recommendation = "STRONG_BUY" if cluster.dominant_direction == "bullish" else "STRONG_SELL"
            elif final_score >= 0.6 and (volume_confirmed or momentum_confirmed):
                recommendation = "BUY" if cluster.dominant_direction == "bullish" else "SELL"
            elif final_score >= 0.4:
                recommendation = "WEAK_BUY" if cluster.dominant_direction == "bullish" else "WEAK_SELL"
            else:
                recommendation = "HOLD"
            
            return {
                'cluster_id': cluster.cluster_id,
                'recommendation': recommendation,
                'final_score': final_score,
                'quality_score': quality_score,
                'diversity_score': diversity_score,
                'volume_confirmed': volume_confirmed,
                'momentum_confirmed': momentum_confirmed,
                'signal_breakdown': {
                    signal_type.value: len([s for s in cluster.signals if s.signal_type == signal_type])
                    for signal_type in SignalType
                },
                'dominant_direction': cluster.dominant_direction,
                'cluster_strength': cluster.cluster_strength,
                'cluster_confidence': cluster.cluster_confidence,
                'timestamp': cluster.timestamp.isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error evaluating cluster: {e}")
            return {'recommendation': 'HOLD', 'error': str(e)}
    
    def update_cluster_performance(self, cluster_id: str, actual_outcome: Dict[str, Any]):
        """Update cluster performance based on actual trading outcome"""
        try:
            with self.lock:
                if cluster_id not in self.cluster_performance:
                    self.cluster_performance[cluster_id] = {
                        'predictions': 0,
                        'correct_predictions': 0,
                        'total_return': 0.0,
                        'accuracy': 0.0
                    }
                
                perf = self.cluster_performance[cluster_id]
                perf['predictions'] += 1
                
                # Check if prediction was correct
                predicted_direction = actual_outcome.get('predicted_direction')
                actual_direction = 'bullish' if actual_outcome.get('pnl', 0) > 0 else 'bearish'
                
                if predicted_direction == actual_direction:
                    perf['correct_predictions'] += 1
                
                # Update returns
                perf['total_return'] += actual_outcome.get('pnl', 0)
                
                # Update accuracy
                perf['accuracy'] = perf['correct_predictions'] / perf['predictions']
                
                # Update signal type accuracy
                cluster = next((c for c in self.cluster_history if c.cluster_id == cluster_id), None)
                if cluster:
                    for signal in cluster.signals:
                        if signal.signal_type not in self.signal_accuracy:
                            self.signal_accuracy[signal.signal_type] = 0.5
                        
                        # Update signal type accuracy with exponential moving average
                        is_correct = predicted_direction == actual_direction
                        alpha = 0.1  # Learning rate
                        self.signal_accuracy[signal.signal_type] = (
                            (1 - alpha) * self.signal_accuracy[signal.signal_type] + 
                            alpha * (1.0 if is_correct else 0.0)
                        )
                
                logging.info(f"Updated cluster performance: {cluster_id}, accuracy: {perf['accuracy']:.2%}")
                
        except Exception as e:
            logging.error(f"Error updating cluster performance: {e}")
    
    def get_signal_quality_metrics(self) -> Dict[str, Any]:
        """Get comprehensive signal quality metrics"""
        try:
            with self.lock:
                total_clusters = len(self.cluster_history)
                successful_clusters = sum(1 for perf in self.cluster_performance.values() 
                                        if perf['accuracy'] > 0.6)
                
                avg_accuracy = 0.0
                if self.cluster_performance:
                    avg_accuracy = sum(perf['accuracy'] for perf in self.cluster_performance.values()) / len(self.cluster_performance)
                
                return {
                    'total_clusters_formed': total_clusters,
                    'successful_clusters': successful_clusters,
                    'cluster_success_rate': successful_clusters / total_clusters if total_clusters > 0 else 0,
                    'average_cluster_accuracy': avg_accuracy,
                    'signal_type_accuracy': dict(self.signal_accuracy),
                    'active_clusters': len(self.signal_clusters),
                    'false_positive_rate': self.false_positive_rate,
                    'signal_weights': dict(self.signal_weights)
                }
                
        except Exception as e:
            logging.error(f"Error getting signal quality metrics: {e}")
            return {}
    
    def cleanup_expired_clusters(self):
        """Clean up old clusters and move to history"""
        try:
            with self.lock:
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                
                # Move expired clusters to history
                expired_clusters = [c for c in self.signal_clusters if c.timestamp < cutoff_time]
                self.cluster_history.extend(expired_clusters)
                
                # Remove expired clusters from active list
                self.signal_clusters = [c for c in self.signal_clusters if c.timestamp >= cutoff_time]
                
                # Limit history size
                if len(self.cluster_history) > 1000:
                    self.cluster_history = self.cluster_history[-500:]
                
                if expired_clusters:
                    logging.info(f"Moved {len(expired_clusters)} expired clusters to history")
                
        except Exception as e:
            logging.error(f"Error cleaning up clusters: {e}")
    
    def export_clustering_data(self) -> Dict[str, Any]:
        """Export comprehensive clustering data"""
        try:
            with self.lock:
                return {
                    'export_timestamp': datetime.utcnow().isoformat(),
                    'active_clusters': len(self.signal_clusters),
                    'cluster_history_size': len(self.cluster_history),
                    'quality_metrics': self.get_signal_quality_metrics(),
                    'recent_clusters': [
                        {
                            'cluster_id': cluster.cluster_id,
                            'signal_count': cluster.signal_count,
                            'dominant_direction': cluster.dominant_direction,
                            'cluster_strength': cluster.cluster_strength,
                            'cluster_confidence': cluster.cluster_confidence,
                            'consensus_score': cluster.consensus_score,
                            'timestamp': cluster.timestamp.isoformat()
                        }
                        for cluster in self.signal_clusters[-10:]  # Last 10 active clusters
                    ],
                    'performance_summary': dict(self.cluster_performance)
                }
                
        except Exception as e:
            logging.error(f"Error exporting clustering data: {e}")
            return {'error': str(e)}