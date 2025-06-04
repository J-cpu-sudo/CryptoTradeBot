from flask import render_template, request, jsonify, redirect, url_for, flash
from app import app, db
from models import Trade, BotConfig, BotLog, MarketData, TradeStatus, TradeType
from datetime import datetime, timedelta
import json
import logging

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/performance')
def performance():
    """Performance analytics page"""
    return render_template('performance.html')

@app.route('/trades')
def trades():
    """Trade history page"""
    page = request.args.get('page', 1, type=int)
    trades = Trade.query.order_by(Trade.timestamp.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('trades.html', trades=trades)

@app.route('/config')
def config():
    """Configuration page"""
    configs = BotConfig.query.all()
    return render_template('config.html', configs=configs)

@app.route('/api/status')
def api_status():
    """Get bot status and statistics"""
    try:
        bot_manager = app.bot_manager
        status_data = bot_manager.get_status()
        
        # Add additional statistics
        today = datetime.utcnow().date()
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Get trade counts
        today_trades = Trade.query.filter(
            Trade.timestamp >= datetime.combine(today, datetime.min.time())
        ).count()
        
        week_trades = Trade.query.filter(
            Trade.timestamp >= week_ago
        ).count()
        
        # Get recent logs
        recent_logs = BotLog.query.order_by(BotLog.timestamp.desc()).limit(10).all()
        
        status_data.update({
            'today_trades': today_trades,
            'week_trades': week_trades,
            'recent_logs': [log.to_dict() for log in recent_logs]
        })
        
        return jsonify(status_data)
        
    except Exception as e:
        logging.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/performance')
def api_performance():
    """Get performance analytics data"""
    try:
        # Get time range from query parameters
        days = request.args.get('days', 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get trades in the time range
        trades = Trade.query.filter(
            Trade.timestamp >= start_date,
            Trade.pnl != 0
        ).order_by(Trade.timestamp.asc()).all()
        
        if not trades:
            return jsonify({
                'total_pnl': 0,
                'total_trades': 0,
                'win_rate': 0,
                'avg_trade': 0,
                'daily_pnl': [],
                'cumulative_pnl': [],
                'trade_distribution': {'wins': 0, 'losses': 0}
            })
        
        # Calculate metrics
        total_pnl = sum(trade.pnl for trade in trades)
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        avg_trade = total_pnl / total_trades if total_trades > 0 else 0
        
        # Calculate daily P&L
        daily_pnl = {}
        for trade in trades:
            date_key = trade.timestamp.date().isoformat()
            if date_key not in daily_pnl:
                daily_pnl[date_key] = 0
            daily_pnl[date_key] += trade.pnl
        
        # Calculate cumulative P&L
        cumulative_pnl = []
        running_total = 0
        for trade in trades:
            running_total += trade.pnl
            cumulative_pnl.append({
                'date': trade.timestamp.isoformat(),
                'pnl': round(running_total, 2)
            })
        
        return jsonify({
            'total_pnl': round(total_pnl, 2),
            'total_trades': total_trades,
            'win_rate': round(win_rate, 1),
            'avg_trade': round(avg_trade, 2),
            'daily_pnl': [{'date': k, 'pnl': round(v, 2)} for k, v in daily_pnl.items()],
            'cumulative_pnl': cumulative_pnl,
            'trade_distribution': {
                'wins': winning_trades,
                'losses': total_trades - winning_trades
            }
        })
        
    except Exception as e:
        logging.error(f"Error getting performance data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trigger', methods=['POST'])
def api_trigger():
    """Start the trading bot"""
    try:
        bot_manager = app.bot_manager
        success = bot_manager.start()
        
        if success:
            return jsonify({'message': 'Bot started successfully', 'status': 'running'})
        else:
            return jsonify({'error': 'Failed to start bot'}), 400
            
    except Exception as e:
        logging.error(f"Error starting bot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop the trading bot"""
    try:
        bot_manager = app.bot_manager
        success = bot_manager.stop()
        
        if success:
            return jsonify({'message': 'Bot stopped successfully', 'status': 'stopped'})
        else:
            return jsonify({'error': 'Failed to stop bot'}), 400
            
    except Exception as e:
        logging.error(f"Error stopping bot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pause', methods=['POST'])
def api_pause():
    """Pause the trading bot"""
    try:
        bot_manager = app.bot_manager
        success = bot_manager.pause()
        
        if success:
            return jsonify({'message': 'Bot paused successfully', 'status': 'paused'})
        else:
            return jsonify({'error': 'Failed to pause bot'}), 400
            
    except Exception as e:
        logging.error(f"Error pausing bot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resume', methods=['POST'])
def api_resume():
    """Resume the trading bot"""
    try:
        bot_manager = app.bot_manager
        success = bot_manager.resume()
        
        if success:
            return jsonify({'message': 'Bot resumed successfully', 'status': 'running'})
        else:
            return jsonify({'error': 'Failed to resume bot'}), 400
            
    except Exception as e:
        logging.error(f"Error resuming bot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """Get or update bot configuration"""
    if request.method == 'GET':
        try:
            configs = BotConfig.query.all()
            config_dict = {config.key: config.value for config in configs}
            return jsonify(config_dict)
            
        except Exception as e:
            logging.error(f"Error getting config: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Update configurations
            for key, value in data.items():
                BotConfig.set_value(key, value)
            
            return jsonify({'message': 'Configuration updated successfully'})
            
        except Exception as e:
            logging.error(f"Error updating config: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/market-data')
def api_market_data():
    """Get current market data and analysis"""
    try:
        from market_analyzer import MarketAnalyzer
        
        analyzer = MarketAnalyzer()
        symbol = request.args.get('symbol', 'BTC-USDT')
        
        analysis = analyzer.analyze_market(symbol)
        if not analysis:
            return jsonify({'error': 'Failed to get market data'}), 500
        
        return jsonify(analysis)
        
    except Exception as e:
        logging.error(f"Error getting market data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def api_logs():
    """Get recent bot logs"""
    try:
        limit = request.args.get('limit', 50, type=int)
        level = request.args.get('level', None)
        
        query = BotLog.query
        if level:
            query = query.filter(BotLog.level == level.upper())
        
        logs = query.order_by(BotLog.timestamp.desc()).limit(limit).all()
        
        return jsonify([log.to_dict() for log in logs])
        
    except Exception as e:
        logging.error(f"Error getting logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades')
def api_trades():
    """Get trade history with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', None)
        
        query = Trade.query
        if status:
            query = query.filter(Trade.status == status)
        
        trades = query.order_by(Trade.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'trades': [trade.to_dict() for trade in trades.items],
            'total': trades.total,
            'pages': trades.pages,
            'current_page': trades.page,
            'has_next': trades.has_next,
            'has_prev': trades.has_prev
        })
        
    except Exception as e:
        logging.error(f"Error getting trades: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('dashboard.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('dashboard.html'), 500
