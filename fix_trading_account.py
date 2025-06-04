#!/usr/bin/env python3
"""
Fix OKX trading account setup for live trading
"""
import os
import time
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime

class OKXAccountFixer:
    def __init__(self):
        self.api_key = os.getenv('OKX_API_KEY')
        self.secret_key = os.getenv('OKX_SECRET_KEY') 
        self.passphrase = os.getenv('OKX_PASSPHRASE')
        self.base_url = 'https://www.okx.com'
        
    def _generate_signature(self, timestamp, method, request_path, body=''):
        """Generate OKX API signature"""
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()

    def _get_headers(self, method, request_path, body=''):
        """Get headers for OKX API request"""
        timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
        signature = self._generate_signature(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }

    def get_account_info(self):
        """Get detailed account information"""
        try:
            path = '/api/v5/account/balance'
            headers = self._get_headers('GET', path)
            
            response = requests.get(self.base_url + path, headers=headers)
            result = response.json()
            
            if result.get('code') == '0':
                print("✅ Account Balance Information:")
                for balance_info in result.get('data', []):
                    total_eq = balance_info.get('totalEq', '0')
                    adj_eq = balance_info.get('adjEq', '0')
                    print(f"   Total Equity: ${total_eq}")
                    print(f"   Adjusted Equity: ${adj_eq}")
                    
                    details = balance_info.get('details', [])
                    for detail in details:
                        if float(detail.get('cashBal', '0')) > 0:
                            currency = detail.get('ccy')
                            cash_bal = detail.get('cashBal')
                            avail_bal = detail.get('availBal')
                            print(f"   {currency}: Cash=${cash_bal}, Available=${avail_bal}")
                
                return result
            else:
                print(f"❌ Failed to get account info: {result}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting account info: {e}")
            return None

    def get_trading_settings(self):
        """Get account trading settings"""
        try:
            path = '/api/v5/account/config'
            headers = self._get_headers('GET', path)
            
            response = requests.get(self.base_url + path, headers=headers)
            result = response.json()
            
            if result.get('code') == '0':
                print("✅ Account Configuration:")
                config = result.get('data', [{}])[0]
                print(f"   Account Level: {config.get('acctLv')}")
                print(f"   Position Mode: {config.get('posMode')}")
                print(f"   Account Type: {config.get('mainUid')}")
                return result
            else:
                print(f"❌ Failed to get trading settings: {result}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting trading settings: {e}")
            return None

    def enable_spot_trading(self):
        """Enable spot trading mode"""
        try:
            # Set account to simple trading mode for spot trading
            path = '/api/v5/account/set-position-mode'
            body = json.dumps({"posMode": "long_short_mode"})
            headers = self._get_headers('POST', path, body)
            
            response = requests.post(self.base_url + path, headers=headers, data=body)
            result = response.json()
            
            print(f"Position mode setup: {result}")
            return result
            
        except Exception as e:
            print(f"❌ Error setting position mode: {e}")
            return None

    def place_small_test_order(self):
        """Place a very small test order to verify trading capability"""
        try:
            # Get current BTC price first
            price_response = requests.get('https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT')
            price_data = price_response.json()
            current_price = float(price_data['data'][0]['last'])
            
            # Calculate minimum order size (around $5-10 worth)
            min_order_value = 10.0  # $10 minimum
            quantity = round(min_order_value / current_price, 6)
            
            path = '/api/v5/trade/order'
            body = json.dumps({
                "instId": "BTC-USDT",
                "tdMode": "cash",  # Spot trading mode
                "side": "buy",
                "ordType": "market",
                "sz": str(quantity)
            })
            
            headers = self._get_headers('POST', path, body)
            
            response = requests.post(self.base_url + path, headers=headers, data=body)
            result = response.json()
            
            if result.get('code') == '0':
                print(f"✅ Test order placed successfully!")
                print(f"   Order ID: {result['data'][0]['ordId']}")
                print(f"   Quantity: {quantity} BTC")
                print(f"   Value: ~${min_order_value}")
                return True
            else:
                print(f"❌ Test order failed: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Error placing test order: {e}")
            return False

    def fix_account_setup(self):
        """Complete account setup process"""
        print("🔧 Analyzing OKX account setup...")
        
        # Step 1: Get account info
        account_info = self.get_account_info()
        if not account_info:
            return False
            
        # Step 2: Get trading settings
        settings = self.get_trading_settings()
        if not settings:
            return False
            
        # Step 3: Enable trading modes
        self.enable_spot_trading()
        time.sleep(1)
        
        # Step 4: Test with small order
        success = self.place_small_test_order()
        
        if success:
            print("🎉 Account setup complete! Live trading enabled.")
            return True
        else:
            print("⚠️  Manual account configuration may be required.")
            return False

if __name__ == "__main__":
    fixer = OKXAccountFixer()
    fixer.fix_account_setup()