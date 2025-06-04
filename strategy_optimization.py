"""
Strategy Optimization - Switch to aggressive mode for current market volatility
"""
import os
import sys
import logging
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from advanced_strategy_engine import AdvancedStrategyEngine, StrategyMode
from app import app, db
from models import BotConfig

def optimize_strategy_for_volatility():
    """Switch to aggressive trading mode to capture current market opportunities"""
    
    with app.app_context():
        try:
            # Update strategy mode to aggressive
            strategy_mode_config = BotConfig.query.filter_by(key='strategy_mode').first()
            if not strategy_mode_config:
                strategy_mode_config = BotConfig(
                    key='strategy_mode',
                    value='aggressive',
                    description='Current strategy mode'
                )
                db.session.add(strategy_mode_config)
            else:
                strategy_mode_config.value = 'aggressive'
            
            # Update confluence requirements
            confluence_config = BotConfig.query.filter_by(key='min_confluence_score').first()
            if not confluence_config:
                confluence_config = BotConfig(
                    key='min_confluence_score',
                    value='0.6',
                    description='Minimum confluence score for trades'
                )
                db.session.add(confluence_config)
            else:
                confluence_config.value = '0.6'
            
            # Update volume requirements
            volume_config = BotConfig.query.filter_by(key='min_volume_ratio').first()
            if not volume_config:
                volume_config = BotConfig(
                    key='min_volume_ratio',
                    value='1.5',
                    description='Minimum volume ratio for trades'
                )
                db.session.add(volume_config)
            else:
                volume_config.value = '1.5'
            
            # Update risk-reward requirements
            risk_reward_config = BotConfig.query.filter_by(key='min_risk_reward').first()
            if not risk_reward_config:
                risk_reward_config = BotConfig(
                    key='min_risk_reward',
                    value='1.5',
                    description='Minimum risk-reward ratio'
                )
                db.session.add(risk_reward_config)
            else:
                risk_reward_config.value = '1.5'
            
            # Enable aggressive RSI levels
            rsi_oversold_config = BotConfig.query.filter_by(key='rsi_oversold_level').first()
            if not rsi_oversold_config:
                rsi_oversold_config = BotConfig(
                    key='rsi_oversold_level',
                    value='30',
                    description='RSI oversold level for buy signals'
                )
                db.session.add(rsi_oversold_config)
            else:
                rsi_oversold_config.value = '30'
            
            rsi_overbought_config = BotConfig.query.filter_by(key='rsi_overbought_level').first()
            if not rsi_overbought_config:
                rsi_overbought_config = BotConfig(
                    key='rsi_overbought_level',
                    value='70',
                    description='RSI overbought level for sell signals'
                )
                db.session.add(rsi_overbought_config)
            else:
                rsi_overbought_config.value = '70'
            
            # Reduce signal cooldown for faster trading
            cooldown_config = BotConfig.query.filter_by(key='signal_cooldown_minutes').first()
            if not cooldown_config:
                cooldown_config = BotConfig(
                    key='signal_cooldown_minutes',
                    value='5',
                    description='Minutes between trading signals'
                )
                db.session.add(cooldown_config)
            else:
                cooldown_config.value = '5'
            
            db.session.commit()
            
            logging.info("Strategy optimized for aggressive trading in high volatility market")
            print(f"Strategy optimization complete at {datetime.now()}")
            print("Switched to AGGRESSIVE mode with:")
            print("- Confluence score: 0.6 (was 0.8)")
            print("- Volume ratio: 1.5 (was 2.0)")
            print("- Risk-reward: 1.5 (was 2.0)")
            print("- RSI levels: 30/70 (was 25/75)")
            print("- Signal cooldown: 5 min (was 15 min)")
            
            return True
            
        except Exception as e:
            logging.error(f"Error optimizing strategy: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    optimize_strategy_for_volatility()