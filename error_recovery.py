import logging
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from functools import wraps

class ErrorRecoveryManager:
    """Handles error recovery, reconnection logic, and fault tolerance"""
    
    def __init__(self, db):
        self.db = db
        self.retry_attempts = {}
        self.circuit_breaker_state = {}
        self.max_retries = 3
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 300  # 5 minutes
        
    def with_retry(self, max_retries: int = 3, backoff_factor: float = 2.0, 
                   exceptions: tuple = (Exception,)):
        """Decorator for automatic retry with exponential backoff"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        
                        if attempt == max_retries:
                            logging.error(f"Function {func.__name__} failed after {max_retries} attempts: {e}")
                            break
                            
                        wait_time = backoff_factor ** attempt
                        logging.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {wait_time}s")
                        time.sleep(wait_time)
                
                return None
            return wrapper
        return decorator
    
    def circuit_breaker(self, service_name: str):
        """Circuit breaker pattern to prevent cascading failures"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                now = datetime.utcnow()
                
                # Check if circuit is open
                if service_name in self.circuit_breaker_state:
                    state = self.circuit_breaker_state[service_name]
                    
                    if state['status'] == 'open':
                        # Check if timeout has passed
                        if now - state['opened_at'] > timedelta(seconds=self.circuit_breaker_timeout):
                            state['status'] = 'half_open'
                            state['failure_count'] = 0
                            logging.info(f"Circuit breaker for {service_name} moving to half-open state")
                        else:
                            logging.warning(f"Circuit breaker for {service_name} is open, rejecting call")
                            return None
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Success - reset or close circuit
                    if service_name in self.circuit_breaker_state:
                        if self.circuit_breaker_state[service_name]['status'] == 'half_open':
                            self.circuit_breaker_state[service_name]['status'] = 'closed'
                            logging.info(f"Circuit breaker for {service_name} closed")
                        self.circuit_breaker_state[service_name]['failure_count'] = 0
                    
                    return result
                    
                except Exception as e:
                    # Failure - increment counter and potentially open circuit
                    if service_name not in self.circuit_breaker_state:
                        self.circuit_breaker_state[service_name] = {
                            'status': 'closed',
                            'failure_count': 0,
                            'opened_at': None
                        }
                    
                    state = self.circuit_breaker_state[service_name]
                    state['failure_count'] += 1
                    
                    if state['failure_count'] >= self.circuit_breaker_threshold:
                        state['status'] = 'open'
                        state['opened_at'] = now
                        logging.error(f"Circuit breaker for {service_name} opened after {state['failure_count']} failures")
                    
                    raise e
                    
            return wrapper
        return decorator
    
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health checks"""
        health_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': 'healthy',
            'services': {}
        }
        
        # Check database connectivity
        try:
            from models import BotConfig
            BotConfig.query.first()
            health_status['services']['database'] = {'status': 'healthy', 'response_time': 0}
        except Exception as e:
            health_status['services']['database'] = {'status': 'unhealthy', 'error': str(e)}
            health_status['overall_status'] = 'degraded'
        
        # Check OKX API connectivity
        try:
            start_time = time.time()
            response = requests.get('https://www.okx.com/api/v5/public/time', timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                health_status['services']['okx_api'] = {
                    'status': 'healthy', 
                    'response_time': round(response_time * 1000, 2)
                }
            else:
                health_status['services']['okx_api'] = {
                    'status': 'unhealthy', 
                    'error': f"HTTP {response.status_code}"
                }
                health_status['overall_status'] = 'degraded'
                
        except Exception as e:
            health_status['services']['okx_api'] = {'status': 'unhealthy', 'error': str(e)}
            health_status['overall_status'] = 'degraded'
        
        # Check circuit breaker states
        health_status['circuit_breakers'] = self.circuit_breaker_state.copy()
        
        return health_status
    
    def recover_from_error(self, error_type: str, error_details: Dict[str, Any]) -> bool:
        """Attempt to recover from specific types of errors"""
        recovery_actions = {
            'network_timeout': self._recover_network_timeout,
            'api_rate_limit': self._recover_rate_limit,
            'insufficient_balance': self._recover_insufficient_balance,
            'order_failed': self._recover_order_failed,
            'database_error': self._recover_database_error
        }
        
        if error_type in recovery_actions:
            try:
                return recovery_actions[error_type](error_details)
            except Exception as e:
                logging.error(f"Recovery action for {error_type} failed: {e}")
                return False
        
        logging.warning(f"No recovery action defined for error type: {error_type}")
        return False
    
    def _recover_network_timeout(self, details: Dict[str, Any]) -> bool:
        """Recover from network timeout errors"""
        logging.info("Attempting to recover from network timeout")
        
        # Wait for network to stabilize
        time.sleep(5)
        
        # Test connectivity
        try:
            response = requests.get('https://www.okx.com/api/v5/public/time', timeout=5)
            if response.status_code == 200:
                logging.info("Network connectivity restored")
                return True
        except:
            pass
        
        logging.warning("Network connectivity not restored")
        return False
    
    def _recover_rate_limit(self, details: Dict[str, Any]) -> bool:
        """Recover from API rate limit errors"""
        logging.info("Recovering from API rate limit")
        
        # Wait for rate limit to reset (typically 1 minute for OKX)
        wait_time = 60
        if 'retry_after' in details:
            wait_time = min(details['retry_after'], 300)  # Max 5 minutes
        
        logging.info(f"Waiting {wait_time} seconds for rate limit reset")
        time.sleep(wait_time)
        
        return True
    
    def _recover_insufficient_balance(self, details: Dict[str, Any]) -> bool:
        """Handle insufficient balance scenarios"""
        logging.warning("Insufficient balance detected - pausing trading")
        
        # Log the issue to database
        try:
            from models import BotLog
            log_entry = BotLog(
                level='WARNING',
                message='Trading paused due to insufficient balance',
                component='error_recovery',
                details=str(details)
            )
            self.db.session.add(log_entry)
            self.db.session.commit()
        except Exception as e:
            logging.error(f"Failed to log insufficient balance: {e}")
        
        # Disable trading temporarily
        try:
            from models import BotConfig
            BotConfig.set_value('trading_enabled', 'false', 'Auto-disabled due to insufficient balance')
            return True
        except Exception as e:
            logging.error(f"Failed to disable trading: {e}")
            return False
    
    def _recover_order_failed(self, details: Dict[str, Any]) -> bool:
        """Handle failed order scenarios"""
        logging.info("Attempting to recover from order failure")
        
        # Cancel any pending orders if possible
        if 'order_id' in details and 'symbol' in details:
            try:
                from trader import Trader
                trader = Trader()
                cancel_result = trader.cancel_order(details['order_id'], details['symbol'])
                if cancel_result:
                    logging.info(f"Successfully cancelled failed order {details['order_id']}")
                    return True
            except Exception as e:
                logging.error(f"Failed to cancel order {details['order_id']}: {e}")
        
        return False
    
    def _recover_database_error(self, details: Dict[str, Any]) -> bool:
        """Recover from database errors"""
        logging.info("Attempting to recover from database error")
        
        try:
            # Rollback current transaction
            self.db.session.rollback()
            
            # Test database connectivity
            from models import BotConfig
            BotConfig.query.first()
            
            logging.info("Database connectivity restored")
            return True
            
        except Exception as e:
            logging.error(f"Database recovery failed: {e}")
            return False
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get statistics about error recovery attempts"""
        return {
            'circuit_breakers': self.circuit_breaker_state,
            'retry_attempts': self.retry_attempts,
            'last_health_check': self.health_check()
        }