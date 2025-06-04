import logging
from functools import wraps
from flask import has_app_context
from typing import Any, Callable

# Global app reference for context management
_app_instance = None

def set_app_instance(app):
    """Set the global app instance for context management"""
    global _app_instance
    _app_instance = app

def with_app_context(func: Callable) -> Callable:
    """Decorator to ensure function runs within Flask app context"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        global _app_instance
        
        if has_app_context():
            # Already in app context, execute directly
            return func(*args, **kwargs)
        
        if _app_instance is None:
            logging.warning(f"No app context available for {func.__name__}")
            return None
        
        # Create app context and execute
        with _app_instance.app_context():
            return func(*args, **kwargs)
    
    return wrapper

def safe_db_operation(operation_func: Callable, *args, **kwargs) -> Any:
    """Safely execute database operation with proper context"""
    global _app_instance
    
    try:
        if has_app_context():
            return operation_func(*args, **kwargs)
        
        if _app_instance is None:
            logging.warning("No app instance available for database operation")
            return None
        
        with _app_instance.app_context():
            return operation_func(*args, **kwargs)
            
    except Exception as e:
        logging.error(f"Database operation error: {e}")
        return None