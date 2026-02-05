#!/usr/bin/env python3
"""
Fear & Greed Index API Validation Script
Tests all primary sentiment APIs and saves sample responses
"""

import requests
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Create samples directory if it doesn't exist
SAMPLES_DIR = "../samples"
os.makedirs(SAMPLES_DIR, exist_ok=True)

class FearGreedValidator:
    def __init__(self):
        self.results = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'crypto-sentiment-validator/1.0'
        })
    
    def validate_alternative_me(self) -> Tuple[bool, Dict]:
        """Validate Alternative.me Fear & Greed Index API"""
        print("🔍 Testing Alternative.me Fear & Greed Index...")
        
        try:
            # Test current index
            url = "https://api.alternative.me/fng/"
            params = {'limit': 7, 'format': 'json'}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response structure
            required_fields = ['name', 'data', 'metadata']
            if not all(field in data for field in required_fields):
                raise ValueError(f"Missing required fields: {required_fields}")
            
            # Validate data entries
            if not data['data'] or len(data['data']) == 0:
                raise ValueError("No data entries found")
            
            latest = data['data'][0]
            required_data_fields = ['value', 'value_classification', 'timestamp']
            if not all(field in latest for field in required_data_fields):
                raise ValueError(f"Missing data fields: {required_data_fields}")
            
            # Validate value range (0-100)
            value = int(latest['value'])
            if not 0 <= value <= 100:
                raise ValueError(f"Invalid fear/greed value: {value}")
            
            # Save sample data
            sample_file = os.path.join(SAMPLES_DIR, "fear_greed_alternative_sample.json")
            with open(sample_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Display results
            timestamp = datetime.fromtimestamp(int(latest['timestamp']))
            print(f"✅ Alternative.me API Status: OK")
            print(f"📊 Current Fear & Greed: {latest['value']} ({latest['value_classification']})")
            print(f"⏰ Last Update: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"📁 Sample saved: {sample_file}")
            
            return True, {
                'endpoint': url,
                'current_value': latest['value'],
                'classification': latest['value_classification'],
                'last_update': timestamp.isoformat(),
                'data_points': len(data['data']),
                'sample_file': sample_file
            }
            
        except Exception as e:
            print(f"❌ Alternative.me API Error: {e}")
            return False, {'error': str(e)}
    
    def validate_cryptometer(self) -> Tuple[bool, Dict]:
        """Validate CryptoMeter API (requires API key)"""
        print("\n🔍 Testing CryptoMeter Trend Indicator...")
        
        api_key = os.getenv('CRYPTOMETER_API_KEY')
        if not api_key:
            print("⚠️  CryptoMeter: CRYPTOMETER_API_KEY environment variable not set")
            print("   Get API key from: https://cryptometer.io/api")
            return False, {'error': 'API key required'}
        
        try:
            url = "https://api.cryptometer.io/trend-indicator-v3/"
            headers = {'api_key': api_key}
            
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response structure
            if 'data' not in data or not data['data']:
                raise ValueError("Invalid response structure")
            
            latest = data['data'][0] if isinstance(data['data'], list) else data['data']
            
            # Save sample data
            sample_file = os.path.join(SAMPLES_DIR, "fear_greed_cryptometer_sample.json")
            with open(sample_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ CryptoMeter API Status: OK")
            if 'trend_score' in latest:
                print(f"📈 Trend Score: {latest['trend_score']}")
            if 'sentiment' in latest:
                print(f"💭 Sentiment: {latest['sentiment']}")
            print(f"📁 Sample saved: {sample_file}")
            
            return True, {
                'endpoint': url,
                'data_structure': list(latest.keys()) if latest else [],
                'sample_file': sample_file
            }
            
        except Exception as e:
            print(f"❌ CryptoMeter API Error: {e}")
            return False, {'error': str(e)}
    
    def validate_coinybubble(self) -> Tuple[bool, Dict]:
        """Validate CoinyBubble Fear & Greed Index"""
        print("\n🔍 Testing CoinyBubble Fear & Greed Index...")
        
        try:
            url = "https://api.coinybubble.com/api/v1/fear-greed-index"
            params = {'period': '1d'}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Save sample data
            sample_file = os.path.join(SAMPLES_DIR, "fear_greed_coinybubble_sample.json")
            with open(sample_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ CoinyBubble API Status: OK")
            
            # Try to extract meaningful data
            if isinstance(data, dict):
                if 'index_value' in data:
                    print(f"📊 Current Index: {data['index_value']}")
                if 'classification' in data:
                    print(f"📈 Classification: {data['classification']}")
            
            print(f"📁 Sample saved: {sample_file}")
            
            return True, {
                'endpoint': url,
                'response_keys': list(data.keys()) if isinstance(data, dict) else 'list',
                'sample_file': sample_file
            }
            
        except Exception as e:
            print(f"❌ CoinyBubble API Error: {e}")
            return False, {'error': str(e)}
    
    def validate_senticrypt(self) -> Tuple[bool, Dict]:
        """Validate SentiCrypt API"""
        print("\n🔍 Testing SentiCrypt Sentiment API...")
        
        try:
            # Test current data
            url = "https://api.senticrypt.com/v2/all.json"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Save sample data
            sample_file = os.path.join(SAMPLES_DIR, "fear_greed_senticrypt_sample.json")
            with open(sample_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ SentiCrypt API Status: OK")
            
            # Display data info
            if isinstance(data, dict):
                data_keys = list(data.keys())
                print(f"📊 Available data keys: {data_keys[:5]}{'...' if len(data_keys) > 5 else ''}")
                
                # Look for recent sentiment data
                for key in ['sentiment', 'score', 'value']:
                    if key in data:
                        print(f"📈 {key.title()}: {data[key]}")
                        break
            
            print(f"📁 Sample saved: {sample_file}")
            
            return True, {
                'endpoint': url,
                'data_type': type(data).__name__,
                'data_size': len(data) if isinstance(data, (dict, list)) else 'unknown',
                'sample_file': sample_file
            }
            
        except Exception as e:
            print(f"❌ SentiCrypt API Error: {e}")
            return False, {'error': str(e)}
    
    def run_all_validations(self) -> Dict:
        """Run all fear & greed validations and return summary"""
        print("🚀 Starting Fear & Greed Index API Validation\n")
        
        validations = [
            ('alternative_me', self.validate_alternative_me),
            ('cryptometer', self.validate_cryptometer),
            ('coinybubble', self.validate_coinybubble),
            ('senticrypt', self.validate_senticrypt)
        ]
        
        results = {}
        successful = 0
        
        for name, validator in validations:
            success, data = validator()
            results[name] = {
                'success': success,
                'data': data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            if success:
                successful += 1
            
            # Add delay between requests
            time.sleep(1)
        
        # Summary
        print(f"\n📋 VALIDATION SUMMARY")
        print(f"{'='*50}")
        print(f"✅ Successful APIs: {successful}/{len(validations)}")
        print(f"❌ Failed APIs: {len(validations) - successful}/{len(validations)}")
        
        # Status breakdown
        for name, result in results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"   {name.replace('_', ' ').title()}: {status}")
        
        if successful >= 1:
            print(f"\n🎉 Primary sentiment data sources validated successfully!")
            print(f"💡 Recommendation: Use Alternative.me as primary, others as backup")
        else:
            print(f"\n⚠️  Warning: No sentiment APIs validated successfully")
        
        # Save validation report
        report_file = os.path.join(SAMPLES_DIR, "fear_greed_validation_report.json")
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"📊 Full report saved: {report_file}")
        
        return results

def main():
    """Main validation function"""
    try:
        validator = FearGreedValidator()
        results = validator.run_all_validations()
        
        # Exit with proper code
        successful_count = sum(1 for r in results.values() if r['success'])
        if successful_count == 0:
            exit(1)  # All validations failed
        elif successful_count < len(results):
            exit(2)  # Some validations failed
        else:
            exit(0)  # All validations passed
            
    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        exit(1)

if __name__ == "__main__":
    main()