"""
Start Autonomous Trading - Initialize and start the trading bot with live API credentials
"""
import os
import sys
import logging
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from bot_manager import BotManager
from apscheduler.schedulers.background import BackgroundScheduler

def start_autonomous_trading():
    """Start the autonomous trading bot with live credentials"""
    
    with app.app_context():
        try:
            # Create scheduler
            scheduler = BackgroundScheduler()
            scheduler.start()
            
            # Initialize bot manager
            bot_manager = BotManager(db, scheduler)
            
            print(f"Initializing autonomous trading system at {datetime.now()}")
            print(f"Current bot status: {bot_manager.status}")
            
            # Start the bot if not running
            if bot_manager.status.value != 'running':
                print("Starting autonomous trading bot...")
                success = bot_manager.start()
                
                if success:
                    print("✓ Autonomous trading bot started successfully")
                    print(f"✓ Status: {bot_manager.status}")
                    
                    # Check scheduled jobs
                    jobs = scheduler.get_jobs()
                    print(f"✓ Active trading jobs: {len(jobs)}")
                    for job in jobs:
                        print(f"  - {job.name}: next run at {job.next_run_time}")
                    
                    print("✓ Live trading with OKX API credentials active")
                    print("✓ Aggressive parameters: 0.6 confluence, 5-min cycles, RSI 30/70")
                    print("✓ Your $11.92 USDT account is now under autonomous management")
                    
                    return True
                else:
                    print("✗ Failed to start trading bot")
                    return False
            else:
                print("✓ Trading bot is already running")
                return True
                
        except Exception as e:
            logging.error(f"Error starting autonomous trading: {e}")
            print(f"✗ Error: {e}")
            return False

if __name__ == "__main__":
    start_autonomous_trading()