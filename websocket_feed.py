import asyncio
import websockets
import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from models import db, MarketData
import time

class WebSocketPriceFeed:
    """Real-time WebSocket price feed for ultra-low latency trading"""
    
    def __init__(self):
        self.ws = None
        self.is_connected = False
        self.callbacks = []
        self.last_price = None
        self.last_volume = None
        self.price_history = []
        self.connection_retries = 0
        self.max_retries = 10
        self.running = False
        
        # Performance tracking
        self.latency_ms = 0
        self.message_count = 0
        self.start_time = time.time()
        
        logging.info("WebSocket price feed initialized")
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for price updates"""
        self.callbacks.append(callback)
    
    async def connect(self, symbols: list = ["BTC-USDT"]):
        """Connect to OKX WebSocket feed"""
        try:
            # OKX WebSocket endpoint
            uri = "wss://ws.okx.com:8443/ws/v5/public"
            
            self.ws = await websockets.connect(uri)
            self.is_connected = True
            self.connection_retries = 0
            
            # Subscribe to ticker and trades
            subscriptions = []
            for symbol in symbols:
                subscriptions.extend([
                    {
                        "op": "subscribe",
                        "args": [{
                            "channel": "tickers",
                            "instId": symbol
                        }]
                    },
                    {
                        "op": "subscribe", 
                        "args": [{
                            "channel": "trades",
                            "instId": symbol
                        }]
                    }
                ])
            
            for sub in subscriptions:
                await self.ws.send(json.dumps(sub))
                logging.info(f"Subscribed to {sub['args'][0]['channel']} for {sub['args'][0]['instId']}")
            
            logging.info(f"WebSocket connected to OKX for symbols: {symbols}")
            
        except Exception as e:
            logging.error(f"WebSocket connection failed: {e}")
            self.is_connected = False
            raise
    
    async def listen(self):
        """Listen for WebSocket messages"""
        self.running = True
        
        try:
            while self.running and self.ws:
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=30.0)
                    await self.handle_message(message)
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await self.ws.ping()
                    continue
                    
                except websockets.exceptions.ConnectionClosed:
                    logging.warning("WebSocket connection closed")
                    break
                    
        except Exception as e:
            logging.error(f"WebSocket listen error: {e}")
        
        finally:
            self.is_connected = False
            if self.connection_retries < self.max_retries:
                await self.reconnect()
    
    async def handle_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            start_time = time.time()
            data = json.loads(message)
            
            if 'data' not in data:
                return
            
            for item in data['data']:
                if data.get('arg', {}).get('channel') == 'tickers':
                    await self.handle_ticker(item)
                elif data.get('arg', {}).get('channel') == 'trades':
                    await self.handle_trade(item)
            
            # Calculate latency
            self.latency_ms = (time.time() - start_time) * 1000
            self.message_count += 1
            
        except Exception as e:
            logging.error(f"Error handling WebSocket message: {e}")
    
    async def handle_ticker(self, ticker_data: Dict[str, Any]):
        """Handle ticker data"""
        try:
            symbol = ticker_data.get('instId')
            price = float(ticker_data.get('last', 0))
            volume = float(ticker_data.get('vol24h', 0))
            timestamp = datetime.utcnow()
            
            # Update internal state
            self.last_price = price
            self.last_volume = volume
            
            # Store in price history (keep last 1000 points)
            self.price_history.append({
                'timestamp': timestamp,
                'price': price,
                'volume': volume
            })
            if len(self.price_history) > 1000:
                self.price_history.pop(0)
            
            # Create market data object
            market_update = {
                'symbol': symbol,
                'price': price,
                'volume': volume,
                'timestamp': timestamp,
                'bid': float(ticker_data.get('bidPx', 0)),
                'ask': float(ticker_data.get('askPx', 0)),
                'high_24h': float(ticker_data.get('high24h', 0)),
                'low_24h': float(ticker_data.get('low24h', 0)),
                'change_24h': float(ticker_data.get('chg24h', 0)),
                'latency_ms': self.latency_ms
            }
            
            # Store in database (async)
            asyncio.create_task(self.store_market_data(market_update))
            
            # Notify callbacks
            for callback in self.callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(market_update))
                    else:
                        callback(market_update)
                except Exception as e:
                    logging.error(f"Callback error: {e}")
            
        except Exception as e:
            logging.error(f"Error handling ticker: {e}")
    
    async def handle_trade(self, trade_data: Dict[str, Any]):
        """Handle individual trade data for volume analysis"""
        try:
            symbol = trade_data.get('instId')
            price = float(trade_data.get('px', 0))
            size = float(trade_data.get('sz', 0))
            side = trade_data.get('side')  # buy/sell
            timestamp = datetime.utcnow()
            
            trade_update = {
                'type': 'trade',
                'symbol': symbol,
                'price': price,
                'size': size,
                'side': side,
                'timestamp': timestamp,
                'latency_ms': self.latency_ms
            }
            
            # Notify callbacks for real-time trade analysis
            for callback in self.callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(trade_update))
                    else:
                        callback(trade_update)
                except Exception as e:
                    logging.error(f"Trade callback error: {e}")
            
        except Exception as e:
            logging.error(f"Error handling trade: {e}")
    
    async def store_market_data(self, market_update: Dict[str, Any]):
        """Store market data in database asynchronously"""
        try:
            # This should be called in a separate thread to avoid blocking
            def store_data():
                try:
                    from flask import current_app
                    with current_app.app_context():
                        market_data = MarketData(
                            symbol=market_update['symbol'],
                            price=market_update['price'],
                            volume=market_update['volume'],
                            timestamp=market_update['timestamp']
                        )
                        db.session.add(market_data)
                        db.session.commit()
                except Exception as e:
                    logging.error(f"Database storage error: {e}")
                    try:
                        db.session.rollback()
                    except:
                        pass
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, store_data)
            
        except Exception as e:
            logging.error(f"Error storing market data: {e}")
    
    async def reconnect(self):
        """Reconnect to WebSocket with exponential backoff"""
        if self.connection_retries >= self.max_retries:
            logging.error("Max reconnection attempts reached")
            return
        
        self.connection_retries += 1
        wait_time = min(2 ** self.connection_retries, 60)  # Max 60 seconds
        
        logging.info(f"Reconnecting in {wait_time} seconds (attempt {self.connection_retries})")
        await asyncio.sleep(wait_time)
        
        try:
            await self.connect()
            await self.listen()
        except Exception as e:
            logging.error(f"Reconnection failed: {e}")
            await self.reconnect()
    
    def get_current_price(self) -> Optional[float]:
        """Get current price (thread-safe)"""
        return self.last_price
    
    def get_price_history(self, limit: int = 100) -> list:
        """Get recent price history"""
        return self.price_history[-limit:] if self.price_history else []
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get WebSocket performance statistics"""
        uptime = time.time() - self.start_time
        return {
            'connected': self.is_connected,
            'latency_ms': self.latency_ms,
            'messages_received': self.message_count,
            'uptime_seconds': uptime,
            'messages_per_second': self.message_count / uptime if uptime > 0 else 0,
            'connection_retries': self.connection_retries
        }
    
    async def close(self):
        """Close WebSocket connection"""
        self.running = False
        if self.ws:
            await self.ws.close()
        self.is_connected = False
        logging.info("WebSocket connection closed")


