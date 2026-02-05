#!/usr/bin/env python3
"""
Advanced Sentiment APIs Validation Script
Tests CoinGecko, Alpha Vantage, LunarCrush, and other sentiment analysis APIs
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

class SentimentAPIException(Exception):
    """Custom exception for sentiment API validation errors"""
    pass

class SentimentAPIValidator:
    def __init__(self):
        self.results = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'crypto-sentiment-validator/1.0'
        })
    
    def validate_coingecko_api(self) -> Tuple[bool, Dict]:
        """Validate CoinGecko API for sentiment and market data"""
        print("🔍 Testing CoinGecko API...")
        
        api_key = os.getenv('COINGECKO_API_KEY')
        
        try:
            base_url = "https://api.coingecko.com/api/v3"
            headers = {}
            
            if api_key:
                headers['x-cg-pro-api-key'] = api_key
                print("  🔑 Using Pro API key")
            else:
                print("  🆓 Using free tier (no API key)")
            
            results = {}
            
            # Test 1: Global market data with sentiment indicators
            print("  🌍 Testing global market data...")
            global_url = f"{base_url}/global"
            
            global_response = self.session.get(global_url, headers=headers, timeout=10)
            global_response.raise_for_status()
            
            global_data = global_response.json()
            
            if 'data' not in global_data:
                raise SentimentAPIException("Invalid global data response")
            
            market_data = global_data['data']
            market_cap_change = market_data.get('market_cap_change_percentage_24h_usd', 0)
            
            print(f"    ✅ Global market cap change 24h: {market_cap_change:.2f}%")
            print(f"    📊 Active cryptocurrencies: {market_data.get('active_cryptocurrencies', 'N/A'):,}")
            
            results['global_data'] = {
                'market_cap_change_24h': market_cap_change,
                'active_cryptocurrencies': market_data.get('active_cryptocurrencies', 0),
                'market_cap_percentage': market_data.get('market_cap_percentage', {}),
                'total_market_cap': market_data.get('total_market_cap', {})
            }
            
            # Test 2: Trending coins (sentiment indicator)
            print("  📈 Testing trending search...")
            trending_url = f"{base_url}/search/trending"
            
            trending_response = self.session.get(trending_url, headers=headers, timeout=10)
            trending_response.raise_for_status()
            
            trending_data = trending_response.json()
            
            if 'coins' in trending_data:
                trending_coins = [coin['item']['name'] for coin in trending_data['coins'][:5]]
                print(f"    ✅ Top trending: {', '.join(trending_coins)}")
                
                results['trending'] = {
                    'top_coins': trending_coins,
                    'total_trending': len(trending_data['coins'])
                }
            
            # Test 3: Specific coin data with social metrics
            print("  🪙 Testing Bitcoin social metrics...")
            btc_url = f"{base_url}/coins/bitcoin"
            btc_params = {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'true',
                'developer_data': 'false'
            }
            
            btc_response = self.session.get(btc_url, headers=headers, params=btc_params, timeout=10)
            btc_response.raise_for_status()
            
            btc_data = btc_response.json()
            
            if 'community_data' in btc_data:
                community = btc_data['community_data']
                print(f"    ✅ BTC Reddit subscribers: {community.get('reddit_subscribers', 'N/A'):,}")
                print(f"    📱 BTC Twitter followers: {community.get('twitter_followers', 'N/A'):,}")
                
                results['bitcoin_social'] = {
                    'reddit_subscribers': community.get('reddit_subscribers', 0),
                    'twitter_followers': community.get('twitter_followers', 0),
                    'reddit_average_posts_48h': community.get('reddit_average_posts_48h', 0),
                    'reddit_average_comments_48h': community.get('reddit_average_comments_48h', 0)
                }
            
            # Save sample data
            sample_file = os.path.join(SAMPLES_DIR, "sentiment_coingecko_sample.json")
            with open(sample_file, 'w') as f:
                json.dump({
                    'global_data': global_data,
                    'trending_data': trending_data,
                    'bitcoin_social': btc_data.get('community_data', {}),
                    'validation_time': datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
            
            results['sample_file'] = sample_file
            print(f"    📁 Sample saved: {sample_file}")
            
            print(f"✅ CoinGecko API Status: OK")
            return True, results
            
        except Exception as e:
            print(f"❌ CoinGecko API Error: {e}")
            return False, {'error': str(e)}
    
    def validate_alpha_vantage_api(self) -> Tuple[bool, Dict]:
        """Validate Alpha Vantage News Sentiment API"""
        print("\n🔍 Testing Alpha Vantage API...")
        
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not api_key:
            print("⚠️  Alpha Vantage: ALPHA_VANTAGE_API_KEY environment variable not set")
            print("   Get API key from: https://www.alphavantage.co/support/#api-key")
            return False, {'error': 'API key required'}
        
        try:
            base_url = "https://www.alphavantage.co/query"
            results = {}
            
            # Test 1: News sentiment for crypto
            print("  📰 Testing news sentiment...")
            sentiment_params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': 'CRYPTO:BTC,CRYPTO:ETH',
                'limit': 20,
                'apikey': api_key
            }
            
            sentiment_response = self.session.get(base_url, params=sentiment_params, timeout=15)
            sentiment_response.raise_for_status()
            
            sentiment_data = sentiment_response.json()
            
            if 'Error Message' in sentiment_data:
                raise SentimentAPIException(f"API Error: {sentiment_data['Error Message']}")
            
            if 'Note' in sentiment_data:
                raise SentimentAPIException(f"Rate limit: {sentiment_data['Note']}")
            
            if 'feed' not in sentiment_data:
                raise SentimentAPIException("No news feed data returned")
            
            news_items = sentiment_data['feed']
            print(f"    ✅ Retrieved {len(news_items)} news items")
            
            # Analyze sentiment scores
            btc_sentiments = []
            eth_sentiments = []
            
            for item in news_items[:10]:  # Analyze first 10 items
                if 'ticker_sentiment' in item:
                    for ticker in item['ticker_sentiment']:
                        if ticker.get('ticker') == 'CRYPTO:BTC':
                            btc_sentiments.append(float(ticker.get('sentiment_score', 0)))
                        elif ticker.get('ticker') == 'CRYPTO:ETH':
                            eth_sentiments.append(float(ticker.get('sentiment_score', 0)))
            
            avg_btc_sentiment = sum(btc_sentiments) / len(btc_sentiments) if btc_sentiments else 0
            avg_eth_sentiment = sum(eth_sentiments) / len(eth_sentiments) if eth_sentiments else 0
            
            print(f"    📊 BTC avg sentiment: {avg_btc_sentiment:.3f} ({len(btc_sentiments)} articles)")
            print(f"    📊 ETH avg sentiment: {avg_eth_sentiment:.3f} ({len(eth_sentiments)} articles)")
            
            results['news_sentiment'] = {
                'total_articles': len(news_items),
                'btc_sentiment_avg': avg_btc_sentiment,
                'eth_sentiment_avg': avg_eth_sentiment,
                'btc_articles_count': len(btc_sentiments),
                'eth_articles_count': len(eth_sentiments)
            }
            
            # Test 2: Crypto rating (if available)
            print("  ⭐ Testing crypto ratings...")
            try:
                rating_params = {
                    'function': 'CRYPTO_RATING',
                    'symbol': 'BTC',
                    'apikey': api_key
                }
                
                rating_response = self.session.get(base_url, params=rating_params, timeout=10)
                rating_response.raise_for_status()
                
                rating_data = rating_response.json()
                
                if 'Crypto Rating' in rating_data:
                    crypto_rating = rating_data['Crypto Rating']
                    print(f"    ✅ BTC Rating: {crypto_rating.get('(3) fcas rating', 'N/A')}")
                    
                    results['crypto_rating'] = {
                        'symbol': 'BTC',
                        'fcas_rating': crypto_rating.get('(3) fcas rating'),
                        'fcas_score': crypto_rating.get('(2) fcas score'),
                        'developer_score': crypto_rating.get('(4) developer score')
                    }
                else:
                    results['crypto_rating'] = {'status': 'not available or rate limited'}
                    
            except Exception as e:
                print(f"    ⚠️  Crypto rating: {e}")
                results['crypto_rating'] = {'error': str(e)}
            
            # Save sample data
            sample_file = os.path.join(SAMPLES_DIR, "sentiment_alphavantage_sample.json")
            with open(sample_file, 'w') as f:
                json.dump({
                    'news_sentiment': sentiment_data,
                    'analysis_results': results,
                    'validation_time': datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
            
            results['sample_file'] = sample_file
            print(f"    📁 Sample saved: {sample_file}")
            
            print(f"✅ Alpha Vantage API Status: OK")
            return True, results
            
        except Exception as e:
            print(f"❌ Alpha Vantage API Error: {e}")
            return False, {'error': str(e)}
    
    def validate_lunarcrush_api(self) -> Tuple[bool, Dict]:
        """Validate LunarCrush Social Intelligence API"""
        print("\n🔍 Testing LunarCrush API...")
        
        api_key = os.getenv('LUNARCRUSH_API_KEY')
        if not api_key:
            print("⚠️  LunarCrush: LUNARCRUSH_API_KEY environment variable not set")
            print("   Get API key from: https://lunarcrush.com/developers")
            return False, {'error': 'API key required'}
        
        try:
            base_url = "https://lunarcrush.com/api3"
            headers = {'Authorization': f'Bearer {api_key}'}
            results = {}
            
            # Test 1: Market overview
            print("  📊 Testing market data...")
            market_url = f"{base_url}/coins"
            market_params = {'symbol': 'BTC,ETH', 'data_points': 1}
            
            market_response = self.session.get(market_url, headers=headers, params=market_params, timeout=10)
            market_response.raise_for_status()
            
            market_data = market_response.json()
            
            if 'data' not in market_data:
                raise SentimentAPIException("Invalid market data response")
            
            coins_data = market_data['data']
            print(f"    ✅ Retrieved data for {len(coins_data)} coins")
            
            for coin in coins_data:
                symbol = coin.get('symbol', 'Unknown')
                social_score = coin.get('social_score', 0)
                print(f"    📈 {symbol} social score: {social_score}")
            
            results['market_data'] = {
                'coins_analyzed': len(coins_data),
                'social_metrics': {coin.get('symbol'): coin.get('social_score', 0) for coin in coins_data}
            }
            
            # Test 2: Social metrics for Bitcoin
            print("  💬 Testing social metrics...")
            try:
                social_url = f"{base_url}/coins/btc/meta"
                
                social_response = self.session.get(social_url, headers=headers, timeout=10)
                social_response.raise_for_status()
                
                social_data = social_response.json()
                
                if 'data' in social_data:
                    btc_social = social_data['data']
                    print(f"    ✅ BTC social volume: {btc_social.get('social_volume', 'N/A')}")
                    print(f"    📱 BTC social score: {btc_social.get('social_score', 'N/A')}")
                    
                    results['btc_social'] = {
                        'social_volume': btc_social.get('social_volume', 0),
                        'social_score': btc_social.get('social_score', 0),
                        'social_dominance': btc_social.get('social_dominance', 0)
                    }
                    
            except Exception as e:
                print(f"    ⚠️  Social metrics: {e}")
                results['btc_social'] = {'error': str(e)}
            
            # Save sample data
            sample_file = os.path.join(SAMPLES_DIR, "sentiment_lunarcrush_sample.json")
            with open(sample_file, 'w') as f:
                json.dump({
                    'market_data': market_data,
                    'analysis_results': results,
                    'validation_time': datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
            
            results['sample_file'] = sample_file
            print(f"    📁 Sample saved: {sample_file}")
            
            print(f"✅ LunarCrush API Status: OK")
            return True, results
            
        except Exception as e:
            print(f"❌ LunarCrush API Error: {e}")
            return False, {'error': str(e)}
    
    def validate_santiment_api(self) -> Tuple[bool, Dict]:
        """Validate Santiment API"""
        print("\n🔍 Testing Santiment API...")
        
        api_key = os.getenv('SANTIMENT_API_KEY')
        if not api_key:
            print("⚠️  Santiment: SANTIMENT_API_KEY environment variable not set")
            print("   Get API key from: https://santiment.net/")
            return False, {'error': 'API key required'}
        
        try:
            url = "https://api.santiment.net/graphql"
            headers = {
                'Authorization': f'Apikey {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Test GraphQL query for social volume
            query = """
            {
              getMetric(metric: "social_volume") {
                timeseriesData(
                  slug: "bitcoin"
                  from: "2024-01-01T00:00:00Z"
                  to: "2024-12-31T23:59:59Z"
                  interval: "1d"
                ) {
                  datetime
                  value
                }
              }
            }
            """
            
            response = self.session.post(url, headers=headers, json={'query': query}, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if 'errors' in data:
                raise SentimentAPIException(f"GraphQL errors: {data['errors']}")
            
            if 'data' in data and data['data']['getMetric']['timeseriesData']:
                timeseries = data['data']['getMetric']['timeseriesData']
                latest_volume = timeseries[-1]['value'] if timeseries else 0
                
                print(f"    ✅ Latest BTC social volume: {latest_volume}")
                print(f"    📊 Data points retrieved: {len(timeseries)}")
                
                # Save sample data
                sample_file = os.path.join(SAMPLES_DIR, "sentiment_santiment_sample.json")
                with open(sample_file, 'w') as f:
                    json.dump({
                        'query_result': data,
                        'latest_social_volume': latest_volume,
                        'data_points': len(timeseries),
                        'validation_time': datetime.now(timezone.utc).isoformat()
                    }, f, indent=2)
                
                print(f"    📁 Sample saved: {sample_file}")
                
                print(f"✅ Santiment API Status: OK")
                return True, {
                    'latest_social_volume': latest_volume,
                    'data_points': len(timeseries),
                    'sample_file': sample_file
                }
            else:
                raise SentimentAPIException("No data returned from query")
                
        except Exception as e:
            print(f"❌ Santiment API Error: {e}")
            return False, {'error': str(e)}
    
    def run_all_validations(self) -> Dict:
        """Run all sentiment API validations and return summary"""
        print("🚀 Starting Advanced Sentiment APIs Validation\n")
        
        validations = [
            ('coingecko', self.validate_coingecko_api),
            ('alpha_vantage', self.validate_alpha_vantage_api),
            ('lunarcrush', self.validate_lunarcrush_api),
            ('santiment', self.validate_santiment_api)
        ]
        
        results = {}
        successful = 0
        free_tier_working = 0
        
        for name, validator in validations:
            success, data = validator()
            results[name] = {
                'success': success,
                'data': data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            if success:
                successful += 1
                # Count free tier APIs
                if name == 'coingecko':
                    free_tier_working += 1
            
            # Add delay between API tests
            time.sleep(3)
        
        # Summary
        print(f"\n📋 SENTIMENT APIs VALIDATION SUMMARY")
        print(f"{'='*50}")
        print(f"✅ Working APIs: {successful}/{len(validations)}")
        print(f"🆓 Free tier APIs: {free_tier_working}")
        print(f"💰 Premium APIs: {successful - free_tier_working}")
        
        # API status breakdown
        for api_name, result in results.items():
            status = "✅ WORKING" if result['success'] else "❌ FAILED"
            tier = "🆓 FREE" if api_name == 'coingecko' else "💰 PREMIUM"
            print(f"   {api_name.title()}: {status} {tier}")
        
        # Recommendations by tier
        print(f"\n💡 IMPLEMENTATION RECOMMENDATIONS:")
        
        if results.get('coingecko', {}).get('success'):
            print("   🥇 Primary: CoinGecko (free tier sufficient for basic sentiment)")
        
        premium_working = [name for name in ['alpha_vantage', 'lunarcrush', 'santiment'] 
                          if results.get(name, {}).get('success')]
        
        if premium_working:
            print(f"   🥈 Premium: {', '.join(premium_working)} available for enhanced sentiment")
            if 'alpha_vantage' in premium_working:
                print("     📰 Alpha Vantage: Best for news sentiment analysis")
            if 'lunarcrush' in premium_working:
                print("     📱 LunarCrush: Best for social media metrics")
            if 'santiment' in premium_working:
                print("     📊 Santiment: Best for on-chain + social correlation")
        
        # Cost-benefit analysis
        print(f"\n💰 COST-BENEFIT ANALYSIS:")
        print("   CoinGecko Free: $0/month - Basic market sentiment")
        print("   Alpha Vantage: $49.99/month - News sentiment analysis")
        print("   LunarCrush Pro: $35/month - Social intelligence")
        print("   Santiment Pro: $71/month - On-chain + social metrics")
        
        # Multi-provider strategy
        if successful >= 2:
            print(f"\n🎯 MULTI-PROVIDER STRATEGY:")
            print("   ✅ Cross-validation: Compare sentiment scores across providers")
            print("   ✅ Consensus scoring: Weight by provider reliability")
            print("   ✅ Fallback system: Use backup APIs when primary fails")
            
            expected_accuracy = min(85 + (successful - 2) * 5, 95)
            print(f"   📈 Expected accuracy: ~{expected_accuracy}% with {successful} providers")
        else:
            print(f"\n⚠️  Limited provider coverage - consider adding more APIs for reliability")
        
        # Integration complexity
        print(f"\n🔧 INTEGRATION COMPLEXITY:")
        if results.get('coingecko', {}).get('success'):
            print("   🟢 Easy: CoinGecko REST API")
        if results.get('alpha_vantage', {}).get('success'):
            print("   🟢 Easy: Alpha Vantage REST API")
        if results.get('lunarcrush', {}).get('success'):
            print("   🟡 Medium: LunarCrush Bearer token auth")
        if results.get('santiment', {}).get('success'):
            print("   🟡 Medium: Santiment GraphQL API")
        
        # Save validation report
        report_file = os.path.join(SAMPLES_DIR, "sentiment_apis_validation_report.json")
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📊 Full report saved: {report_file}")
        
        return results

def main():
    """Main validation function"""
    try:
        validator = SentimentAPIValidator()
        results = validator.run_all_validations()
        
        # Exit with proper code
        successful_count = sum(1 for r in results.values() if r['success'])
        if successful_count == 0:
            exit(1)  # All validations failed
        elif successful_count < 2:
            exit(2)  # Limited API coverage
        else:
            exit(0)  # Good API coverage
            
    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        exit(1)

if __name__ == "__main__":
    main()