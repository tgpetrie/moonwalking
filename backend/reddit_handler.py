#!/usr/bin/env python3
"""
Reddit Handler for Crypto Sentiment Collection
Uses PRAW to collect posts and comments from crypto subreddits
"""

import asyncio
import praw
import prawcore
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import time
from concurrent.futures import ThreadPoolExecutor
import json


REDDIT_CLIENT_ID_PLACEHOLDER = "YOUR_REDDIT_CLIENT_ID"
REDDIT_CLIENT_SECRET_PLACEHOLDER = "YOUR_REDDIT_CLIENT_SECRET"  # pragma: allowlist secret
REDDIT_USER_AGENT = "CryptoSentimentBot/1.0"

class RedditHandler:
    def __init__(self, reddit_config: Dict):
        self.reddit_config = reddit_config or {}
        self.logger = logging.getLogger(__name__)
        self.reddit = None
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # Reddit API credentials (set these in your environment)
        self.reddit_client_id = self.reddit_config.get("client_id", REDDIT_CLIENT_ID_PLACEHOLDER)
        self.reddit_client_secret = self.reddit_config.get("client_secret", REDDIT_CLIENT_SECRET_PLACEHOLDER)
        self.reddit_user_agent = self.reddit_config.get("user_agent", REDDIT_USER_AGENT)
        
        self._init_reddit_client()
    
    def _init_reddit_client(self):
        """Initialize Reddit client"""
        try:
            self.reddit = praw.Reddit(
                client_id=self.reddit_client_id,
                client_secret=self.reddit_client_secret,
                user_agent=self.reddit_user_agent
            )
            
            # Test connection
            self.reddit.user.me()
            self.logger.info("Reddit client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Reddit client: {e}")
            self.reddit = None
    
    def _clean_reddit_content(self, content: str) -> str:
        """Clean Reddit content (remove markdown, links, etc.)"""
        if not content:
            return ""
        
        # Remove markdown formatting
        content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)  # Bold
        content = re.sub(r'\*(.*?)\*', r'\1', content)      # Italic
        content = re.sub(r'~~(.*?)~~', r'\1', content)      # Strikethrough
        
        # Remove Reddit links
        content = re.sub(r'/?u/[\w-]+', '', content)        # User mentions
        content = re.sub(r'/?r/[\w-]+', '', content)        # Subreddit mentions
        content = re.sub(r'https?://[^\s]+', '', content)   # URLs
        
        # Remove Reddit formatting
        content = re.sub(r'^>', '', content, flags=re.MULTILINE)  # Quotes
        content = re.sub(r'^\d+\.', '', content, flags=re.MULTILINE)  # Numbered lists
        content = re.sub(r'^\*', '', content, flags=re.MULTILINE)     # Bullet points
        
        # Clean whitespace
        content = ' '.join(content.split())
        
        return content.strip()
    
    def _extract_crypto_mentions(self, content: str) -> List[str]:
        """Extract cryptocurrency mentions from content"""
        crypto_patterns = {
            'bitcoin': ['btc', 'bitcoin', '₿'],
            'ethereum': ['eth', 'ethereum', 'ether'],
            'solana': ['sol', 'solana'],
            'avalanche': ['avax', 'avalanche'],
            'cardano': ['ada', 'cardano'],
            'polygon': ['matic', 'polygon'],
            'chainlink': ['link', 'chainlink'],
            'polkadot': ['dot', 'polkadot'],
            'dogecoin': ['doge', 'dogecoin'],
            'shiba': ['shib', 'shiba']
        }
        
        mentions = []
        content_lower = content.lower()
        
        for crypto, patterns in crypto_patterns.items():
            for pattern in patterns:
                if pattern in content_lower:
                    mentions.append(crypto.upper())
                    break
        
        return list(set(mentions))  # Remove duplicates
    
    def _score_content_relevance(self, content: str) -> float:
        """Score how relevant content is to crypto sentiment"""
        crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'trading', 'price', 'moon', 'bear', 'bull', 'hodl', 'diamond',
            'hands', 'sell', 'buy', 'dump', 'pump', 'rally', 'crash',
            'market', 'dip', 'support', 'resistance'
        ]
        
        content_lower = content.lower()
        matches = sum(1 for keyword in crypto_keywords if keyword in content_lower)
        
        # Normalize by content length
        word_count = len(content.split())
        if word_count == 0:
            return 0.0
        
        relevance = min(matches / max(word_count * 0.1, 1), 1.0)
        return relevance
    
    async def _fetch_subreddit_posts(self, sub_config: Dict) -> List[Dict]:
        """Fetch posts from a single subreddit"""
        subreddit_name = sub_config['sub']
        base_trust = sub_config['base_trust']
        
        if not self.reddit:
            self.logger.error("Reddit client not initialized")
            return []
        
        try:
            self.logger.info(f"Fetching posts from r/{subreddit_name}")
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            posts_data = await loop.run_in_executor(
                self.executor,
                self._fetch_subreddit_sync,
                subreddit_name,
                base_trust
            )
            
            return posts_data
            
        except Exception as e:
            self.logger.error(f"Error fetching r/{subreddit_name}: {str(e)}")
            return []
    
    def _fetch_subreddit_sync(self, subreddit_name: str, base_trust: float) -> List[Dict]:
        """Synchronous subreddit fetching (for thread pool)"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts_data = []
            
            # Get hot posts (last 24 hours)
            for post in subreddit.hot(limit=25):
                # Skip stickied posts
                if post.stickied:
                    continue
                
                # Check if post is recent (within 24 hours)
                post_time = datetime.fromtimestamp(post.created_utc)
                if datetime.now() - post_time > timedelta(days=1):
                    continue
                
                # Combine title and selftext
                content = f"{post.title}. {post.selftext}"
                clean_content = self._clean_reddit_content(content)
                
                # Skip very short content
                if len(clean_content) < 30:
                    continue
                
                # Check relevance
                relevance = self._score_content_relevance(clean_content)
                if relevance < 0.1:  # Skip irrelevant content
                    continue
                
                # Extract crypto mentions
                crypto_mentions = self._extract_crypto_mentions(clean_content)
                
                post_data = {
                    'subreddit': subreddit_name,
                    'title': post.title,
                    'content': clean_content,
                    'url': f"https://reddit.com{post.permalink}",
                    'score': post.score,
                    'comments': post.num_comments,
                    'timestamp': post_time,
                    'base_trust': base_trust,
                    'crypto_mentions': crypto_mentions,
                    'relevance_score': relevance,
                    'author': str(post.author) if post.author else '[deleted]'
                }
                posts_data.append(post_data)
                
                # Also get top comments for high-scoring posts
                if post.score > 50 and post.num_comments > 10:
                    comments_data = self._fetch_post_comments(post, subreddit_name, base_trust)
                    posts_data.extend(comments_data)
            
            # Also get new posts for early sentiment
            for post in subreddit.new(limit=15):
                if post.stickied:
                    continue
                
                post_time = datetime.fromtimestamp(post.created_utc)
                if datetime.now() - post_time > timedelta(hours=6):  # Only very recent
                    continue
                
                content = f"{post.title}. {post.selftext}"
                clean_content = self._clean_reddit_content(content)
                
                if len(clean_content) < 30:
                    continue
                
                relevance = self._score_content_relevance(clean_content)
                if relevance < 0.15:  # Higher threshold for new posts
                    continue
                
                crypto_mentions = self._extract_crypto_mentions(clean_content)
                
                post_data = {
                    'subreddit': subreddit_name,
                    'title': post.title,
                    'content': clean_content,
                    'url': f"https://reddit.com{post.permalink}",
                    'score': post.score,
                    'comments': post.num_comments,
                    'timestamp': post_time,
                    'base_trust': base_trust * 0.8,  # Lower trust for new posts
                    'crypto_mentions': crypto_mentions,
                    'relevance_score': relevance,
                    'author': str(post.author) if post.author else '[deleted]',
                    'post_type': 'new'
                }
                posts_data.append(post_data)
            
            self.logger.info(f"Collected {len(posts_data)} items from r/{subreddit_name}")
            return posts_data
            
        except prawcore.exceptions.Redirect:
            self.logger.error(f"Subreddit r/{subreddit_name} not found")
            return []
        except prawcore.exceptions.Forbidden:
            self.logger.error(f"Access forbidden to r/{subreddit_name}")
            return []
        except Exception as e:
            self.logger.error(f"Error fetching r/{subreddit_name}: {str(e)}")
            return []
    
    def _fetch_post_comments(self, post, subreddit_name: str, base_trust: float) -> List[Dict]:
        """Fetch top comments from a post"""
        comments_data = []
        
        try:
            # Get top 5 comments
            post.comments.replace_more(limit=0)  # Don't expand "more comments"
            top_comments = post.comments[:5]
            
            for comment in top_comments:
                if hasattr(comment, 'body') and comment.body:
                    clean_content = self._clean_reddit_content(comment.body)
                    
                    if len(clean_content) < 20:
                        continue
                    
                    relevance = self._score_content_relevance(clean_content)
                    if relevance < 0.1:
                        continue
                    
                    crypto_mentions = self._extract_crypto_mentions(clean_content)
                    comment_time = datetime.fromtimestamp(comment.created_utc)
                    
                    comment_data = {
                        'subreddit': subreddit_name,
                        'title': f"Comment on: {post.title[:50]}...",
                        'content': clean_content,
                        'url': f"https://reddit.com{comment.permalink}",
                        'score': comment.score,
                        'comments': 0,  # Comments don't have replies in our data
                        'timestamp': comment_time,
                        'base_trust': base_trust * 0.9,  # Slightly lower trust for comments
                        'crypto_mentions': crypto_mentions,
                        'relevance_score': relevance,
                        'author': str(comment.author) if comment.author else '[deleted]',
                        'content_type': 'comment'
                    }
                    comments_data.append(comment_data)
        
        except Exception as e:
            self.logger.error(f"Error fetching comments: {str(e)}")
        
        return comments_data
    
    async def fetch_all_subreddits(self) -> List[Dict]:
        """Fetch posts from all configured subreddits"""
        if not self.reddit:
            self.logger.error("Reddit client not available")
            return []
        
        subreddits = self.reddit_config.get('subs', [])
        
        # Create tasks for all subreddits
        tasks = []
        for sub_config in subreddits:
            tasks.append(self._fetch_subreddit_posts(sub_config))
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        all_posts = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Subreddit fetch error: {result}")
            elif isinstance(result, list):
                all_posts.extend(result)
        
        # Sort by relevance and recency
        all_posts.sort(key=lambda x: (x['relevance_score'], x['timestamp']), reverse=True)
        
        self.logger.info(f"Total Reddit items collected: {len(all_posts)}")
        return all_posts
    
    def get_reddit_stats(self) -> Dict:
        """Get statistics about Reddit collection"""
        if not self.reddit:
            return {'error': 'Reddit client not available'}
        
        subreddits = self.reddit_config.get('subs', [])
        
        stats = {
            'total_subreddits_configured': len(subreddits),
            'subreddits_by_trust_level': {},
            'client_status': 'connected' if self.reddit else 'disconnected'
        }
        
        # Group by trust level
        for sub_config in subreddits:
            trust = sub_config['base_trust']
            trust_range = f"{int(trust * 10) / 10:.1f}"
            if trust_range not in stats['subreddits_by_trust_level']:
                stats['subreddits_by_trust_level'][trust_range] = []
            stats['subreddits_by_trust_level'][trust_range].append(sub_config['sub'])
        
        return stats
    
    async def get_trending_topics(self) -> Dict:
        """Get trending crypto topics across all subreddits"""
        all_posts = await self.fetch_all_subreddits()
        
        # Count crypto mentions
        crypto_counts = {}
        topic_keywords = {}
        
        for post in all_posts:
            for crypto in post.get('crypto_mentions', []):
                crypto_counts[crypto] = crypto_counts.get(crypto, 0) + 1
            
            # Extract keywords from high-scoring posts
            if post['score'] > 100:
                words = post['content'].lower().split()
                for word in words:
                    if len(word) > 4 and word.isalpha():
                        topic_keywords[word] = topic_keywords.get(word, 0) + 1
        
        # Get top trending
        top_cryptos = sorted(crypto_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_keywords = sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)[:20]
        
        return {
            'trending_cryptos': top_cryptos,
            'trending_keywords': top_keywords,
            'total_posts_analyzed': len(all_posts)
        }

# Test function
async def test_reddit_handler():
    """Test Reddit handler with sample configuration"""
    test_config = {
        'subs': [
            {'sub': 'CryptoCurrency', 'base_trust': 0.65},
            {'sub': 'Bitcoin', 'base_trust': 0.70},
            {'sub': 'ethereum', 'base_trust': 0.70}
        ]
    }
    
    handler = RedditHandler(test_config)
    
    if handler.reddit:
        posts = await handler.fetch_all_subreddits()
        
        print(f"Collected {len(posts)} posts")
        for post in posts[:3]:  # Show first 3 posts
            print(f"\nSubreddit: r/{post['subreddit']}")
            print(f"Title: {post['title']}")
            print(f"Content: {post['content'][:200]}...")
            print(f"Score: {post['score']}")
            print(f"Crypto mentions: {post['crypto_mentions']}")
            print(f"Relevance: {post['relevance_score']:.2f}")
    else:
        print("Reddit client not available - check credentials")

if __name__ == "__main__":
    asyncio.run(test_reddit_handler())