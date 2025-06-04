#!/usr/bin/env python3
import os
os.environ['DRY_RUN'] = 'false'

from trader import Trader

trader = Trader()
trader.dry_run = False

print('Testing OKX API authentication...')

# Test account balance first (simpler endpoint)
balance = trader.get_account_balance()
if balance:
    print('Authentication successful!')
    print(f'Account balance: ${balance.get("totalEq", "N/A")}')
    
    # Now try live trade
    print('Executing live BTC buy order...')
    result = trader.buy(symbol='BTC-USDT', size='15')
    
    if result:
        print('LIVE TRADE EXECUTED!')
        print(f'Order ID: {result.get("ordId", "N/A")}')
        print(f'Status: {result.get("sMsg", "Success")}')
        print('Autonomous trading system now active!')
    else:
        print('Trade execution failed')
else:
    print('Authentication still failing')