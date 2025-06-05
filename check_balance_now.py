import os
import requests
import hmac
import hashlib
import base64
from datetime import datetime, timezone

api_key = os.environ.get('OKX_API_KEY')
secret_key = os.environ.get('OKX_SECRET_KEY')
passphrase = os.environ.get('OKX_PASSPHRASE')

def get_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def create_signature(timestamp, method, path, body=''):
    message = timestamp + method + path + body
    signature = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(signature).decode('utf-8')

def api_request(method, endpoint, body=None):
    timestamp = get_timestamp()
    signature = create_signature(timestamp, method, endpoint, body or '')
    
    headers = {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }
    
    url = 'https://www.okx.com' + endpoint
    response = requests.get(url, headers=headers)
    return response.json()

# Check current balance
balance_data = api_request('GET', '/api/v5/account/balance')
print(f"Balance response: {balance_data}")

if balance_data.get('code') == '0':
    for detail in balance_data['data'][0]['details']:
        if detail['ccy'] == 'USDT':
            print(f'Current USDT Balance: ${float(detail["availBal"]):.2f}')
else:
    print('Authentication error - API credentials may need updating')