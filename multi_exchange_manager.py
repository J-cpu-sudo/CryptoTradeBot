import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json
import time

class ExchangeType(Enum):
    OKX = "okx"
    BYBIT = "bybit"
    BINANCE = "binance"
    DERIV = "deriv"

class ExchangeStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"

@dataclass
class ExchangeConfig:
    name: str
    exchange_type: ExchangeType
    api_key: str
    api_secret: str
    passphrase: Optional[str]
    sandbox: bool
    enabled: bool
    weight: float  # Capital allocation weight
    base_url: Optional[str] = None

@dataclass
class ExchangeBalance:
    exchange: str
    currency: str
    total: float
    available: float
    locked: float
    timestamp: datetime

@dataclass
class CrossExchangeOrder:
    order_id: str
    exchange: str
    symbol: str
    side: str
    amount: float
    price: float
    order_type: str
    status: str
    filled: float
    remaining: float
    timestamp: datetime

class MultiExchangeManager:
    """Manages trading across multiple exchanges with intelligent routing"""
    
    def __init__(self):
        self.exchanges: Dict[str, Any] = {}
        self.exchange_configs: Dict[str, ExchangeConfig] = {}
        self.exchange_status: Dict[str, ExchangeStatus] = {}
        self.balances: Dict[str, List[ExchangeBalance]] = {}
        self.active_orders: Dict[str, List[CrossExchangeOrder]] = {}
        
        # Capital allocation
        self.total_capital = 0.0
        self.allocation_weights = {}
        self.min_allocation_per_exchange = 100.0  # Minimum $100 per exchange
        
        # Performance tracking
        self.exchange_performance: Dict[str, Dict[str, float]] = {}
        self.latency_tracking: Dict[str, List[float]] = {}
        
        # Risk management
        self.max_exchanges_active = 4
        self.correlation_threshold = 0.7
        
        # Thread safety
        self.lock = threading.Lock()
        
        logging.info("Multi-exchange manager initialized")
    
    def add_exchange(self, config: ExchangeConfig) -> bool:
        """Add and configure a new exchange"""
        try:
            with self.lock:
                if config.name in self.exchanges:
                    logging.warning(f"Exchange {config.name} already exists")
                    return False
                
                # Initialize exchange client based on type
                exchange_client = self._create_exchange_client(config)
                if not exchange_client:
                    return False
                
                self.exchanges[config.name] = exchange_client
                self.exchange_configs[config.name] = config
                self.exchange_status[config.name] = ExchangeStatus.DISCONNECTED
                self.balances[config.name] = []
                self.active_orders[config.name] = []
                self.exchange_performance[config.name] = {
                    'total_trades': 0,
                    'successful_trades': 0,
                    'total_pnl': 0.0,
                    'avg_latency': 0.0,
                    'uptime': 0.0
                }
                self.latency_tracking[config.name] = []
                
                # Test connection
                if self._test_exchange_connection(config.name):
                    self.exchange_status[config.name] = ExchangeStatus.CONNECTED
                    logging.info(f"Successfully added exchange: {config.name}")
                    return True
                else:
                    self._remove_exchange(config.name)
                    return False
                
        except Exception as e:
            logging.error(f"Error adding exchange {config.name}: {e}")
            return False
    
    def _create_exchange_client(self, config: ExchangeConfig) -> Optional[Any]:
        """Create exchange-specific client"""
        try:
            if config.exchange_type == ExchangeType.OKX:
                return self._create_okx_client(config)
            elif config.exchange_type == ExchangeType.BYBIT:
                return self._create_bybit_client(config)
            elif config.exchange_type == ExchangeType.BINANCE:
                return self._create_binance_client(config)
            elif config.exchange_type == ExchangeType.DERIV:
                return self._create_deriv_client(config)
            else:
                logging.error(f"Unsupported exchange type: {config.exchange_type}")
                return None
                
        except Exception as e:
            logging.error(f"Error creating client for {config.name}: {e}")
            return None
    
    def _create_okx_client(self, config: ExchangeConfig) -> Dict[str, Any]:
        """Create OKX API client"""
        return {
            'type': 'okx',
            'config': config,
            'base_url': 'https://www.okx.com' if not config.sandbox else 'https://www.okx.com',
            'endpoints': {
                'ticker': '/api/v5/market/ticker',
                'candles': '/api/v5/market/candles',
                'balance': '/api/v5/account/balance',
                'order': '/api/v5/trade/order',
                'orders': '/api/v5/trade/orders-pending'
            }
        }
    
    def _create_bybit_client(self, config: ExchangeConfig) -> Dict[str, Any]:
        """Create Bybit API client"""
        return {
            'type': 'bybit',
            'config': config,
            'base_url': 'https://api.bybit.com' if not config.sandbox else 'https://api-testnet.bybit.com',
            'endpoints': {
                'ticker': '/v5/market/tickers',
                'candles': '/v5/market/kline',
                'balance': '/v5/account/wallet-balance',
                'order': '/v5/order/create',
                'orders': '/v5/order/realtime'
            }
        }
    
    def _create_binance_client(self, config: ExchangeConfig) -> Dict[str, Any]:
        """Create Binance API client"""
        return {
            'type': 'binance',
            'config': config,
            'base_url': 'https://api.binance.com' if not config.sandbox else 'https://testnet.binance.vision',
            'endpoints': {
                'ticker': '/api/v3/ticker/24hr',
                'candles': '/api/v3/klines',
                'balance': '/api/v3/account',
                'order': '/api/v3/order',
                'orders': '/api/v3/openOrders'
            }
        }
    
    def _create_deriv_client(self, config: ExchangeConfig) -> Dict[str, Any]:
        """Create Deriv API client"""
        return {
            'type': 'deriv',
            'config': config,
            'base_url': 'https://api.deriv.com' if not config.sandbox else 'https://api.deriv.com',
            'endpoints': {
                'ticker': '/ticks',
                'candles': '/ticks_history',
                'balance': '/balance',
                'order': '/buy',
                'orders': '/portfolio'
            }
        }
    
    def _test_exchange_connection(self, exchange_name: str) -> bool:
        """Test connection to exchange"""
        try:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                return False
            
            # Simple connectivity test (would implement actual API call)
            start_time = time.time()
            
            # Simulate API call delay
            time.sleep(0.1)
            
            latency = (time.time() - start_time) * 1000
            self.latency_tracking[exchange_name].append(latency)
            
            logging.info(f"Connection test passed for {exchange_name} (latency: {latency:.1f}ms)")
            return True
            
        except Exception as e:
            logging.error(f"Connection test failed for {exchange_name}: {e}")
            return False
    
    def get_optimal_exchange_routing(self, symbol: str, side: str, amount: float) -> List[Tuple[str, float]]:
        """Get optimal exchange routing for order execution"""
        try:
            with self.lock:
                available_exchanges = [
                    name for name, status in self.exchange_status.items()
                    if status == ExchangeStatus.CONNECTED and self.exchange_configs[name].enabled
                ]
                
                if not available_exchanges:
                    return []
                
                # Get current prices and liquidity from each exchange
                exchange_quotes = {}
                for exchange_name in available_exchanges:
                    quote = self._get_exchange_quote(exchange_name, symbol, side, amount)
                    if quote:
                        exchange_quotes[exchange_name] = quote
                
                if not exchange_quotes:
                    return []
                
                # Sort by best price
                if side == 'buy':
                    # For buy orders, prefer lowest ask price
                    sorted_exchanges = sorted(
                        exchange_quotes.items(),
                        key=lambda x: x[1]['price']
                    )
                else:
                    # For sell orders, prefer highest bid price
                    sorted_exchanges = sorted(
                        exchange_quotes.items(),
                        key=lambda x: x[1]['price'],
                        reverse=True
                    )
                
                # Calculate routing based on liquidity and allocation weights
                routing = []
                remaining_amount = amount
                
                for exchange_name, quote in sorted_exchanges:
                    if remaining_amount <= 0:
                        break
                    
                    # Consider exchange allocation weight
                    weight = self.exchange_configs[exchange_name].weight
                    max_allocation = amount * weight
                    
                    # Consider available liquidity
                    available_liquidity = quote.get('available_amount', amount)
                    
                    # Calculate amount for this exchange
                    exchange_amount = min(remaining_amount, max_allocation, available_liquidity)
                    
                    if exchange_amount > 0:
                        routing.append((exchange_name, exchange_amount))
                        remaining_amount -= exchange_amount
                
                return routing
                
        except Exception as e:
            logging.error(f"Error calculating optimal routing: {e}")
            return []
    
    def _get_exchange_quote(self, exchange_name: str, symbol: str, side: str, amount: float) -> Optional[Dict[str, Any]]:
        """Get price quote from specific exchange"""
        try:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                return None
            
            # Simulate getting real-time quote
            # In production, this would make actual API calls
            base_price = 45000  # BTC price simulation
            spread = 10  # $10 spread simulation
            
            if side == 'buy':
                price = base_price + spread/2
            else:
                price = base_price - spread/2
            
            # Add small random variation per exchange
            import random
            price_variation = random.uniform(-20, 20)
            price += price_variation
            
            return {
                'price': price,
                'available_amount': amount * 2,  # Assume 2x liquidity available
                'timestamp': datetime.utcnow(),
                'exchange': exchange_name
            }
            
        except Exception as e:
            logging.error(f"Error getting quote from {exchange_name}: {e}")
            return None
    
    def execute_cross_exchange_order(self, symbol: str, side: str, total_amount: float, 
                                   order_type: str = 'market') -> List[CrossExchangeOrder]:
        """Execute order across multiple exchanges with optimal routing"""
        try:
            with self.lock:
                # Get optimal routing
                routing = self.get_optimal_exchange_routing(symbol, side, total_amount)
                
                if not routing:
                    logging.error("No available exchanges for order execution")
                    return []
                
                executed_orders = []
                
                for exchange_name, amount in routing:
                    try:
                        order = self._execute_single_exchange_order(
                            exchange_name, symbol, side, amount, order_type
                        )
                        
                        if order:
                            executed_orders.append(order)
                            self.active_orders[exchange_name].append(order)
                            
                            # Update performance tracking
                            self._update_exchange_performance(exchange_name, True)
                        else:
                            self._update_exchange_performance(exchange_name, False)
                            
                    except Exception as e:
                        logging.error(f"Error executing order on {exchange_name}: {e}")
                        self._update_exchange_performance(exchange_name, False)
                
                logging.info(f"Executed {len(executed_orders)} orders across {len(routing)} exchanges")
                return executed_orders
                
        except Exception as e:
            logging.error(f"Error executing cross-exchange order: {e}")
            return []
    
    def _execute_single_exchange_order(self, exchange_name: str, symbol: str, side: str, 
                                     amount: float, order_type: str) -> Optional[CrossExchangeOrder]:
        """Execute order on single exchange"""
        try:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                return None
            
            # Generate order ID
            order_id = f"{exchange_name}_{int(time.time() * 1000)}"
            
            # Simulate order execution
            start_time = time.time()
            
            # Get execution price
            quote = self._get_exchange_quote(exchange_name, symbol, side, amount)
            if not quote:
                return None
            
            execution_price = quote['price']
            
            # Record latency
            execution_latency = (time.time() - start_time) * 1000
            self.latency_tracking[exchange_name].append(execution_latency)
            
            # Create order record
            order = CrossExchangeOrder(
                order_id=order_id,
                exchange=exchange_name,
                symbol=symbol,
                side=side,
                amount=amount,
                price=execution_price,
                order_type=order_type,
                status='filled',  # Simulate immediate fill for market orders
                filled=amount,
                remaining=0.0,
                timestamp=datetime.utcnow()
            )
            
            logging.info(f"Order executed on {exchange_name}: {side} {amount} {symbol} at {execution_price}")
            return order
            
        except Exception as e:
            logging.error(f"Error executing order on {exchange_name}: {e}")
            return None
    
    def update_all_balances(self) -> Dict[str, List[ExchangeBalance]]:
        """Update balances across all connected exchanges"""
        try:
            with self.lock:
                updated_balances = {}
                
                for exchange_name in self.exchanges.keys():
                    if self.exchange_status[exchange_name] == ExchangeStatus.CONNECTED:
                        balances = self._get_exchange_balances(exchange_name)
                        if balances:
                            self.balances[exchange_name] = balances
                            updated_balances[exchange_name] = balances
                
                # Update total capital calculation
                self._update_total_capital()
                
                return updated_balances
                
        except Exception as e:
            logging.error(f"Error updating balances: {e}")
            return {}
    
    def _get_exchange_balances(self, exchange_name: str) -> List[ExchangeBalance]:
        """Get balances from specific exchange"""
        try:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                return []
            
            # Simulate balance retrieval
            # In production, this would make actual API calls
            balances = []
            
            # Simulate USDT balance
            total_usdt = 1000.0  # Simulate $1000 balance
            available_usdt = total_usdt * 0.9  # 90% available
            locked_usdt = total_usdt - available_usdt
            
            balances.append(ExchangeBalance(
                exchange=exchange_name,
                currency='USDT',
                total=total_usdt,
                available=available_usdt,
                locked=locked_usdt,
                timestamp=datetime.utcnow()
            ))
            
            # Simulate BTC balance
            btc_amount = 0.02  # Simulate 0.02 BTC
            balances.append(ExchangeBalance(
                exchange=exchange_name,
                currency='BTC',
                total=btc_amount,
                available=btc_amount,
                locked=0.0,
                timestamp=datetime.utcnow()
            ))
            
            return balances
            
        except Exception as e:
            logging.error(f"Error getting balances from {exchange_name}: {e}")
            return []
    
    def _update_total_capital(self):
        """Update total capital across all exchanges"""
        try:
            total = 0.0
            btc_price = 45000  # Simulate BTC price
            
            for exchange_name, balances in self.balances.items():
                exchange_total = 0.0
                
                for balance in balances:
                    if balance.currency == 'USDT':
                        exchange_total += balance.total
                    elif balance.currency == 'BTC':
                        exchange_total += balance.total * btc_price
                
                total += exchange_total
                
                # Update allocation weight based on current balance
                if total > 0:
                    self.allocation_weights[exchange_name] = exchange_total / total
            
            self.total_capital = total
            
        except Exception as e:
            logging.error(f"Error updating total capital: {e}")
    
    def _update_exchange_performance(self, exchange_name: str, success: bool):
        """Update performance metrics for exchange"""
        try:
            perf = self.exchange_performance.get(exchange_name, {})
            
            perf['total_trades'] = perf.get('total_trades', 0) + 1
            if success:
                perf['successful_trades'] = perf.get('successful_trades', 0) + 1
            
            # Update average latency
            latencies = self.latency_tracking.get(exchange_name, [])
            if latencies:
                perf['avg_latency'] = sum(latencies[-10:]) / len(latencies[-10:])  # Last 10 trades
            
            # Calculate success rate
            if perf['total_trades'] > 0:
                perf['success_rate'] = perf['successful_trades'] / perf['total_trades']
            
            self.exchange_performance[exchange_name] = perf
            
        except Exception as e:
            logging.error(f"Error updating performance for {exchange_name}: {e}")
    
    def get_exchange_rankings(self) -> List[Dict[str, Any]]:
        """Get exchanges ranked by performance"""
        try:
            rankings = []
            
            for exchange_name, perf in self.exchange_performance.items():
                status = self.exchange_status.get(exchange_name, ExchangeStatus.DISCONNECTED)
                config = self.exchange_configs.get(exchange_name)
                
                ranking_score = 0.0
                if perf.get('total_trades', 0) > 0:
                    # Calculate composite score
                    success_rate = perf.get('success_rate', 0)
                    avg_latency = perf.get('avg_latency', 1000)
                    uptime = perf.get('uptime', 0)
                    
                    # Lower latency is better, so invert it
                    latency_score = max(0, 1000 - avg_latency) / 1000
                    
                    ranking_score = (success_rate * 0.4 + latency_score * 0.3 + uptime * 0.3)
                
                rankings.append({
                    'exchange': exchange_name,
                    'type': config.exchange_type.value if config else 'unknown',
                    'status': status.value,
                    'enabled': config.enabled if config else False,
                    'ranking_score': ranking_score,
                    'performance': perf,
                    'current_allocation': self.allocation_weights.get(exchange_name, 0)
                })
            
            # Sort by ranking score (highest first)
            rankings.sort(key=lambda x: x['ranking_score'], reverse=True)
            
            return rankings
            
        except Exception as e:
            logging.error(f"Error getting exchange rankings: {e}")
            return []
    
    def rebalance_allocations(self) -> Dict[str, float]:
        """Rebalance capital allocations based on performance"""
        try:
            with self.lock:
                rankings = self.get_exchange_rankings()
                active_exchanges = [r for r in rankings if r['status'] == 'connected' and r['enabled']]
                
                if not active_exchanges:
                    return {}
                
                # Calculate new weights based on performance
                total_score = sum(r['ranking_score'] for r in active_exchanges)
                new_weights = {}
                
                if total_score > 0:
                    for exchange_data in active_exchanges:
                        exchange_name = exchange_data['exchange']
                        performance_weight = exchange_data['ranking_score'] / total_score
                        
                        # Apply minimum and maximum allocation limits
                        min_weight = 0.1  # 10% minimum
                        max_weight = 0.5  # 50% maximum
                        
                        new_weight = max(min_weight, min(max_weight, performance_weight))
                        new_weights[exchange_name] = new_weight
                
                # Normalize weights to sum to 1.0
                total_weight = sum(new_weights.values())
                if total_weight > 0:
                    for exchange_name in new_weights:
                        new_weights[exchange_name] /= total_weight
                
                # Update allocation weights
                self.allocation_weights.update(new_weights)
                
                logging.info(f"Rebalanced allocations: {new_weights}")
                return new_weights
                
        except Exception as e:
            logging.error(f"Error rebalancing allocations: {e}")
            return {}
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            with self.lock:
                connected_exchanges = len([
                    s for s in self.exchange_status.values() 
                    if s == ExchangeStatus.CONNECTED
                ])
                
                total_orders = sum(len(orders) for orders in self.active_orders.values())
                
                return {
                    'total_exchanges': len(self.exchanges),
                    'connected_exchanges': connected_exchanges,
                    'total_capital': self.total_capital,
                    'active_orders': total_orders,
                    'allocation_weights': self.allocation_weights,
                    'exchange_status': {name: status.value for name, status in self.exchange_status.items()},
                    'performance_summary': {
                        name: {
                            'success_rate': perf.get('success_rate', 0),
                            'avg_latency': perf.get('avg_latency', 0),
                            'total_trades': perf.get('total_trades', 0)
                        }
                        for name, perf in self.exchange_performance.items()
                    },
                    'last_updated': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logging.error(f"Error getting system status: {e}")
            return {'error': str(e)}
    
    def _remove_exchange(self, exchange_name: str):
        """Remove exchange from system"""
        try:
            with self.lock:
                if exchange_name in self.exchanges:
                    del self.exchanges[exchange_name]
                if exchange_name in self.exchange_configs:
                    del self.exchange_configs[exchange_name]
                if exchange_name in self.exchange_status:
                    del self.exchange_status[exchange_name]
                if exchange_name in self.balances:
                    del self.balances[exchange_name]
                if exchange_name in self.active_orders:
                    del self.active_orders[exchange_name]
                if exchange_name in self.exchange_performance:
                    del self.exchange_performance[exchange_name]
                if exchange_name in self.latency_tracking:
                    del self.latency_tracking[exchange_name]
                
                logging.info(f"Removed exchange: {exchange_name}")
                
        except Exception as e:
            logging.error(f"Error removing exchange {exchange_name}: {e}")
    
    def export_system_data(self) -> Dict[str, Any]:
        """Export comprehensive system data"""
        try:
            with self.lock:
                return {
                    'export_timestamp': datetime.utcnow().isoformat(),
                    'system_status': self.get_system_status(),
                    'exchange_rankings': self.get_exchange_rankings(),
                    'recent_orders': {
                        name: [asdict(order) for order in orders[-10:]]  # Last 10 orders per exchange
                        for name, orders in self.active_orders.items()
                    },
                    'balance_summary': {
                        name: [asdict(balance) for balance in balances]
                        for name, balances in self.balances.items()
                    }
                }
                
        except Exception as e:
            logging.error(f"Error exporting system data: {e}")
            return {'error': str(e)}