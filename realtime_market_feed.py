import asyncio
import websockets
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from collections import deque
from dataclasses import dataclass

@dataclass
class MarketTick:
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    bid: float
    ask: float
    change_24h: float
    volume_24h: float

@dataclass
class TradeTick:
    symbol: str
    price: float
    size: float
    side: str  # 'buy' or 'sell'
    timestamp: datetime

class RealtimeMarketFeed:
    """Real-time market data feed with volume spike detection and latency optimization"""
    
    def __init__(self):
        self.ws = None
        self.is_connected = False
        self.callbacks = []
        self.running = False
        
        # Real-time data storage
        self.current_prices = {}
        self.price_history = deque(maxlen=1000)
        self.trade_history = deque(maxlen=500)
        self.volume_history = deque(maxlen=100)
        
        # Performance metrics
        self.latency_ms = 0
        self.message_count = 0
        self.last_update = None
        
        # Volume spike detection
        self.volume_threshold = 2.0  # 2x average volume
        self.price_change_threshold = 0.005  # 0.5% price change
        
        logging.info("Real-time market feed initialized")
    
    async def connect_and_stream(self, symbols: List[str] = ["BTC-USDT"]):
        """Connect to OKX WebSocket and start streaming"""
        try:
            uri = "wss://ws.okx.com:8443/ws/v5/public"
            
            async with websockets.connect(uri) as websocket:
                self.ws = websocket
                self.is_connected = True
                logging.info("Connected to OKX WebSocket")
                
                # Subscribe to real-time feeds
                await self._subscribe_to_feeds(symbols)
                
                # Start message processing loop
                await self._process_messages()
                
        except Exception as e:
            logging.error(f"WebSocket connection error: {e}")
            self.is_connected = False
            await self._reconnect()
    
    async def _subscribe_to_feeds(self, symbols: List[str]):
        """Subscribe to ticker and trade feeds"""
        for symbol in symbols:
            # Subscribe to ticker (price updates)
            ticker_sub = {
                "op": "subscribe",
                "args": [{"channel": "tickers", "instId": symbol}]
            }
            await self.ws.send(json.dumps(ticker_sub))
            
            # Subscribe to trades (volume/trade flow)
            trades_sub = {
                "op": "subscribe", 
                "args": [{"channel": "trades", "instId": symbol}]
            }
            await self.ws.send(json.dumps(trades_sub))
            
            logging.info(f"Subscribed to real-time feeds for {symbol}")
    
    async def _process_messages(self):
        """Process incoming WebSocket messages"""
        self.running = True
        
        while self.running and self.ws:
            try:
                message = await asyncio.wait_for(self.ws.recv(), timeout=30.0)
                await self._handle_message(message)
                
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await self.ws.ping()
                continue
                
            except websockets.exceptions.ConnectionClosed:
                logging.warning("WebSocket connection closed")
                break
    
    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message with latency tracking"""
        start_time = time.time()
        
        try:
            data = json.loads(message)
            
            if 'data' not in data:
                return
            
            channel = data.get('arg', {}).get('channel')
            
            for item in data['data']:
                if channel == 'tickers':
                    await self._process_ticker(item)
                elif channel == 'trades':
                    await self._process_trade(item)
            
            # Update performance metrics
            self.latency_ms = (time.time() - start_time) * 1000
            self.message_count += 1
            self.last_update = datetime.utcnow()
            
        except Exception as e:
            logging.error(f"Error processing message: {e}")
    
    async def _process_ticker(self, ticker_data: Dict[str, Any]):
        """Process ticker data for real-time price updates"""
        try:
            symbol = ticker_data.get('instId')
            price = float(ticker_data.get('last', 0))
            volume_24h = float(ticker_data.get('vol24h', 0))
            
            market_tick = MarketTick(
                symbol=symbol,
                price=price,
                volume=volume_24h,
                timestamp=datetime.utcnow(),
                bid=float(ticker_data.get('bidPx', 0)),
                ask=float(ticker_data.get('askPx', 0)),
                change_24h=float(ticker_data.get('chg24h', 0)),
                volume_24h=volume_24h
            )
            
            # Update current price tracking
            old_price = self.current_prices.get(symbol, price)
            self.current_prices[symbol] = price
            
            # Add to price history
            self.price_history.append(market_tick)
            
            # Detect significant price movements
            price_change = abs(price - old_price) / old_price if old_price > 0 else 0
            
            # Volume spike detection
            volume_spike = self._detect_volume_spike(symbol, volume_24h)
            
            # Create enhanced market update
            market_update = {
                'type': 'ticker',
                'symbol': symbol,
                'price': price,
                'volume_24h': volume_24h,
                'bid': market_tick.bid,
                'ask': market_tick.ask,
                'spread': market_tick.ask - market_tick.bid,
                'change_24h': market_tick.change_24h,
                'timestamp': market_tick.timestamp.isoformat(),
                'latency_ms': self.latency_ms,
                'price_change': price_change,
                'volume_spike': volume_spike,
                'significant_move': price_change > self.price_change_threshold
            }
            
            # Notify all callbacks
            await self._notify_callbacks(market_update)
            
        except Exception as e:
            logging.error(f"Error processing ticker: {e}")
    
    async def _process_trade(self, trade_data: Dict[str, Any]):
        """Process individual trade data for volume analysis"""
        try:
            symbol = trade_data.get('instId')
            price = float(trade_data.get('px', 0))
            size = float(trade_data.get('sz', 0))
            side = trade_data.get('side')
            
            trade_tick = TradeTick(
                symbol=symbol,
                price=price,
                size=size,
                side=side,
                timestamp=datetime.utcnow()
            )
            
            # Add to trade history
            self.trade_history.append(trade_tick)
            
            # Calculate trade flow metrics
            trade_update = {
                'type': 'trade',
                'symbol': symbol,
                'price': price,
                'size': size,
                'side': side,
                'timestamp': trade_tick.timestamp.isoformat(),
                'trade_intensity': self._calculate_trade_intensity(symbol),
                'buy_sell_ratio': self._calculate_buy_sell_ratio(symbol)
            }
            
            # Notify callbacks for trade flow analysis
            await self._notify_callbacks(trade_update)
            
        except Exception as e:
            logging.error(f"Error processing trade: {e}")
    
    def _detect_volume_spike(self, symbol: str, current_volume: float) -> Dict[str, Any]:
        """Detect volume spikes compared to recent average"""
        try:
            # Get recent volume data for this symbol
            recent_volumes = [
                tick.volume for tick in list(self.price_history)[-20:] 
                if tick.symbol == symbol
            ]
            
            if len(recent_volumes) < 5:
                return {'detected': False, 'ratio': 1.0, 'avg_volume': current_volume}
            
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            return {
                'detected': volume_ratio > self.volume_threshold,
                'ratio': volume_ratio,
                'avg_volume': avg_volume,
                'threshold': self.volume_threshold
            }
            
        except Exception as e:
            logging.error(f"Volume spike detection error: {e}")
            return {'detected': False, 'ratio': 1.0, 'avg_volume': current_volume}
    
    def _calculate_trade_intensity(self, symbol: str) -> float:
        """Calculate recent trade intensity (trades per minute)"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=1)
            recent_trades = [
                trade for trade in self.trade_history 
                if trade.symbol == symbol and trade.timestamp > cutoff_time
            ]
            return len(recent_trades)
            
        except Exception:
            return 0.0
    
    def _calculate_buy_sell_ratio(self, symbol: str) -> Dict[str, Any]:
        """Calculate buy/sell ratio from recent trades"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=5)
            recent_trades = [
                trade for trade in self.trade_history 
                if trade.symbol == symbol and trade.timestamp > cutoff_time
            ]
            
            buy_volume = sum(trade.size for trade in recent_trades if trade.side == 'buy')
            sell_volume = sum(trade.size for trade in recent_trades if trade.side == 'sell')
            total_volume = buy_volume + sell_volume
            
            return {
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'buy_ratio': buy_volume / total_volume if total_volume > 0 else 0.5,
                'net_flow': buy_volume - sell_volume
            }
            
        except Exception:
            return {'buy_volume': 0, 'sell_volume': 0, 'buy_ratio': 0.5, 'net_flow': 0}
    
    async def _notify_callbacks(self, data: Dict[str, Any]):
        """Notify all registered callbacks with market data"""
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logging.error(f"Callback error: {e}")
    
    async def _reconnect(self):
        """Reconnect with exponential backoff"""
        wait_time = 5
        max_wait = 60
        
        while not self.is_connected and self.running:
            logging.info(f"Reconnecting in {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            
            try:
                await self.connect_and_stream()
            except Exception as e:
                logging.error(f"Reconnection failed: {e}")
                wait_time = min(wait_time * 2, max_wait)
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for real-time market updates"""
        self.callbacks.append(callback)
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        return self.current_prices.get(symbol)
    
    def get_recent_data(self, symbol: str, limit: int = 50) -> List[MarketTick]:
        """Get recent market data for symbol"""
        return [tick for tick in list(self.price_history)[-limit:] if tick.symbol == symbol]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get feed performance statistics"""
        return {
            'connected': self.is_connected,
            'latency_ms': self.latency_ms,
            'messages_received': self.message_count,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'symbols_tracked': len(set(tick.symbol for tick in self.price_history)),
            'data_points': len(self.price_history)
        }
    
    def stop(self):
        """Stop the feed"""
        self.running = False
        self.is_connected = False


class MarketFeedManager:
    """Thread-safe manager for real-time market feed"""
    
    def __init__(self):
        self.feed = RealtimeMarketFeed()
        self.thread = None
        self.running = False
    
    def start(self, symbols: List[str] = ["BTC-USDT"]):
        """Start market feed in background thread"""
        if self.running:
            logging.warning("Market feed already running")
            return
        
        def run_feed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self.feed.connect_and_stream(symbols))
            except Exception as e:
                logging.error(f"Market feed error: {e}")
            finally:
                loop.close()
        
        self.thread = threading.Thread(target=run_feed, daemon=True)
        self.thread.start()
        self.running = True
        
        logging.info("Market feed manager started")
    
    def stop(self):
        """Stop market feed"""
        if not self.running:
            return
        
        self.feed.stop()
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
        
        logging.info("Market feed manager stopped")
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for market updates"""
        self.feed.add_callback(callback)
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price"""
        return self.feed.get_current_price(symbol)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return self.feed.get_performance_stats()
    
    def get_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Get current market snapshot"""
        recent_data = self.feed.get_recent_data(symbol, 10)
        
        if not recent_data:
            return {'error': 'No data available'}
        
        latest = recent_data[-1]
        
        return {
            'symbol': symbol,
            'price': latest.price,
            'volume_24h': latest.volume_24h,
            'change_24h': latest.change_24h,
            'bid': latest.bid,
            'ask': latest.ask,
            'spread': latest.ask - latest.bid,
            'timestamp': latest.timestamp.isoformat(),
            'data_quality': 'live' if self.feed.is_connected else 'stale'
        }