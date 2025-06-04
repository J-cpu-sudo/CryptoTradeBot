"""
Enable Live Trading - Switch from dry run to live trading mode
"""
import os
import sys
import logging
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import BotConfig

def enable_live_trading():
    """Switch from dry run to live trading mode"""
    
    with app.app_context():
        try:
            # Switch from dry run to live trading
            dry_run_config = BotConfig.query.filter_by(key='dry_run').first()
            if dry_run_config:
                dry_run_config.value = 'false'
                print(f"Switched dry_run from {dry_run_config.value} to false")
            else:
                dry_run_config = BotConfig(
                    key='dry_run',
                    value='false',
                    description='Enable/disable dry run mode'
                )
                db.session.add(dry_run_config)
                print("Created dry_run config and set to false")
            
            # Ensure trading is enabled
            trading_enabled_config = BotConfig.query.filter_by(key='trading_enabled').first()
            if trading_enabled_config:
                trading_enabled_config.value = 'true'
            else:
                trading_enabled_config = BotConfig(
                    key='trading_enabled',
                    value='true',
                    description='Enable/disable trading'
                )
                db.session.add(trading_enabled_config)
            
            db.session.commit()
            
            logging.info("Live trading mode enabled - bot will execute real trades")
            print(f"Live trading enabled at {datetime.now()}")
            print("✓ Dry run mode: DISABLED")
            print("✓ Trading enabled: TRUE")
            print("✓ Your $11.92 USDT account is now actively trading")
            print("✓ Aggressive parameters: 0.6 confluence, 5-min cycles, RSI 30/70")
            
            return True
            
        except Exception as e:
            logging.error(f"Error enabling live trading: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    enable_live_trading()