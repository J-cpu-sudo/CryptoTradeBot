import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

class CurrencyTier(Enum):
    TIER_1 = "tier_1"  # BTC, ETH - highest allocation
    TIER_2 = "tier_2"  # SOL, ADA, BNB - medium allocation  
    TIER_3 = "tier_3"  # Smaller caps - lower allocation

@dataclass
class CurrencyConfig:
    symbol: str
    tier: CurrencyTier
    max_allocation_percent: float
    risk_multiplier: float
    min_trade_size: float
    exchange_priority: List[str]
    trading_enabled: bool = True
    
class MultiCurrencyManager:
    """Manages trading across multiple cryptocurrency pairs with intelligent allocation"""
    
    def __init__(self):
        self.currencies = self._init_currency_configs()
        self.current_allocations = {}
        self.performance_metrics = {}
        self.correlation_matrix = {}
        
        logging.info(f"Multi-currency manager initialized with {len(self.currencies)} trading pairs")
    
    def _init_currency_configs(self) -> Dict[str, CurrencyConfig]:
        """Initialize supported currency configurations"""
        configs = {
            # Tier 1 - Major cryptocurrencies (40% max allocation each)
            "BTC-USDT": CurrencyConfig(
                symbol="BTC-USDT",
                tier=CurrencyTier.TIER_1,
                max_allocation_percent=40.0,
                risk_multiplier=1.0,
                min_trade_size=10.0,
                exchange_priority=["OKX", "Binance", "Bybit"]
            ),
            "ETH-USDT": CurrencyConfig(
                symbol="ETH-USDT", 
                tier=CurrencyTier.TIER_1,
                max_allocation_percent=35.0,
                risk_multiplier=1.2,
                min_trade_size=10.0,
                exchange_priority=["OKX", "Binance", "Bybit"]
            ),
            
            # Tier 2 - Established altcoins (25% max allocation each)
            "SOL-USDT": CurrencyConfig(
                symbol="SOL-USDT",
                tier=CurrencyTier.TIER_2, 
                max_allocation_percent=25.0,
                risk_multiplier=1.5,
                min_trade_size=5.0,
                exchange_priority=["OKX", "Binance", "Bybit"]
            ),
            "ADA-USDT": CurrencyConfig(
                symbol="ADA-USDT",
                tier=CurrencyTier.TIER_2,
                max_allocation_percent=20.0,
                risk_multiplier=1.8,
                min_trade_size=5.0,
                exchange_priority=["OKX", "Binance", "Bybit"]
            ),
            "BNB-USDT": CurrencyConfig(
                symbol="BNB-USDT",
                tier=CurrencyTier.TIER_2,
                max_allocation_percent=20.0,
                risk_multiplier=1.4,
                min_trade_size=5.0,
                exchange_priority=["Binance", "OKX"]
            ),
            
            # Tier 3 - Smaller caps (15% max allocation each)
            "DOT-USDT": CurrencyConfig(
                symbol="DOT-USDT",
                tier=CurrencyTier.TIER_3,
                max_allocation_percent=15.0,
                risk_multiplier=2.0,
                min_trade_size=3.0,
                exchange_priority=["OKX", "Binance", "Bybit"]
            ),
            "AVAX-USDT": CurrencyConfig(
                symbol="AVAX-USDT",
                tier=CurrencyTier.TIER_3,
                max_allocation_percent=15.0,
                risk_multiplier=2.0,
                min_trade_size=3.0,
                exchange_priority=["OKX", "Binance", "Bybit"]
            )
        }
        
        return configs
    
    def get_enabled_symbols(self) -> List[str]:
        """Get list of enabled trading symbols"""
        return [config.symbol for config in self.currencies.values() if config.trading_enabled]
    
    def get_currency_config(self, symbol: str) -> Optional[CurrencyConfig]:
        """Get configuration for specific currency"""
        return self.currencies.get(symbol)
    
    def calculate_position_size(self, symbol: str, account_balance: float, signal_strength: float) -> float:
        """Calculate position size for currency based on tier and risk"""
        config = self.get_currency_config(symbol)
        if not config:
            return 0.0
        
        # Base allocation based on tier
        base_allocation = config.max_allocation_percent / 100.0
        
        # Adjust for signal strength (0.5 to 1.5 multiplier)
        signal_multiplier = 0.5 + (signal_strength * 1.0)
        
        # Apply risk multiplier
        risk_adjusted_allocation = base_allocation * signal_multiplier / config.risk_multiplier
        
        # Calculate position size
        position_size = account_balance * risk_adjusted_allocation
        
        # Ensure minimum trade size
        return max(position_size, config.min_trade_size)
    
    def check_correlation_limits(self, new_symbol: str, existing_positions: Dict[str, float]) -> bool:
        """Check if new position would violate correlation limits"""
        # Simple correlation check - avoid overexposure to similar assets
        tier_exposure = {}
        
        # Calculate current tier exposure
        for symbol, position_value in existing_positions.items():
            config = self.get_currency_config(symbol)
            if config:
                tier = config.tier.value
                tier_exposure[tier] = tier_exposure.get(tier, 0) + position_value
        
        # Check new position tier exposure
        new_config = self.get_currency_config(new_symbol)
        if not new_config:
            return False
        
        new_tier = new_config.tier.value
        current_tier_exposure = tier_exposure.get(new_tier, 0)
        
        # Tier exposure limits
        tier_limits = {
            "tier_1": 0.60,  # 60% max in tier 1
            "tier_2": 0.45,  # 45% max in tier 2  
            "tier_3": 0.30   # 30% max in tier 3
        }
        
        total_portfolio = sum(existing_positions.values())
        if total_portfolio == 0:
            return True
        
        tier_exposure_percent = current_tier_exposure / total_portfolio
        return tier_exposure_percent < tier_limits.get(new_tier, 0.20)
    
    def get_best_exchange(self, symbol: str) -> str:
        """Get best exchange for trading symbol"""
        config = self.get_currency_config(symbol)
        if not config or not config.exchange_priority:
            return "OKX"  # Default
        
        return config.exchange_priority[0]
    
    def update_performance(self, symbol: str, pnl: float, trade_count: int):
        """Update performance metrics for currency"""
        if symbol not in self.performance_metrics:
            self.performance_metrics[symbol] = {
                "total_pnl": 0.0,
                "trade_count": 0,
                "win_rate": 0.0,
                "avg_return": 0.0
            }
        
        metrics = self.performance_metrics[symbol]
        metrics["total_pnl"] += pnl
        metrics["trade_count"] += trade_count
        
        # Calculate win rate and average return (simplified)
        if metrics["trade_count"] > 0:
            metrics["avg_return"] = metrics["total_pnl"] / metrics["trade_count"]
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio summary"""
        summary = {
            "total_currencies": len(self.currencies),
            "enabled_currencies": len(self.get_enabled_symbols()),
            "tier_breakdown": {
                "tier_1": len([c for c in self.currencies.values() if c.tier == CurrencyTier.TIER_1]),
                "tier_2": len([c for c in self.currencies.values() if c.tier == CurrencyTier.TIER_2]),
                "tier_3": len([c for c in self.currencies.values() if c.tier == CurrencyTier.TIER_3])
            },
            "performance_metrics": self.performance_metrics,
            "enabled_symbols": self.get_enabled_symbols()
        }
        
        return summary
    
    def enable_currency(self, symbol: str, enabled: bool = True):
        """Enable or disable trading for specific currency"""
        if symbol in self.currencies:
            self.currencies[symbol].trading_enabled = enabled
            logging.info(f"Currency {symbol} {'enabled' if enabled else 'disabled'}")
    
    def add_custom_currency(self, symbol: str, tier: CurrencyTier, max_allocation: float, 
                          risk_multiplier: float = 1.5, min_trade_size: float = 5.0):
        """Add custom currency configuration"""
        config = CurrencyConfig(
            symbol=symbol,
            tier=tier,
            max_allocation_percent=max_allocation,
            risk_multiplier=risk_multiplier,
            min_trade_size=min_trade_size,
            exchange_priority=["OKX", "Binance", "Bybit"]
        )
        
        self.currencies[symbol] = config
        logging.info(f"Added custom currency: {symbol}")
    
    def export_config(self) -> str:
        """Export currency configurations to JSON"""
        export_data = {}
        for symbol, config in self.currencies.items():
            export_data[symbol] = asdict(config)
            export_data[symbol]["tier"] = config.tier.value
        
        return json.dumps(export_data, indent=2)
    
    def get_rebalancing_recommendations(self, current_positions: Dict[str, float]) -> List[Dict[str, Any]]:
        """Get portfolio rebalancing recommendations"""
        recommendations = []
        total_value = sum(current_positions.values())
        
        if total_value == 0:
            return recommendations
        
        for symbol, config in self.currencies.items():
            if not config.trading_enabled:
                continue
            
            current_value = current_positions.get(symbol, 0)
            current_percent = (current_value / total_value) * 100
            target_percent = config.max_allocation_percent * 0.8  # Target 80% of max
            
            difference = target_percent - current_percent
            
            if abs(difference) > 5.0:  # Only recommend if >5% difference
                action = "increase" if difference > 0 else "decrease"
                recommendations.append({
                    "symbol": symbol,
                    "action": action,
                    "current_percent": round(current_percent, 2),
                    "target_percent": round(target_percent, 2),
                    "difference": round(difference, 2)
                })
        
        return sorted(recommendations, key=lambda x: abs(x["difference"]), reverse=True)