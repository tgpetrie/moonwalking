#!/usr/bin/env python3
"""
Sentiment Analyzer for Crypto Content
Multi-model sentiment analysis with crypto-specific tuning
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional
import numpy as np
from datetime import datetime
import pickle
import os

# NLP Libraries
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

class SentimentAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize available models
        self.vader_analyzer = None
        self.transformer_analyzer = None
        self.custom_crypto_model = None
        
        # Crypto-specific sentiment lexicon
        self.crypto_sentiment_lexicon = self._build_crypto_lexicon()
        
        # Language detection patterns
        self.language_patterns = {
            'zh': re.compile(r'[\u4e00-\u9fff]'),
            'es': ['el', 'la', 'de', 'para', 'con', 'bitcoin', 'criptomoneda'],
            'en': True  # Default
        }
        
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize all available sentiment analysis models"""
        # Initialize VADER
        if VADER_AVAILABLE:
            try:
                self.vader_analyzer = SentimentIntensityAnalyzer()
                # Add crypto-specific terms to VADER lexicon
                self._enhance_vader_lexicon()
                self.logger.info("VADER sentiment analyzer initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize VADER: {e}")
        
        # Initialize Transformer model
        if TRANSFORMERS_AVAILABLE:
            try:
                # Use a financial sentiment model if available, otherwise default
                model_name = "ProsusAI/finbert"  # Financial BERT model
                try:
                    self.transformer_analyzer = pipeline(
                        "sentiment-analysis",
                        model=model_name,
                        tokenizer=model_name,
                        device=0 if torch.cuda.is_available() else -1
                    )
                    self.logger.info("FinBERT transformer model initialized")
                except:
                    # Fallback to default model
                    self.transformer_analyzer = pipeline(
                        "sentiment-analysis",
                        model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                        device=0 if torch.cuda.is_available() else -1
                    )
                    self.logger.info("RoBERTa sentiment model initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize transformer model: {e}")
        
        # Try to load custom crypto model
        self._load_custom_crypto_model()
    
    def _build_crypto_lexicon(self) -> Dict[str, float]:
        """Build crypto-specific sentiment lexicon"""
        crypto_lexicon = {
            # Extremely Bullish (0.8 - 1.0)
            'moon': 0.9, 'mooning': 0.9, 'lambo': 0.85, 'diamond_hands': 0.8,
            'hodl': 0.8, 'bullish': 0.8, 'pump': 0.85, 'rocket': 0.9,
            'to_the_moon': 0.95, 'ath': 0.8, 'breakout': 0.8,
            
            # Moderately Bullish (0.6 - 0.8)
            'buy': 0.7, 'long': 0.7, 'accumulate': 0.75, 'dip_buying': 0.7,
            'support': 0.6, 'bounce': 0.7, 'recovery': 0.7, 'green': 0.6,
            'gains': 0.75, 'profit': 0.7, 'bull_market': 0.8,
            
            # Slightly Bullish (0.5 - 0.6)
            'stable': 0.55, 'holding': 0.55, 'steady': 0.55, 'consolidation': 0.55,
            
            # Slightly Bearish (0.4 - 0.5)
            'uncertainty': 0.45, 'volatility': 0.45, 'correction': 0.4,
            'resistance': 0.4, 'sideways': 0.45,
            
            # Moderately Bearish (0.2 - 0.4)
            'sell': 0.3, 'short': 0.3, 'dump': 0.25, 'bear': 0.3,
            'crash': 0.2, 'red': 0.4, 'loss': 0.3, 'bear_market': 0.2,
            'decline': 0.3, 'drop': 0.3, 'fall': 0.3,
            
            # Extremely Bearish (0.0 - 0.2)
            'rekt': 0.1, 'liquidated': 0.1, 'dead_cat_bounce': 0.15,
            'capitulation': 0.1, 'panic_selling': 0.1, 'bloodbath': 0.05,
            'rugpull': 0.0, 'scam': 0.0, 'ponzi': 0.0,
            
            # Hype/FOMO terms (context dependent)
            'fomo': 0.6, 'yolo': 0.7, 'ape_in': 0.6, 'diamond_hands': 0.8,
            'paper_hands': 0.3, 'weak_hands': 0.3,
            
            # Technical analysis
            'breakout': 0.75, 'breakdown': 0.25, 'reversal': 0.5,
            'momentum': 0.7, 'oversold': 0.6, 'overbought': 0.4,
            'bullish_divergence': 0.8, 'bearish_divergence': 0.2,
            
            # Market sentiment
            'euphoria': 0.9, 'greed': 0.8, 'fear': 0.2, 'despair': 0.1,
            'optimism': 0.7, 'pessimism': 0.3, 'neutral': 0.5
        }
        
        return crypto_lexicon
    
    def _enhance_vader_lexicon(self):
        """Add crypto-specific terms to VADER lexicon"""
        if not self.vader_analyzer:
            return
        
        # Add crypto terms to VADER's lexicon
        for term, score in self.crypto_sentiment_lexicon.items():
            # Convert 0-1 scale to VADER's -4 to 4 scale
            vader_score = (score - 0.5) * 8
            self.vader_analyzer.lexicon[term.lower()] = vader_score
            
            # Also add variations
            self.vader_analyzer.lexicon[term.replace('_', '')] = vader_score
            self.vader_analyzer.lexicon[term.replace('_', ' ')] = vader_score
    
    def _load_custom_crypto_model(self):
        """Load custom trained crypto sentiment model if available"""
        model_path = "models/crypto_sentiment_model.pkl"
        
        try:
            if os.path.exists(model_path):
                with open(model_path, 'rb') as f:
                    self.custom_crypto_model = pickle.load(f)
                self.logger.info("Custom crypto sentiment model loaded")
            else:
                self.logger.info("No custom crypto model found, using default models")
        except Exception as e:
            self.logger.error(f"Failed to load custom crypto model: {e}")
    
    def _detect_language(self, text: str) -> str:
        """Detect the language of the text"""
        if not text:
            return 'en'
        
        # Check for Chinese characters
        if self.language_patterns['zh'].search(text):
            return 'zh'
        
        # Check for Spanish indicators
        spanish_indicators = sum(1 for word in self.language_patterns['es'] 
                               if isinstance(word, str) and word.lower() in text.lower())
        if spanish_indicators > 2:
            return 'es'
        
        return 'en'  # Default to English
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for sentiment analysis"""
        if not text:
            return ""
        
        # Convert to lowercase for processing
        text = text.lower()
        
        # Handle crypto-specific abbreviations
        crypto_replacements = {
            'btc': 'bitcoin',
            'eth': 'ethereum',
            'hodl': 'hold',
            'fud': 'fear uncertainty doubt',
            'fomo': 'fear of missing out',
            'rekt': 'wrecked',
            'dyor': 'do your own research',
            'ath': 'all time high',
            'atl': 'all time low'
        }
        
        for abbrev, full_form in crypto_replacements.items():
            text = re.sub(r'\b' + abbrev + r'\b', full_form, text)
        
        # Handle emojis and special characters
        emoji_replacements = {
            '🚀': 'rocket positive',
            '🌙': 'moon positive',
            '💎': 'diamond positive',
            '🙌': 'hands positive',
            '📈': 'chart up positive',
            '📉': 'chart down negative',
            '💩': 'negative',
            '😭': 'crying negative',
            '😱': 'shocked negative',
            '🤑': 'money positive',
            '💸': 'money flying negative'
        }
        
        for emoji, replacement in emoji_replacements.items():
            text = text.replace(emoji, f' {replacement} ')
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return text
    
    async def _analyze_with_vader(self, text: str) -> Dict:
        """Analyze sentiment using VADER"""
        if not self.vader_analyzer:
            return {}
        
        try:
            scores = self.vader_analyzer.polarity_scores(text)
            
            # Convert compound score (-1 to 1) to 0-1 scale
            sentiment_score = (scores['compound'] + 1) / 2
            
            return {
                'sentiment_score': sentiment_score,
                'confidence': abs(scores['compound']),  # Use compound score magnitude as confidence
                'raw_scores': scores,
                'model': 'vader'
            }
        except Exception as e:
            self.logger.error(f"VADER analysis error: {e}")
            return {}
    
    async def _analyze_with_transformer(self, text: str) -> Dict:
        """Analyze sentiment using transformer model"""
        if not self.transformer_analyzer:
            return {}
        
        try:
            # Truncate text if too long for transformer
            max_length = 512
            if len(text.split()) > max_length:
                text = ' '.join(text.split()[:max_length])
            
            result = self.transformer_analyzer(text)
            
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            # Map labels to sentiment scores
            label = result['label'].upper()
            confidence = result['score']
            
            # Handle different model label formats
            if 'POSITIVE' in label or 'BULLISH' in label:
                sentiment_score = 0.5 + (confidence * 0.5)
            elif 'NEGATIVE' in label or 'BEARISH' in label:
                sentiment_score = 0.5 - (confidence * 0.5)
            else:  # NEUTRAL
                sentiment_score = 0.5
            
            return {
                'sentiment_score': sentiment_score,
                'confidence': confidence,
                'raw_label': label,
                'model': 'transformer'
            }
        except Exception as e:
            self.logger.error(f"Transformer analysis error: {e}")
            return {}
    
    async def _analyze_with_crypto_lexicon(self, text: str) -> Dict:
        """Analyze sentiment using crypto-specific lexicon"""
        try:
            words = text.lower().split()
            sentiment_scores = []
            matched_terms = []
            
            for word in words:
                # Direct match
                if word in self.crypto_sentiment_lexicon:
                    sentiment_scores.append(self.crypto_sentiment_lexicon[word])
                    matched_terms.append(word)
                
                # Check for underscore variations
                word_underscore = word.replace(' ', '_')
                if word_underscore in self.crypto_sentiment_lexicon:
                    sentiment_scores.append(self.crypto_sentiment_lexicon[word_underscore])
                    matched_terms.append(word_underscore)
                
                # Check for phrase matches
                for phrase in self.crypto_sentiment_lexicon:
                    if '_' in phrase or ' ' in phrase:
                        phrase_normalized = phrase.replace('_', ' ').replace(' ', '')
                        if phrase_normalized in text.replace(' ', ''):
                            sentiment_scores.append(self.crypto_sentiment_lexicon[phrase])
                            matched_terms.append(phrase)
            
            if sentiment_scores:
                # Weight by frequency and recency of terms
                avg_sentiment = np.mean(sentiment_scores)
                confidence = min(len(matched_terms) / 10, 1.0)  # Max confidence at 10+ matches
                
                return {
                    'sentiment_score': avg_sentiment,
                    'confidence': confidence,
                    'matched_terms': matched_terms,
                    'model': 'crypto_lexicon'
                }
            else:
                return {
                    'sentiment_score': 0.5,  # Neutral if no crypto terms found
                    'confidence': 0.1,
                    'matched_terms': [],
                    'model': 'crypto_lexicon'
                }
                
        except Exception as e:
            self.logger.error(f"Crypto lexicon analysis error: {e}")
            return {}
    
    async def _analyze_with_textblob(self, text: str) -> Dict:
        """Analyze sentiment using TextBlob (fallback method)"""
        if not TEXTBLOB_AVAILABLE:
            return {}
        
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 to 1
            
            # Convert to 0-1 scale
            sentiment_score = (polarity + 1) / 2
            confidence = abs(polarity)
            
            return {
                'sentiment_score': sentiment_score,
                'confidence': confidence,
                'polarity': polarity,
                'subjectivity': blob.sentiment.subjectivity,
                'model': 'textblob'
            }
        except Exception as e:
            self.logger.error(f"TextBlob analysis error: {e}")
            return {}
    
    def _ensemble_sentiment(self, analyses: List[Dict]) -> Dict:
        """Combine multiple sentiment analyses using ensemble method"""
        if not analyses:
            return {
                'score': 0.5,
                'confidence': 0.0,
                'model': 'ensemble',
                'individual_analyses': []
            }
        
        # Filter out empty analyses
        valid_analyses = [a for a in analyses if 'sentiment_score' in a]
        
        if not valid_analyses:
            return {
                'score': 0.5,
                'confidence': 0.0,
                'model': 'ensemble',
                'individual_analyses': []
            }
        
        # Weight different models
        model_weights = {
            'vader': 0.3,
            'transformer': 0.4,
            'crypto_lexicon': 0.2,
            'textblob': 0.1
        }
        
        weighted_scores = []
        total_weight = 0
        confidence_scores = []
        
        for analysis in valid_analyses:
            model = analysis.get('model', 'unknown')
            weight = model_weights.get(model, 0.1)
            score = analysis['sentiment_score']
            confidence = analysis['confidence']
            
            weighted_scores.append(score * weight * confidence)
            total_weight += weight * confidence
            confidence_scores.append(confidence)
        
        # Calculate ensemble score
        if total_weight > 0:
            ensemble_score = sum(weighted_scores) / total_weight
        else:
            ensemble_score = np.mean([a['sentiment_score'] for a in valid_analyses])
        
        # Calculate ensemble confidence
        ensemble_confidence = np.mean(confidence_scores) if confidence_scores else 0.0
        
        # Boost confidence if multiple models agree
        if len(valid_analyses) > 1:
            score_variance = np.var([a['sentiment_score'] for a in valid_analyses])
            if score_variance < 0.1:  # Low variance = high agreement
                ensemble_confidence = min(ensemble_confidence * 1.2, 1.0)
        
        return {
            'score': ensemble_score,
            'confidence': ensemble_confidence,
            'model': 'ensemble',
            'individual_analyses': valid_analyses,
            'agreement_variance': np.var([a['sentiment_score'] for a in valid_analyses]) if len(valid_analyses) > 1 else 0
        }
    
    async def analyze(self, text: str, language: str = None) -> Dict:
        """Main sentiment analysis method"""
        if not text or len(text.strip()) < 5:
            return {
                'score': 0.5,
                'confidence': 0.0,
                'language': 'unknown',
                'model': 'none'
            }
        
        # Detect language if not provided
        if not language:
            language = self._detect_language(text)
        
        # Preprocess text
        processed_text = self._preprocess_text(text)
        
        # Run all available analyses concurrently
        analysis_tasks = []
        
        if self.vader_analyzer:
            analysis_tasks.append(self._analyze_with_vader(processed_text))
        
        if self.transformer_analyzer:
            analysis_tasks.append(self._analyze_with_transformer(processed_text))
        
        analysis_tasks.append(self._analyze_with_crypto_lexicon(processed_text))
        
        if TEXTBLOB_AVAILABLE:
            analysis_tasks.append(self._analyze_with_textblob(processed_text))
        
        # Execute all analyses
        try:
            analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)
            
            # Filter out exceptions
            valid_analyses = [a for a in analyses if isinstance(a, dict) and 'sentiment_score' in a]
            
        except Exception as e:
            self.logger.error(f"Error in sentiment analysis: {e}")
            valid_analyses = []
        
        # Combine results using ensemble method
        ensemble_result = self._ensemble_sentiment(valid_analyses)
        
        return {
            'score': ensemble_result['score'],
            'confidence': ensemble_result['confidence'],
            'language': language,
            'model': ensemble_result['model'],
            'processed_text': processed_text,
            'individual_results': ensemble_result.get('individual_analyses', []),
            'agreement_variance': ensemble_result.get('agreement_variance', 0),
            'timestamp': datetime.now()
        }
    
    async def analyze_batch(self, texts: List[str], language: str = None) -> List[Dict]:
        """Analyze multiple texts in batch"""
        tasks = [self.analyze(text, language) for text in texts]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_analyzer_stats(self) -> Dict:
        """Get statistics about available analyzers"""
        stats = {
            'available_models': [],
            'crypto_lexicon_size': len(self.crypto_sentiment_lexicon),
            'supported_languages': list(self.language_patterns.keys())
        }
        
        if self.vader_analyzer:
            stats['available_models'].append('vader')
        if self.transformer_analyzer:
            stats['available_models'].append('transformer')
        if self.custom_crypto_model:
            stats['available_models'].append('custom_crypto')
        if TEXTBLOB_AVAILABLE:
            stats['available_models'].append('textblob')
        
        stats['available_models'].append('crypto_lexicon')  # Always available
        
        return stats

# Test function
async def test_sentiment_analyzer():
    """Test sentiment analyzer with sample crypto content"""
    analyzer = SentimentAnalyzer()
    
    test_texts = [
        "Bitcoin to the moon! 🚀 This pump is incredible, HODL diamond hands!",
        "Crypto market is crashing, everything is red. Time to panic sell?",
        "Steady consolidation in ETH, good support levels holding",
        "比特币价格今天上涨了很多",  # Chinese: Bitcoin price rose a lot today
        "El precio de Bitcoin está subiendo mucho hoy"  # Spanish: Bitcoin price is rising a lot today
    ]
    
    print("Sentiment Analysis Results:")
    print("=" * 50)
    
    for text in test_texts:
        result = await analyzer.analyze(text)
        
        print(f"\nText: {text}")
        print(f"Sentiment Score: {result['score']:.3f}")
        print(f"Confidence: {result['confidence']:.3f}")
        print(f"Language: {result['language']}")
        print(f"Model: {result['model']}")
        
        if 'individual_results' in result:
            print("Individual Model Results:")
            for individual in result['individual_results']:
                model_name = individual.get('model', 'unknown')
                score = individual.get('sentiment_score', 0)
                conf = individual.get('confidence', 0)
                print(f"  {model_name}: {score:.3f} (conf: {conf:.3f})")
    
    # Print analyzer statistics
    print(f"\nAnalyzer Statistics:")
    stats = analyzer.get_analyzer_stats()
    print(f"Available models: {', '.join(stats['available_models'])}")
    print(f"Crypto lexicon size: {stats['crypto_lexicon_size']}")
    print(f"Supported languages: {', '.join(stats['supported_languages'])}")

if __name__ == "__main__":
    asyncio.run(test_sentiment_analyzer())