#!/usr/bin/env python3
"""
Data Aggregator for Crypto Sentiment
Aggregates sentiment data across sources, detects divergences, calculates metrics
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics
from dataclasses import asdict
import json

class DataAggregator:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Source tier mappings
        self.source_tiers = self._build_source_tiers()
        
        # Time decay settings
        self.time_decay_settings = config.get('processing', {}).get('trust_decay', {
            'fringe_sources': 0.95,
            'mainstream': 0.99
        })
        
        # Divergence thresholds
        self.divergence_thresholds = config.get('processing', {}).get('divergence_alerts', {
            'tier1_vs_fringe': 0.4,
            'regional_vs_global': 0.3
        })
    
    def _build_source_tiers(self) -> Dict[str, Dict]:
        """Build source tier mappings from config"""
        tiers = {
            'tier1': {'trust_range': (0.8, 1.0), 'sources': []},
            'tier2': {'trust_range': (0.6, 0.8), 'sources': []},
            'tier3': {'trust_range': (0.4, 0.6), 'sources': []},
            'fringe': {'trust_range': (0.0, 0.4), 'sources': []}
        }
        
        # Categorize RSS sources
        for rss_source in self.config.get('news_rss', []):
            trust = rss_source['base_trust']
            source_name = rss_source['name']
            
            if trust >= 0.8:
                tiers['tier1']['sources'].append(source_name)
            elif trust >= 0.6:
                tiers['tier2']['sources'].append(source_name)
            elif trust >= 0.4:
                tiers['tier3']['sources'].append(source_name)
            else:
                tiers['fringe']['sources'].append(source_name)
        
        # Categorize Reddit sources
        for reddit_source in self.config.get('reddit', {}).get('subs', []):
            trust = reddit_source['base_trust']
            source_name = f"r/{reddit_source['sub']}"
            
            if trust >= 0.8:
                tiers['tier1']['sources'].append(source_name)
            elif trust >= 0.6:
                tiers['tier2']['sources'].append(source_name)
            elif trust >= 0.4:
                tiers['tier3']['sources'].append(source_name)
            else:
                tiers['fringe']['sources'].append(source_name)
        
        return tiers
    
    def _get_source_tier(self, source_name: str) -> str:
        """Get the tier of a source"""
        for tier, info in self.source_tiers.items():
            if source_name in info['sources']:
                return tier
        return 'unknown'
    
    def _apply_time_decay(self, sentiment_data, current_time: datetime) -> float:
        """Apply time decay to sentiment data based on age"""
        time_diff = current_time - sentiment_data.timestamp
        hours_old = time_diff.total_seconds() / 3600
        
        # Determine decay rate based on source type
        source_tier = self._get_source_tier(sentiment_data.source)
        if source_tier == 'fringe':
            decay_rate = self.time_decay_settings.get('fringe_sources', 0.95)
        else:
            decay_rate = self.time_decay_settings.get('mainstream', 0.99)
        
        # Apply exponential decay
        decay_factor = decay_rate ** hours_old
        
        return min(decay_factor, 1.0)
    
    def _calculate_weighted_sentiment(self, sentiment_data_list: List, current_time: datetime) -> Dict:
        """Calculate weighted sentiment score from multiple data points"""
        if not sentiment_data_list:
            return {
                'weighted_score': 0.5,
                'confidence': 0.0,
                'data_points': 0,
                'total_weight': 0.0
            }
        
        weighted_scores = []
        total_weight = 0.0
        confidence_scores = []
        
        for data in sentiment_data_list:
            # Base weight from trust score
            base_weight = data.base_trust
            
            # Apply time decay
            time_decay = self._apply_time_decay(data, current_time)
            
            # Apply confidence weighting
            confidence_weight = data.confidence
            
            # Final weight calculation
            final_weight = base_weight * time_decay * confidence_weight
            
            weighted_scores.append(data.sentiment_score * final_weight)
            total_weight += final_weight
            confidence_scores.append(data.confidence)
        
        if total_weight > 0:
            weighted_score = sum(weighted_scores) / total_weight
        else:
            weighted_score = 0.5
        
        overall_confidence = np.mean(confidence_scores) if confidence_scores else 0.0
        
        return {
            'weighted_score': weighted_score,
            'confidence': overall_confidence,
            'data_points': len(sentiment_data_list),
            'total_weight': total_weight
        }
    
    async def aggregate_sentiment(self, sentiment_data: List) -> Dict:
        """Aggregate sentiment data across multiple dimensions"""
        current_time = datetime.now()
        
        aggregated = {
            'overall': {},
            'by_source_tier': {},
            'by_symbol': {},
            'by_source_type': {},
            'by_language': {},
            'by_timeframe': {},
            'by_region': {}
        }
        
        # Overall aggregation
        aggregated['overall'] = self._calculate_weighted_sentiment(sentiment_data, current_time)
        
        # Aggregate by source tier
        by_tier = defaultdict(list)
        for data in sentiment_data:
            tier = self._get_source_tier(data.source)
            by_tier[tier].append(data)
        
        for tier, tier_data in by_tier.items():
            aggregated['by_source_tier'][tier] = self._calculate_weighted_sentiment(tier_data, current_time)
        
        # Aggregate by cryptocurrency symbol
        by_symbol = defaultdict(list)
        for data in sentiment_data:
            if data.symbols:
                for symbol in data.symbols:
                    by_symbol[symbol].append(data)
            else:
                by_symbol['GENERAL'].append(data)
        
        for symbol, symbol_data in by_symbol.items():
            aggregated['by_symbol'][symbol] = self._calculate_weighted_sentiment(symbol_data, current_time)
        
        # Aggregate by source type
        by_source_type = defaultdict(list)
        for data in sentiment_data:
            by_source_type[data.source_type].append(data)
        
        for source_type, type_data in by_source_type.items():
            aggregated['by_source_type'][source_type] = self._calculate_weighted_sentiment(type_data, current_time)
        
        # Aggregate by language
        by_language = defaultdict(list)
        for data in sentiment_data:
            by_language[data.language].append(data)
        
        for language, lang_data in by_language.items():
            aggregated['by_language'][language] = self._calculate_weighted_sentiment(lang_data, current_time)
        
        # Aggregate by timeframe (recent vs older)
        recent_threshold = current_time - timedelta(hours=6)
        very_recent_threshold = current_time - timedelta(hours=1)
        
        recent_data = [d for d in sentiment_data if d.timestamp >= recent_threshold]
        very_recent_data = [d for d in sentiment_data if d.timestamp >= very_recent_threshold]
        older_data = [d for d in sentiment_data if d.timestamp < recent_threshold]
        
        aggregated['by_timeframe'] = {
            'very_recent_1h': self._calculate_weighted_sentiment(very_recent_data, current_time),
            'recent_6h': self._calculate_weighted_sentiment(recent_data, current_time),
            'older_6h_plus': self._calculate_weighted_sentiment(older_data, current_time)
        }
        
        # Aggregate by region (based on language and source)
        by_region = defaultdict(list)
        for data in sentiment_data:
            if data.language == 'zh':
                by_region['china'].append(data)
            elif data.language == 'es':
                by_region['latin_america'].append(data)
            elif 'telegram' in data.source_type.lower():
                by_region['global_social'].append(data)
            elif data.source_type == 'rss' and data.base_trust >= 0.8:
                by_region['western_mainstream'].append(data)
            else:
                by_region['global_general'].append(data)
        
        for region, region_data in by_region.items():
            aggregated['by_region'][region] = self._calculate_weighted_sentiment(region_data, current_time)
        
        return aggregated
    
    async def detect_divergences(self, sentiment_data: List) -> List[Dict]:
        """Detect significant divergences between different data sources"""
        current_time = datetime.now()
        divergences = []
        
        # Get aggregated data
        aggregated = await self.aggregate_sentiment(sentiment_data)
        
        # Check Tier 1 vs Fringe divergence
        tier1_sentiment = aggregated['by_source_tier'].get('tier1', {}).get('weighted_score')
        fringe_sentiment = aggregated['by_source_tier'].get('fringe', {}).get('weighted_score')
        
        if tier1_sentiment is not None and fringe_sentiment is not None:
            divergence_magnitude = abs(tier1_sentiment - fringe_sentiment)
            if divergence_magnitude > self.divergence_thresholds['tier1_vs_fringe']:
                divergences.append({
                    'type': 'tier1_vs_fringe',
                    'magnitude': divergence_magnitude,
                    'tier1_sentiment': tier1_sentiment,
                    'fringe_sentiment': fringe_sentiment,
                    'description': f"Significant divergence between mainstream ({tier1_sentiment:.2f}) and fringe sources ({fringe_sentiment:.2f})",
                    'severity': 'high' if divergence_magnitude > 0.5 else 'medium',
                    'detected_at': current_time
                })
        
        # Check Regional divergences
        china_sentiment = aggregated['by_region'].get('china', {}).get('weighted_score')
        western_sentiment = aggregated['by_region'].get('western_mainstream', {}).get('weighted_score')
        
        if china_sentiment is not None and western_sentiment is not None:
            divergence_magnitude = abs(china_sentiment - western_sentiment)
            if divergence_magnitude > self.divergence_thresholds['regional_vs_global']:
                divergences.append({
                    'type': 'china_vs_western',
                    'magnitude': divergence_magnitude,
                    'china_sentiment': china_sentiment,
                    'western_sentiment': western_sentiment,
                    'description': f"Regional divergence between China ({china_sentiment:.2f}) and Western sources ({western_sentiment:.2f})",
                    'severity': 'medium' if divergence_magnitude > 0.4 else 'low',
                    'detected_at': current_time
                })
        
        # Check Source Type divergences
        source_types = aggregated['by_source_type']
        if len(source_types) >= 2:
            source_scores = [(k, v.get('weighted_score', 0.5)) for k, v in source_types.items() 
                           if v.get('data_points', 0) > 5]  # Only consider sources with sufficient data
            
            if len(source_scores) >= 2:
                max_score = max(score for _, score in source_scores)
                min_score = min(score for _, score in source_scores)
                divergence_magnitude = max_score - min_score
                
                if divergence_magnitude > 0.3:
                    max_source = next(source for source, score in source_scores if score == max_score)
                    min_source = next(source for source, score in source_scores if score == min_score)
                    
                    divergences.append({
                        'type': 'source_type_divergence',
                        'magnitude': divergence_magnitude,
                        'max_source': max_source,
                        'min_source': min_source,
                        'max_sentiment': max_score,
                        'min_sentiment': min_score,
                        'description': f"Source type divergence: {max_source} ({max_score:.2f}) vs {min_source} ({min_score:.2f})",
                        'severity': 'medium',
                        'detected_at': current_time
                    })
        
        # Check Symbol-specific divergences
        symbol_sentiments = aggregated['by_symbol']
        if len(symbol_sentiments) >= 2:
            symbol_scores = [(k, v.get('weighted_score', 0.5)) for k, v in symbol_sentiments.items() 
                           if v.get('data_points', 0) > 3]
            
            if len(symbol_scores) >= 2:
                # Find the most divergent pair
                max_divergence = 0
                divergent_pair = None
                
                for i, (symbol1, score1) in enumerate(symbol_scores):
                    for symbol2, score2 in symbol_scores[i+1:]:
                        divergence = abs(score1 - score2)
                        if divergence > max_divergence:
                            max_divergence = divergence
                            divergent_pair = (symbol1, score1, symbol2, score2)
                
                if max_divergence > 0.35 and divergent_pair:
                    symbol1, score1, symbol2, score2 = divergent_pair
                    divergences.append({
                        'type': 'symbol_divergence',
                        'magnitude': max_divergence,
                        'symbol1': symbol1,
                        'symbol2': symbol2,
                        'sentiment1': score1,
                        'sentiment2': score2,
                        'description': f"Symbol divergence: {symbol1} ({score1:.2f}) vs {symbol2} ({score2:.2f})",
                        'severity': 'low',
                        'detected_at': current_time
                    })
        
        # Check Temporal divergences (recent vs historical)
        recent_sentiment = aggregated['by_timeframe'].get('very_recent_1h', {}).get('weighted_score')
        older_sentiment = aggregated['by_timeframe'].get('older_6h_plus', {}).get('weighted_score')
        
        if recent_sentiment is not None and older_sentiment is not None:
            divergence_magnitude = abs(recent_sentiment - older_sentiment)
            if divergence_magnitude > 0.25:
                divergences.append({
                    'type': 'temporal_shift',
                    'magnitude': divergence_magnitude,
                    'recent_sentiment': recent_sentiment,
                    'older_sentiment': older_sentiment,
                    'description': f"Temporal shift: Recent sentiment ({recent_sentiment:.2f}) vs older ({older_sentiment:.2f})",
                    'severity': 'medium' if divergence_magnitude > 0.4 else 'low',
                    'detected_at': current_time
                })
        
        # Sort divergences by magnitude
        divergences.sort(key=lambda x: x['magnitude'], reverse=True)
        
        return divergences
    
    async def calculate_overall_metrics(self, sentiment_data: List) -> Dict:
        """Calculate comprehensive metrics from sentiment data"""
        current_time = datetime.now()
        
        if not sentiment_data:
            return {
                'weighted_sentiment': 0.5,
                'confidence': 0.0,
                'data_quality_score': 0.0,
                'source_diversity': 0.0,
                'temporal_coverage': 0.0,
                'total_data_points': 0
            }
        
        # Basic metrics
        total_data_points = len(sentiment_data)
        
        # Calculate weighted overall sentiment
        overall_sentiment = self._calculate_weighted_sentiment(sentiment_data, current_time)
        weighted_sentiment = overall_sentiment['weighted_score']
        overall_confidence = overall_sentiment['confidence']
        
        # Data quality score
        quality_factors = []
        
        # Factor 1: Source diversity
        unique_sources = len(set(data.source for data in sentiment_data))
        unique_source_types = len(set(data.source_type for data in sentiment_data))
        source_diversity = min((unique_sources + unique_source_types) / 20, 1.0)  # Normalize to max 20
        quality_factors.append(source_diversity)
        
        # Factor 2: Trust distribution
        trust_scores = [data.base_trust for data in sentiment_data]
        avg_trust = np.mean(trust_scores)
        trust_variance = np.var(trust_scores)
        trust_quality = avg_trust * (1 - trust_variance)  # High average, low variance is good
        quality_factors.append(trust_quality)
        
        # Factor 3: Temporal coverage
        timestamps = [data.timestamp for data in sentiment_data]
        time_span = (max(timestamps) - min(timestamps)).total_seconds() / 3600  # Hours
        temporal_coverage = min(time_span / 24, 1.0)  # Normalize to 24 hours max
        quality_factors.append(temporal_coverage)
        
        # Factor 4: Confidence distribution
        confidence_scores = [data.confidence for data in sentiment_data]
        avg_confidence = np.mean(confidence_scores)
        quality_factors.append(avg_confidence)
        
        # Factor 5: Language diversity
        unique_languages = len(set(data.language for data in sentiment_data))
        language_diversity = min(unique_languages / 5, 1.0)  # Normalize to max 5 languages
        quality_factors.append(language_diversity)
        
        data_quality_score = np.mean(quality_factors)
        
        # Calculate sentiment distribution
        sentiment_scores = [data.sentiment_score for data in sentiment_data]
        sentiment_std = np.std(sentiment_scores)
        sentiment_skewness = self._calculate_skewness(sentiment_scores)
        
        # Calculate momentum (recent vs older sentiment)
        recent_threshold = current_time - timedelta(hours=3)
        recent_data = [d for d in sentiment_data if d.timestamp >= recent_threshold]
        older_data = [d for d in sentiment_data if d.timestamp < recent_threshold]
        
        momentum = 0.0
        if recent_data and older_data:
            recent_sentiment = self._calculate_weighted_sentiment(recent_data, current_time)['weighted_score']
            older_sentiment = self._calculate_weighted_sentiment(older_data, current_time)['weighted_score']
            momentum = recent_sentiment - older_sentiment
        
        # Calculate source tier distribution
        tier_distribution = {}
        for tier in ['tier1', 'tier2', 'tier3', 'fringe']:
            tier_count = sum(1 for data in sentiment_data if self._get_source_tier(data.source) == tier)
            tier_distribution[tier] = tier_count / total_data_points if total_data_points > 0 else 0
        
        # Calculate symbol coverage
        all_symbols = set()
        for data in sentiment_data:
            all_symbols.update(data.symbols)
        symbol_coverage = len(all_symbols)
        
        # Fear & Greed classification
        fear_greed_index = weighted_sentiment * 100
        if fear_greed_index <= 25:
            fear_greed_classification = "Extreme Fear"
        elif fear_greed_index <= 45:
            fear_greed_classification = "Fear"
        elif fear_greed_index <= 55:
            fear_greed_classification = "Neutral"
        elif fear_greed_index <= 75:
            fear_greed_classification = "Greed"
        else:
            fear_greed_classification = "Extreme Greed"
        
        return {
            'weighted_sentiment': weighted_sentiment,
            'confidence': overall_confidence,
            'data_quality_score': data_quality_score,
            'source_diversity': source_diversity,
            'temporal_coverage': temporal_coverage,
            'total_data_points': total_data_points,
            'sentiment_distribution': {
                'mean': np.mean(sentiment_scores),
                'std': sentiment_std,
                'skewness': sentiment_skewness,
                'min': np.min(sentiment_scores),
                'max': np.max(sentiment_scores)
            },
            'momentum': momentum,
            'tier_distribution': tier_distribution,
            'symbol_coverage': symbol_coverage,
            'fear_greed_index': fear_greed_index,
            'fear_greed_classification': fear_greed_classification,
            'language_breakdown': self._get_language_breakdown(sentiment_data),
            'source_type_breakdown': self._get_source_type_breakdown(sentiment_data),
            'calculated_at': current_time
        }
    
    def _calculate_skewness(self, data: List[float]) -> float:
        """Calculate skewness of sentiment data"""
        if len(data) < 3:
            return 0.0
        
        try:
            mean = np.mean(data)
            std = np.std(data)
            if std == 0:
                return 0.0
            
            skewness = np.mean([(x - mean) ** 3 for x in data]) / (std ** 3)
            return skewness
        except:
            return 0.0
    
    def _get_language_breakdown(self, sentiment_data: List) -> Dict:
        """Get breakdown of data by language"""
        language_counts = defaultdict(int)
        for data in sentiment_data:
            language_counts[data.language] += 1
        
        total = len(sentiment_data)
        return {lang: count / total for lang, count in language_counts.items()} if total > 0 else {}
    
    def _get_source_type_breakdown(self, sentiment_data: List) -> Dict:
        """Get breakdown of data by source type"""
        source_type_counts = defaultdict(int)
        for data in sentiment_data:
            source_type_counts[data.source_type] += 1
        
        total = len(sentiment_data)
        return {source_type: count / total for source_type, count in source_type_counts.items()} if total > 0 else {}
    
    async def generate_summary_report(self, sentiment_data: List) -> Dict:
        """Generate a comprehensive summary report"""
        aggregated = await self.aggregate_sentiment(sentiment_data)
        divergences = await self.detect_divergences(sentiment_data)
        metrics = await self.calculate_overall_metrics(sentiment_data)
        
        # Generate insights
        insights = self._generate_insights(aggregated, divergences, metrics)
        
        return {
            'summary': {
                'overall_sentiment': metrics['weighted_sentiment'],
                'confidence': metrics['confidence'],
                'classification': metrics['fear_greed_classification'],
                'data_quality': metrics['data_quality_score'],
                'total_sources': metrics['total_data_points']
            },
            'aggregated_data': aggregated,
            'divergences': divergences,
            'detailed_metrics': metrics,
            'insights': insights,
            'generated_at': datetime.now()
        }
    
    def _generate_insights(self, aggregated: Dict, divergences: List[Dict], metrics: Dict) -> List[str]:
        """Generate human-readable insights from the analysis"""
        insights = []
        
        overall_sentiment = metrics['weighted_sentiment']
        
        # Overall sentiment insight
        if overall_sentiment > 0.75:
            insights.append("📈 Strong bullish sentiment detected across sources")
        elif overall_sentiment > 0.6:
            insights.append("📊 Moderately positive sentiment in the market")
        elif overall_sentiment < 0.25:
            insights.append("📉 Strong bearish sentiment detected across sources")
        elif overall_sentiment < 0.4:
            insights.append("📊 Moderately negative sentiment in the market")
        else:
            insights.append("⚖️ Market sentiment appears neutral to mixed")
        
        # Data quality insight
        quality = metrics['data_quality_score']
        if quality > 0.8:
            insights.append("✅ High quality data with good source diversity")
        elif quality < 0.5:
            insights.append("⚠️ Data quality could be improved - limited source diversity")
        
        # Divergence insights
        if divergences:
            high_severity = [d for d in divergences if d.get('severity') == 'high']
            if high_severity:
                insights.append("🚨 Significant divergence detected between mainstream and fringe sources")
            
            regional_divergences = [d for d in divergences if 'china' in d.get('type', '')]
            if regional_divergences:
                insights.append("🌏 Regional sentiment differences detected between China and Western sources")
        
        # Momentum insight
        momentum = metrics.get('momentum', 0)
        if abs(momentum) > 0.1:
            direction = "improving" if momentum > 0 else "declining"
            insights.append(f"📊 Sentiment momentum is {direction} based on recent data")
        
        # Source tier insight
        tier_dist = metrics.get('tier_distribution', {})
        if tier_dist.get('fringe', 0) > 0.3:
            insights.append("📱 High activity from fringe sources - early trend detection possible")
        
        return insights

# Test function
async def test_data_aggregator():
    """Test data aggregator with sample data"""
    from sentiment_orchestrator import SentimentData
    
    # Create sample sentiment data
    sample_data = [
        SentimentData(
            source="CoinDesk",
            source_type="rss",
            content="Bitcoin showing strong momentum",
            sentiment_score=0.75,
            confidence=0.8,
            base_trust=0.85,
            timestamp=datetime.now() - timedelta(hours=1),
            symbols=["BTC"],
            language="en"
        ),
        SentimentData(
            source="4chan /biz/",
            source_type="custom_scraper",
            content="Moon mission incoming!!!",
            sentiment_score=0.9,
            confidence=0.6,
            base_trust=0.4,
            timestamp=datetime.now() - timedelta(minutes=30),
            symbols=["BTC"],
            language="en"
        ),
        SentimentData(
            source="r/CryptoCurrency",
            source_type="reddit",
            content="Market looking bearish today",
            sentiment_score=0.3,
            confidence=0.7,
            base_trust=0.65,
            timestamp=datetime.now() - timedelta(hours=2),
            symbols=["BTC", "ETH"],
            language="en"
        )
    ]
    
    # Test aggregator
    config = {
        'news_rss': [{'name': 'CoinDesk', 'base_trust': 0.85}],
        'reddit': {'subs': [{'sub': 'CryptoCurrency', 'base_trust': 0.65}]}
    }
    
    aggregator = DataAggregator(config)
    
    print("Data Aggregation Test Results:")
    print("=" * 50)
    
    # Test aggregation
    aggregated = await aggregator.aggregate_sentiment(sample_data)
    print(f"Overall weighted sentiment: {aggregated['overall']['weighted_score']:.3f}")
    
    # Test divergence detection
    divergences = await aggregator.detect_divergences(sample_data)
    print(f"Divergences detected: {len(divergences)}")
    for div in divergences:
        print(f"  - {div['type']}: {div['description']}")
    
    # Test metrics calculation
    metrics = await aggregator.calculate_overall_metrics(sample_data)
    print(f"Data quality score: {metrics['data_quality_score']:.3f}")
    print(f"Fear & Greed classification: {metrics['fear_greed_classification']}")
    
    # Test summary report
    report = await aggregator.generate_summary_report(sample_data)
    print("\nInsights:")
    for insight in report['insights']:
        print(f"  - {insight}")

if __name__ == "__main__":
    asyncio.run(test_data_aggregator())