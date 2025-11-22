#!/usr/bin/env python3
"""
Social Media APIs Validation Script
Tests Reddit and Twitter APIs for crypto sentiment data collection
"""

import requests
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import base64

# Create samples directory if it doesn't exist
SAMPLES_DIR = "../samples"
os.makedirs(SAMPLES_DIR, exist_ok=True)

class SocialAPIException(Exception):
    """Custom exception for social API validation errors"""
    pass

class SocialAPIValidator:
    def __init__(self):
        self.results = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'crypto-social-validator/1.0'
        })
    
    def validate_reddit_api(self) -> Tuple[bool, Dict]:
        """Validate Reddit API using PRAW-style authentication"""
        print("🔍 Testing Reddit API...")
        
        # Check for credentials
        client_id = os.getenv('REDDIT_CLIENT_ID')
        client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        username = os.getenv('REDDIT_USERNAME')
        password = os.getenv('REDDIT_PASSWORD')
        
        if not all([client_id, client_secret, username, password]):
            print("⚠️  Reddit: Missing credentials in environment variables")
            print("   Required: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD")
            print("   Get credentials at: https://reddit.com/prefs/apps")
            return False, {'error': 'Missing credentials'}
        
        try:
            # Reddit OAuth2 authentication
            print("  🔐 Authenticating with Reddit...")
            
            auth_url = "https://www.reddit.com/api/v1/access_token"
            auth_data = {
                'grant_type': 'password',
                'username': username,
                'password': password
            }
            
            # Basic auth with client credentials
            auth_string = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
            auth_headers = {
                'Authorization': f'Basic {auth_string}',
                'User-Agent': 'crypto-sentiment-validator/1.0 by /u/testuser'
            }
            
            auth_response = self.session.post(auth_url, data=auth_data, headers=auth_headers, timeout=10)
            auth_response.raise_for_status()
            
            auth_result = auth_response.json()
            if 'access_token' not in auth_result:
                raise SocialAPIException("Failed to get access token")
            
            access_token = auth_result['access_token']
            print("    ✅ Authentication successful")
            
            # Test API calls with authenticated session
            api_headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': 'crypto-sentiment-validator/1.0 by /u/testuser'
            }
            
            results = {}
            
            # Test 1: Get subreddit info
            print("  📱 Testing subreddit access...")
            subreddits_to_test = ['CryptoCurrency', 'Bitcoin', 'ethereum']
            
            for subreddit in subreddits_to_test:
                try:
                    sub_url = f"https://oauth.reddit.com/r/{subreddit}/about"
                    sub_response = self.session.get(sub_url, headers=api_headers, timeout=10)
                    sub_response.raise_for_status()
                    
                    sub_data = sub_response.json()
                    
                    if 'data' in sub_data:
                        subscribers = sub_data['data'].get('subscribers', 0)
                        print(f"    ✅ r/{subreddit}: {subscribers:,} subscribers")
                        results[f'subreddit_{subreddit.lower()}'] = {
                            'subscribers': subscribers,
                            'active_users': sub_data['data'].get('active_user_count', 0),
                            'over18': sub_data['data'].get('over18', False)
                        }
                    
                except Exception as e:
                    print(f"    ❌ r/{subreddit}: {e}")
                    results[f'subreddit_{subreddit.lower()}'] = {'error': str(e)}
                
                time.sleep(1)  # Rate limiting
            
            # Test 2: Get recent posts
            print("  📰 Testing post retrieval...")
            try:
                posts_url = "https://oauth.reddit.com/r/CryptoCurrency/hot"
                posts_params = {'limit': 5}
                
                posts_response = self.session.get(posts_url, headers=api_headers, params=posts_params, timeout=10)
                posts_response.raise_for_status()
                
                posts_data = posts_response.json()
                
                if 'data' in posts_data and 'children' in posts_data['data']:
                    posts = posts_data['data']['children']
                    print(f"    ✅ Retrieved {len(posts)} posts from r/CryptoCurrency")
                    
                    # Process sample posts
                    sample_posts = []
                    for post in posts[:3]:
                        post_data = post['data']
                        sample_posts.append({
                            'title': post_data.get('title', ''),
                            'score': post_data.get('score', 0),
                            'num_comments': post_data.get('num_comments', 0),
                            'created_utc': post_data.get('created_utc', 0),
                            'upvote_ratio': post_data.get('upvote_ratio', 0),
                            'author': post_data.get('author', '[deleted]'),
                            'url': post_data.get('url', '')
                        })
                    
                    # Save sample data
                    sample_file = os.path.join(SAMPLES_DIR, "reddit_cryptocurrency_sample.json")
                    with open(sample_file, 'w') as f:
                        json.dump({
                            'subreddit_info': results,
                            'sample_posts': sample_posts,
                            'total_posts_retrieved': len(posts),
                            'validation_time': datetime.now(timezone.utc).isoformat()
                        }, f, indent=2)
                    
                    results['posts_test'] = {
                        'posts_retrieved': len(posts),
                        'sample_file': sample_file
                    }
                    
                    print(f"    📁 Sample saved: {sample_file}")
                else:
                    raise SocialAPIException("Invalid posts response structure")
                    
            except Exception as e:
                print(f"    ❌ Post retrieval: {e}")
                results['posts_test'] = {'error': str(e)}
            
            print(f"✅ Reddit API Status: OK")
            return True, results
            
        except Exception as e:
            print(f"❌ Reddit API Error: {e}")
            return False, {'error': str(e)}
    
    def validate_twitter_api(self) -> Tuple[bool, Dict]:
        """Validate Twitter API v2"""
        print("\n🔍 Testing Twitter/X API v2...")
        
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        if not bearer_token:
            print("⚠️  Twitter: TWITTER_BEARER_TOKEN environment variable not set")
            print("   Get bearer token from: https://developer.twitter.com/")
            return False, {'error': 'Bearer token required'}
        
        try:
            headers = {
                'Authorization': f'Bearer {bearer_token}',
                'User-Agent': 'crypto-sentiment-validator/1.0'
            }
            
            results = {}
            
            # Test 1: Recent search for crypto tweets
            print("  🔍 Testing recent search...")
            search_url = "https://api.twitter.com/2/tweets/search/recent"
            search_params = {
                'query': 'bitcoin OR #BTC -is:retweet lang:en',
                'max_results': 10,
                'tweet.fields': 'created_at,author_id,public_metrics,context_annotations'
            }
            
            search_response = self.session.get(search_url, headers=headers, params=search_params, timeout=10)
            search_response.raise_for_status()
            
            search_data = search_response.json()
            
            if 'data' not in search_data:
                # Check if it's a rate limit or auth issue
                if 'errors' in search_data:
                    error_msg = search_data['errors'][0].get('message', 'Unknown error')
                    raise SocialAPIException(f"Twitter API error: {error_msg}")
                else:
                    raise SocialAPIException("No tweets found or API response invalid")
            
            tweets = search_data['data']
            print(f"    ✅ Found {len(tweets)} recent Bitcoin tweets")
            
            # Process sample tweets
            sample_tweets = []
            for tweet in tweets[:5]:
                sample_tweets.append({
                    'id': tweet.get('id'),
                    'text': tweet.get('text', '')[:100] + '...' if len(tweet.get('text', '')) > 100 else tweet.get('text', ''),
                    'created_at': tweet.get('created_at'),
                    'author_id': tweet.get('author_id'),
                    'public_metrics': tweet.get('public_metrics', {}),
                    'context_annotations': tweet.get('context_annotations', [])
                })
            
            results['recent_search'] = {
                'tweets_found': len(tweets),
                'query_used': search_params['query']
            }
            
            # Test 2: User lookup (if we have specific user access)
            print("  👤 Testing user lookup...")
            try:
                user_url = "https://api.twitter.com/2/users/by/username/VitalikButerin"
                user_params = {'user.fields': 'public_metrics,verified,description'}
                
                user_response = self.session.get(user_url, headers=headers, params=user_params, timeout=10)
                user_response.raise_for_status()
                
                user_data = user_response.json()
                
                if 'data' in user_data:
                    user_info = user_data['data']
                    print(f"    ✅ Retrieved user info for @{user_info.get('username')}")
                    print(f"    👥 Followers: {user_info.get('public_metrics', {}).get('followers_count', 'N/A'):,}")
                    
                    results['user_lookup'] = {
                        'username': user_info.get('username'),
                        'followers': user_info.get('public_metrics', {}).get('followers_count', 0),
                        'verified': user_info.get('verified', False)
                    }
                else:
                    results['user_lookup'] = {'error': 'User data not available'}
                    
            except Exception as e:
                print(f"    ⚠️  User lookup: {e}")
                results['user_lookup'] = {'error': str(e)}
            
            # Save sample data
            sample_file = os.path.join(SAMPLES_DIR, "twitter_crypto_sample.json")
            with open(sample_file, 'w') as f:
                json.dump({
                    'search_results': results,
                    'sample_tweets': sample_tweets,
                    'validation_time': datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
            
            results['sample_file'] = sample_file
            print(f"    📁 Sample saved: {sample_file}")
            
            print(f"✅ Twitter API Status: OK")
            return True, results
            
        except Exception as e:
            print(f"❌ Twitter API Error: {e}")
            return False, {'error': str(e)}
    
    def validate_rate_limits(self) -> Tuple[bool, Dict]:
        """Test API rate limits and quota information"""
        print("\n🔍 Testing API Rate Limits...")
        
        results = {}
        
        # Reddit rate limit info
        print("  📊 Reddit Rate Limits:")
        print("    💡 Standard: 100 requests/minute per OAuth client")
        print("    💡 Burst: 60 requests in quick succession allowed")
        print("    💡 Reset: Rate limits reset every minute")
        
        results['reddit'] = {
            'requests_per_minute': 100,
            'burst_limit': 60,
            'reset_window': '1 minute',
            'cost': 'free'
        }
        
        # Twitter rate limit info
        print("  📊 Twitter Rate Limits:")
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        if bearer_token:
            try:
                # Get rate limit status
                headers = {'Authorization': f'Bearer {bearer_token}'}
                rate_limit_url = "https://api.twitter.com/1.1/application/rate_limit_status.json"
                
                response = self.session.get(rate_limit_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                rate_data = response.json()
                
                if 'resources' in rate_data:
                    search_limits = rate_data['resources'].get('search', {})
                    users_limits = rate_data['resources'].get('users', {})
                    
                    if '/search/tweets' in search_limits:
                        search_info = search_limits['/search/tweets']
                        print(f"    💡 Search: {search_info.get('remaining', 'N/A')}/{search_info.get('limit', 'N/A')} remaining")
                    
                    results['twitter'] = {
                        'search_limits': search_limits.get('/search/tweets', {}),
                        'user_limits': users_limits.get('/users/show/:id', {}),
                        'rate_limit_check': 'successful'
                    }
                else:
                    results['twitter'] = {'rate_limit_check': 'data not available'}
                    
            except Exception as e:
                print(f"    ⚠️  Rate limit check failed: {e}")
                results['twitter'] = {'rate_limit_check': 'failed', 'error': str(e)}
        else:
            print("    💡 Free Tier: 100 reads/month (insufficient for production)")
            print("    💡 Basic ($200/month): 10,000 reads/month")
            print("    💡 Pro ($5,000/month): 1M reads/month + real-time streaming")
            
            results['twitter'] = {
                'free_tier': '100 reads/month',
                'basic_tier': '10,000 reads/month - $200',
                'pro_tier': '1M reads/month - $5,000',
                'note': 'Bearer token not configured'
            }
        
        return True, results
    
    def run_all_validations(self) -> Dict:
        """Run all social media API validations and return summary"""
        print("🚀 Starting Social Media API Validation\n")
        
        validations = [
            ('reddit', self.validate_reddit_api),
            ('twitter', self.validate_twitter_api),
            ('rate_limits', self.validate_rate_limits)
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
            
            # Add delay between API tests
            if name in ['reddit', 'twitter']:
                time.sleep(2)
        
        # Summary
        print(f"\n📋 SOCIAL MEDIA API VALIDATION SUMMARY")
        print(f"{'='*50}")
        print(f"✅ Working APIs: {successful-1}/{len(validations)-1}")  # Exclude rate_limits from count
        print(f"📊 Rate Limits: {'✅ Checked' if results.get('rate_limits', {}).get('success') else '❌ Failed'}")
        
        # API status breakdown
        api_results = {k: v for k, v in results.items() if k != 'rate_limits'}
        for api_name, result in api_results.items():
            status = "✅ WORKING" if result['success'] else "❌ FAILED"
            print(f"   {api_name.title()}: {status}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        
        reddit_working = results.get('reddit', {}).get('success', False)
        twitter_working = results.get('twitter', {}).get('success', False)
        
        if reddit_working and twitter_working:
            print("   🥇 Excellent: Both Reddit and Twitter APIs validated")
            print("   📈 Recommendation: Use both for comprehensive social sentiment")
        elif reddit_working:
            print("   🥈 Good: Reddit API working (strong community sentiment)")
            print("   📈 Recommendation: Focus on Reddit for sentiment, consider Twitter premium")
        elif twitter_working:
            print("   🥉 Limited: Only Twitter working (real-time but costly)")
            print("   📈 Recommendation: Use Twitter carefully due to rate limits")
        else:
            print("   ⚠️  Warning: No social APIs validated")
            print("   📈 Recommendation: Check credentials and network connectivity")
        
        # Cost analysis
        print(f"\n💰 COST ANALYSIS:")
        print(f"   Reddit: Free (100 req/min sufficient for most use cases)")
        if twitter_working:
            print(f"   Twitter: Currently using Free/Basic tier")
            print(f"   Twitter: Consider Pro tier ($5,000/month) for production volume")
        else:
            print(f"   Twitter: Requires paid tier for meaningful usage")
        
        # Data quality assessment
        print(f"\n📊 DATA QUALITY:")
        if reddit_working:
            print(f"   Reddit: High-quality discussions, community sentiment, upvote ratios")
        if twitter_working:
            print(f"   Twitter: Real-time reactions, influencer sentiment, viral trends")
        
        # Save validation report
        report_file = os.path.join(SAMPLES_DIR, "social_apis_validation_report.json")
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📊 Full report saved: {report_file}")
        
        return results

def main():
    """Main validation function"""
    try:
        validator = SocialAPIValidator()
        results = validator.run_all_validations()
        
        # Exit with proper code based on critical APIs
        reddit_success = results.get('reddit', {}).get('success', False)
        twitter_success = results.get('twitter', {}).get('success', False)
        
        if reddit_success or twitter_success:
            exit(0)  # At least one critical API working
        else:
            exit(1)  # No social APIs working
            
    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        exit(1)

if __name__ == "__main__":
    main()