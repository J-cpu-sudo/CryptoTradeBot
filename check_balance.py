import os
import time
import hmac
import hashlib
import base64
import requests
from datetime import datetime

def get_okx_balance():
    """Get actual account balance from OKX using API credentials"""
    
    # API credentials
    api_key = "f43547e4-0331-4114-881a-c92b9e4d7d95"
    secret_key = "0E1161EECD34F8FB117F4D1A06587AF8"
    passphrase = "Kongoni3491$"
    
    # API endpoint
    endpoint = "/api/v5/account/balance"
    method = "GET"
    timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
    
    # Create signature
    message = timestamp + method + endpoint
    signature = base64.b64encode(
        hmac.new(
            secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
    ).decode('utf-8')
    
    # Headers
    headers = {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }
    
    try:
        # Make request
        url = "https://www.okx.com" + endpoint
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == '0':
                balances = data.get('data', [])
                if balances:
                    account_data = balances[0]
                    details = account_data.get('details', [])
                    
                    print("=== OKX Account Balance ===")
                    total_equity = float(account_data.get('totalEq', 0))
                    print(f"Total Equity: ${total_equity:.2f} USDT")
                    
                    print("\nCurrency Breakdown:")
                    for detail in details:
                        currency = detail.get('ccy', '')
                        balance = float(detail.get('cashBal', 0))
                        if balance > 0:
                            print(f"{currency}: {balance:.6f}")
                    
                    return total_equity
                else:
                    print("No balance data found")
                    return 0
            else:
                print(f"API Error: {data.get('msg', 'Unknown error')}")
                return None
        else:
            print(f"HTTP Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"Error checking balance: {e}")
        return None

if __name__ == "__main__":
    balance = get_okx_balance()