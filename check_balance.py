#!/usr/bin/env python3
"""
Check Balance and Trading Status - Comprehensive account analysis
"""
import os
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BalanceChecker:
    def __init__(self):
        self.api_key = str(os.environ.get('OKX_API_KEY', ''))
        self.secret_key = str(os.environ.get('OKX_SECRET_KEY', ''))
        self.passphrase = str(os.environ.get('OKX_PASSPHRASE', ''))
        self.base_url = 'https://www.okx.com'
    
    def get_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def create_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        message = timestamp + method + path + body
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(self, method: str, path: str, body: str = '') -> dict:
        timestamp = self.get_timestamp()
        signature = self.create_signature(timestamp, method, path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def api_request(self, method: str, endpoint: str, body: str = None):
        url = self.base_url + endpoint
        headers = self.get_headers(method, endpoint, body or '')
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=15)
            
            return response
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def check_comprehensive_status(self):
        """Check all account details and trading status"""
        logger.info("COMPREHENSIVE ACCOUNT STATUS CHECK")
        logger.info("=" * 50)
        
        # Check balance
        logger.info("1. Checking account balance...")
        balance_response = self.api_request('GET', '/api/v5/account/balance')
        if balance_response and balance_response.status_code == 200:
            data = balance_response.json()
            if data.get('code') == '0':
                logger.info("✓ Balance API working")
                for detail in data['data'][0]['details']:
                    if detail['ccy'] == 'USDT':
                        balance = float(detail['availBal'])
                        logger.info(f"USDT Balance: ${balance:.8f}")
                        break
            else:
                logger.error(f"Balance API error: {data.get('msg')}")
        
        # Check account configuration
        logger.info("\n2. Checking account configuration...")
        config_response = self.api_request('GET', '/api/v5/account/config')
        if config_response and config_response.status_code == 200:
            data = config_response.json()
            if data.get('code') == '0':
                config = data['data'][0]
                logger.info(f"Account Level: {config.get('acctLv')}")
                logger.info(f"Position Mode: {config.get('posMode')}")
                logger.info(f"Auto Borrow: {config.get('autoBorrow')}")
                logger.info(f"Greeks Type: {config.get('greeksType')}")
            else:
                logger.error(f"Config API error: {data.get('msg')}")
        
        # Check trading permissions
        logger.info("\n3. Checking trading permissions...")
        try:
            # Test with smallest possible order on MEME-USDT
            test_order = {
                "instId": "MEME-USDT",
                "tdMode": "cash",
                "side": "buy",
                "ordType": "market",
                "sz": "100"  # Minimum size
            }
            
            test_body = json.dumps(test_order)
            test_response = self.api_request('POST', '/api/v5/trade/order', test_body)
            
            if test_response:
                logger.info(f"Test order response status: {test_response.status_code}")
                if test_response.status_code == 200:
                    result = test_response.json()
                    logger.info(f"Test order result: {result}")
                    if result.get('code') == '0':
                        logger.info("✓ Trading permissions confirmed")
                        # Cancel the test order if it went through
                        order_id = result['data'][0]['ordId']
                        cancel_data = {"instId": "MEME-USDT", "ordId": order_id}
                        cancel_body = json.dumps(cancel_data)
                        self.api_request('POST', '/api/v5/trade/cancel-order', cancel_body)
                    else:
                        logger.warning(f"Trading restriction: {result.get('msg')}")
                else:
                    logger.warning(f"Trading API error: {test_response.status_code}")
        except Exception as e:
            logger.error(f"Trading test failed: {e}")
        
        # Check account max available
        logger.info("\n4. Checking maximum buy power...")
        max_response = self.api_request('GET', '/api/v5/account/max-avail-size?instId=MEME-USDT&tdMode=cash')
        if max_response and max_response.status_code == 200:
            data = max_response.json()
            if data.get('code') == '0':
                max_data = data['data'][0]
                logger.info(f"Max available for MEME-USDT: {max_data}")
            else:
                logger.error(f"Max avail API error: {data.get('msg')}")
        
        # Check positions
        logger.info("\n5. Checking current positions...")
        pos_response = self.api_request('GET', '/api/v5/account/positions')
        if pos_response and pos_response.status_code == 200:
            data = pos_response.json()
            if data.get('code') == '0':
                positions = data['data']
                if positions:
                    logger.info(f"Current positions: {len(positions)}")
                    for pos in positions[:5]:  # Show first 5
                        logger.info(f"  {pos['instId']}: {pos['pos']} @ {pos['avgPx']}")
                else:
                    logger.info("No open positions")
            else:
                logger.error(f"Positions API error: {data.get('msg')}")

def main():
    checker = BalanceChecker()
    checker.check_comprehensive_status()

if __name__ == "__main__":
    main()