class WebSocketManager:
    """Thread-safe WebSocket manager for integration with Flask app"""
    
    def __init__(self, app=None):
        self.feed = WebSocketPriceFeed()
        self.loop = None
        self.thread = None
        self.running = False
        self.app = app
    
    def start(self, symbols: list = ["BTC-USDT"]):
        """Start WebSocket feed in background thread"""
        if self.running:
            logging.warning("WebSocket feed already running")
            return
        
        def run_websocket():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            async def websocket_main():
                try:
                    await self.feed.connect(symbols)
                    await self.feed.listen()
                except Exception as e:
                    logging.error(f"WebSocket main error: {e}")
            
            self.loop.run_until_complete(websocket_main())
        
        self.thread = threading.Thread(target=run_websocket, daemon=True)
        self.thread.start()
        self.running = True
        
        logging.info("WebSocket manager started")
    
    def stop(self):
        """Stop WebSocket feed"""
        if not self.running:
            return
        
        self.running = False
        
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.feed.close(), self.loop)
        
        if self.thread:
            self.thread.join(timeout=5)
        
        logging.info("WebSocket manager stopped")
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for price updates"""
        self.feed.add_callback(callback)
    
    def get_current_price(self) -> Optional[float]:
        """Get current price"""
        return self.feed.get_current_price()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return self.feed.get_performance_stats()