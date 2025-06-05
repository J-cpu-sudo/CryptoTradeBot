#!/usr/bin/env python3
"""
Test Authentication - Verify API credentials and trading status
"""
import os
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone

def test_authentication():
    api_key = str(os.environ.get('OKX_API_KEY', ''))
    secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
    passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
    
    def get_timestamp():
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def create_signature(timestamp, method, path, body=''):
        message = timestamp + method + path + body
        signature = hmac.new(
            secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    timestamp = get_timestamp()
    path = '/api/v5/account/balance'
    signature = create_signature(timestamp, 'GET', path)
    
    headers = {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }
    
    print("Testing API authentication...")
    print(f"API Key present: {'Yes' if api_key else 'No'}")
    print(f"Secret Key present: {'Yes' if secret_key else 'No'}")
    print(f"Passphrase present: {'Yes' if passphrase else 'No'}")
    
    try:
        response = requests.get('https://www.okx.com/api/v5/account/balance', headers=headers, timeout=10)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"API Response: {data}")
            if data.get('code') == '0':
                print("✓ Authentication successful")
                for detail in data['data'][0]['details']:
                    if detail['ccy'] == 'USDT':
                        balance = float(detail['availBal'])
                        print(f"USDT Balance: ${balance:.8f}")
            else:
                print(f"API Error: {data.get('msg')}")
        else:
            print(f"HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_authentication()