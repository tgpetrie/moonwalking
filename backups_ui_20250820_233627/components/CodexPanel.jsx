import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { API_ENDPOINTS, fetchData } from '../api.js';
import TradingViewChart from './TradingViewChart.jsx';

const CodexPanel = ({ isOpen, onClose, selectedCoin }) => {
  const [activeTab, setActiveTab] = useState('analysis');
  const [technicalData, setTechnicalData] = useState(null);
  const [newsData, setNewsData] = useState([]);
  const [socialData, setSocialData] = useState(null);
  const [loadingStates, setLoadingStates] = useState({
    technical: false,
    news: false,
    social: false
  });
  const modalRef = useRef(null);
  const { latestData, fetchPricesForSymbols } = useWebSocket();

  // Fetch technical analysis data
  const fetchTechnicalAnalysis = async (symbol) => {
    if (!symbol) return;
    
    setLoadingStates(prev => ({ ...prev, technical: true }));
    try {
      const response = await fetchData(API_ENDPOINTS.technicalAnalysis(symbol));
      if (response.success) {
        setTechnicalData(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch technical analysis:', error);
    } finally {
      setLoadingStates(prev => ({ ...prev, technical: false }));
    }
  };

  // Fetch news data
  const fetchNews = async (symbol) => {
    if (!symbol) return;
    
    setLoadingStates(prev => ({ ...prev, news: true }));
    try {
      const response = await fetchData(API_ENDPOINTS.cryptoNews(symbol));
      if (response.success) {
        setNewsData(response.articles || []);
      }
    } catch (error) {
      console.error('Failed to fetch news:', error);
    } finally {
      setLoadingStates(prev => ({ ...prev, news: false }));
    }
  };

  // Fetch social sentiment data
  const fetchSocialSentiment = async (symbol) => {
    if (!symbol) return;
    
    setLoadingStates(prev => ({ ...prev, social: true }));
    try {
      const response = await fetchData(API_ENDPOINTS.socialSentiment(symbol));
      if (response.success) {
        setSocialData(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch social sentiment:', error);
    } finally {
      setLoadingStates(prev => ({ ...prev, social: false }));
    }
  };

  // Fetch data when coin changes
  useEffect(() => {
    if (isOpen && selectedCoin) {
      fetchTechnicalAnalysis(selectedCoin);
      fetchNews(selectedCoin);
      fetchSocialSentiment(selectedCoin);
    }
  }, [selectedCoin, isOpen]);

  // Close modal on Escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  // Close modal when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (modalRef.current && !modalRef.current.contains(e.target)) {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen || !selectedCoin) return null;

  // Get current coin data
  const getCoinData = () => {
    if (latestData.prices && latestData.prices[selectedCoin]) {
      return latestData.prices[selectedCoin];
    }
    if (latestData.crypto && Array.isArray(latestData.crypto)) {
      return latestData.crypto.find(coin => 
        coin.symbol === selectedCoin || coin.symbol === `${selectedCoin}-USD`
      );
    }
    return null;
  };

  const coinData = getCoinData();
  const tabs = [
    { id: 'analysis', label: 'Analysis', icon: '📊' },
    { id: 'news', label: 'News', icon: '📰' },
    { id: 'charts', label: 'Charts', icon: '📈' },
    { id: 'social', label: 'Social', icon: '🌍' }
  ];

  const formatIndicatorValue = (value) => {
    if (value === null || value === undefined) return 'N/A';
    if (typeof value === 'number') {
      return Math.abs(value) < 0.001 ? value.toExponential(3) : value.toFixed(4);
    }
    return value;
  };

  const getRecommendationColor = (recommendation) => {
    if (!recommendation) return 'text-gray-400';
    if (recommendation.includes('🟢') || recommendation.toLowerCase().includes('bullish')) return 'text-green-400';
    if (recommendation.includes('🔴') || recommendation.toLowerCase().includes('bearish')) return 'text-red-400';
    return 'text-yellow-400';
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'analysis':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="text-sm text-gray-400 mb-2">Current Price</div>
                <div className="text-2xl font-bold text-teal">
                  ${coinData?.price || coinData?.current_price || technicalData?.current_price || 'N/A'}
                </div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="text-sm text-gray-400 mb-2">24h Change</div>
                <div className={`text-2xl font-bold ${(coinData?.changePercent || coinData?.price_change_percentage_24h || 0) >= 0 ? 'text-blue' : 'text-pink'}`}>
                  {coinData?.changePercent ? `${coinData.changePercent.toFixed(2)}%` : 
                   coinData?.price_change_percentage_24h ? `${coinData.price_change_percentage_24h.toFixed(2)}%` : 'N/A'}
                </div>
              </div>
            </div>
            
            {loadingStates.technical ? (
              <div className="bg-gray-800/30 rounded-lg p-4">
                <div className="animate-pulse text-blue">Loading technical analysis...</div>
              </div>
            ) : (
              <>
                <div className="bg-gray-800/30 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-3">Technical Indicators</div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-gray-300">RSI (14)</span>
                        <span className={`font-mono ${technicalData?.rsi ? 
                          (technicalData.rsi > 70 ? 'text-red-400' : 
                           technicalData.rsi < 30 ? 'text-green-400' : 'text-yellow-400') : 'text-gray-400'}`}>
                          {technicalData?.rsi || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-300">MACD</span>
                        <span className={`font-mono text-xs ${technicalData?.macd?.macd ? 
                          (technicalData.macd.macd > technicalData.macd.signal ? 'text-green-400' : 'text-red-400') : 'text-gray-400'}`}>
                          {technicalData?.macd?.macd ? formatIndicatorValue(technicalData.macd.macd) : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-300">MACD Signal</span>
                        <span className="font-mono text-xs text-gray-300">
                          {technicalData?.macd?.signal ? formatIndicatorValue(technicalData.macd.signal) : 'N/A'}
                        </span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-gray-300">BB Upper</span>
                        <span className="font-mono text-xs text-gray-300">
                          ${technicalData?.bollinger_bands?.upper || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-300">BB Middle</span>
                        <span className="font-mono text-xs text-gray-300">
                          ${technicalData?.bollinger_bands?.middle || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-300">BB Lower</span>
                        <span className="font-mono text-xs text-gray-300">
                          ${technicalData?.bollinger_bands?.lower || 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {technicalData?.volume_analysis && (
                  <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="text-sm text-gray-400 mb-3">Volume Analysis</div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-gray-300">Volume Trend</span>
                        <span className={`font-medium capitalize ${
                          technicalData.volume_analysis.volume_trend === 'high' ? 'text-green-400' :
                          technicalData.volume_analysis.volume_trend === 'low' ? 'text-red-400' : 'text-yellow-400'
                        }`}>
                          {technicalData.volume_analysis.volume_trend}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-300">Avg Volume</span>
                        <span className="text-gray-300 font-mono text-xs">
                          {technicalData.volume_analysis.avg_volume?.toLocaleString() || 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {technicalData?.recommendation && (
                  <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="text-sm text-gray-400 mb-3">Recommendation</div>
                    <div className={`text-sm font-medium leading-relaxed ${getRecommendationColor(technicalData.recommendation)}`}>
                      {technicalData.recommendation}
                    </div>
                    {technicalData.data_points && (
                      <div className="text-xs text-gray-500 mt-2">
                        Based on {technicalData.data_points} data points
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        );
      
      case 'news':
        return (
          <div className="space-y-4">
            {loadingStates.news ? (
              <div className="text-center py-8">
                <div className="animate-pulse text-blue">Loading news...</div>
              </div>
            ) : newsData.length > 0 ? (
              <div className="space-y-4">
                {newsData.map((article, index) => (
                  <div key={article.id || index} className="bg-gray-800/30 rounded-lg p-4 hover:bg-gray-800/50 transition-colors">
                    <div className="flex items-start gap-3">
                      <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                        article.sentiment === 'positive' ? 'bg-green-400' :
                        article.sentiment === 'negative' ? 'bg-red-400' : 'bg-yellow-400'
                      }`} />
                      <div className="flex-1">
                        <h4 className="text-white font-medium mb-2 leading-snug">{article.title}</h4>
                        <p className="text-gray-300 text-sm mb-3 leading-relaxed">{article.summary}</p>
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>{article.source}</span>
                          <span>{new Date(article.published).toLocaleString()}</span>
                        </div>
                        {article.url && (
                          <button
                            onClick={() => window.open(article.url, '_blank')}
                            className="mt-2 text-blue-400 hover:text-blue-300 text-xs font-medium"
                          >
                            Read More →
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="text-4xl mb-4">📰</div>
                <div className="text-gray-400">No news available</div>
                <div className="text-sm text-gray-500 mt-2">
                  News for {selectedCoin} will appear here when available
                </div>
              </div>
            )}
          </div>
        );
      
      case 'charts':
        return (
          <div className="space-y-4">
            <div className="bg-gray-800/30 rounded-lg p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Advanced Chart</h3>
                <div className="text-xs text-gray-400">Powered by TradingView</div>
              </div>
              <div className="rounded-lg overflow-hidden">
                <TradingViewChart 
                  symbol={selectedCoin} 
                  theme="dark" 
                  height={450}
                />
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-gray-800/30 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-300 mb-2">Chart Features</h4>
                <ul className="text-xs text-gray-400 space-y-1">
                  <li>• Real-time price data from Coinbase</li>
                  <li>• Technical indicators (RSI, MACD, MA)</li>
                  <li>• Multiple timeframes (1m to 1W)</li>
                  <li>• Drawing tools and annotations</li>
                </ul>
              </div>
              
              <div className="bg-gray-800/30 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-300 mb-2">Quick Actions</h4>
                <div className="space-y-2">
                  <button
                    onClick={() => window.open(`https://www.tradingview.com/symbols/COINBASE-${selectedCoin}USD/`, '_blank')}
                    className="w-full text-left px-3 py-2 bg-gray-700/50 hover:bg-gray-700 rounded text-xs text-gray-300 transition-colors"
                  >
                    Open Full Chart →
                  </button>
                  <button
                    onClick={() => window.open(`https://www.coinbase.com/advanced-trade/spot/${selectedCoin?.toLowerCase()}-USD`, '_blank')}
                    className="w-full text-left px-3 py-2 bg-blue/20 hover:bg-blue/30 rounded text-xs text-blue-300 transition-colors"
                  >
                    Trade on Coinbase →
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      
      case 'social':
        return (
          <div className="space-y-4">
            {loadingStates.social ? (
              <div className="text-center py-8">
                <div className="animate-pulse text-blue">Loading social sentiment...</div>
              </div>
            ) : socialData ? (
              <>
                {/* Overall Sentiment */}
                <div className="bg-gray-800/30 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-3">Overall Sentiment</div>
                  <div className="flex items-center gap-4 mb-4">
                    <div className="text-3xl font-bold">
                      <span className={`${
                        socialData.overall_sentiment.score >= 0.6 ? 'text-green-400' :
                        socialData.overall_sentiment.score <= 0.4 ? 'text-red-400' : 'text-yellow-400'
                      }`}>
                        {(socialData.overall_sentiment.score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div>
                      <div className={`font-medium ${
                        socialData.overall_sentiment.score >= 0.6 ? 'text-green-400' :
                        socialData.overall_sentiment.score <= 0.4 ? 'text-red-400' : 'text-yellow-400'
                      }`}>
                        {socialData.overall_sentiment.label}
                      </div>
                      <div className="text-xs text-gray-400">
                        Confidence: {(socialData.overall_sentiment.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                  
                  {/* Sentiment Distribution */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span className="text-xs text-gray-300">Positive: {(socialData.sentiment_distribution.positive * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                      <span className="text-xs text-gray-300">Negative: {(socialData.sentiment_distribution.negative * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                      <span className="text-xs text-gray-300">Neutral: {(socialData.sentiment_distribution.neutral * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                </div>

                {/* Social Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-blue-400">🐦</span>
                      <span className="text-sm text-gray-300">Twitter</span>
                    </div>
                    <div className="text-lg font-bold text-white mb-1">
                      {socialData.social_metrics.twitter.mentions_24h.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-400">mentions (24h)</div>
                    <div className={`text-xs mt-2 ${
                      socialData.social_metrics.twitter.sentiment_score >= 0.6 ? 'text-green-400' :
                      socialData.social_metrics.twitter.sentiment_score <= 0.4 ? 'text-red-400' : 'text-yellow-400'
                    }`}>
                      Sentiment: {(socialData.social_metrics.twitter.sentiment_score * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-orange-400">🔴</span>
                      <span className="text-sm text-gray-300">Reddit</span>
                    </div>
                    <div className="text-lg font-bold text-white mb-1">
                      {socialData.social_metrics.reddit.posts_24h.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-400">posts (24h)</div>
                    <div className={`text-xs mt-2 ${
                      socialData.social_metrics.reddit.sentiment_score >= 0.6 ? 'text-green-400' :
                      socialData.social_metrics.reddit.sentiment_score <= 0.4 ? 'text-red-400' : 'text-yellow-400'
                    }`}>
                      Sentiment: {(socialData.social_metrics.reddit.sentiment_score * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-cyan-400">✈️</span>
                      <span className="text-sm text-gray-300">Telegram</span>
                    </div>
                    <div className="text-lg font-bold text-white mb-1">
                      {socialData.social_metrics.telegram.messages_24h.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-400">messages (24h)</div>
                    <div className={`text-xs mt-2 ${
                      socialData.social_metrics.telegram.sentiment_score >= 0.6 ? 'text-green-400' :
                      socialData.social_metrics.telegram.sentiment_score <= 0.4 ? 'text-red-400' : 'text-yellow-400'
                    }`}>
                      Sentiment: {(socialData.social_metrics.telegram.sentiment_score * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>

                {/* Trending Keywords */}
                {socialData.trending_topics && socialData.trending_topics.length > 0 && (
                  <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="text-sm text-gray-400 mb-3">Trending Keywords</div>
                    <div className="flex flex-wrap gap-2">
                      {socialData.trending_topics.slice(0, 8).map((topic, index) => (
                        <div key={index} className="bg-gray-700/50 px-3 py-1 rounded-full text-xs">
                          <span className="text-white">{topic.keyword}</span>
                          <span className={`ml-1 ${topic.growth_24h > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            ({topic.growth_24h > 0 ? '+' : ''}{topic.growth_24h.toFixed(1)}%)
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Influencer Mentions */}
                {socialData.influencer_mentions && socialData.influencer_mentions.length > 0 && (
                  <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="text-sm text-gray-400 mb-3">Influencer Mentions</div>
                    <div className="space-y-3">
                      {socialData.influencer_mentions.map((mention, index) => (
                        <div key={index} className="flex items-start gap-3">
                          <div className={`w-2 h-2 rounded-full mt-2 ${
                            mention.sentiment === 'bullish' ? 'bg-green-400' :
                            mention.sentiment === 'bearish' ? 'bg-red-400' : 'bg-gray-400'
                          }`} />
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-white text-sm font-medium">{mention.influencer}</span>
                              {mention.verified && <span className="text-blue-400 text-xs">✓</span>}
                              <span className="text-gray-400 text-xs">
                                {mention.followers.toLocaleString()} followers
                              </span>
                            </div>
                            <p className="text-gray-300 text-xs mt-1">{mention.preview}</p>
                            <div className="flex items-center gap-3 mt-1">
                              <span className={`text-xs capitalize ${
                                mention.sentiment === 'bullish' ? 'text-green-400' :
                                mention.sentiment === 'bearish' ? 'text-red-400' : 'text-gray-400'
                              }`}>
                                {mention.sentiment}
                              </span>
                              <span className="text-gray-500 text-xs">
                                {mention.engagement.toLocaleString()} engagements
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Additional Metrics */}
                <div className="bg-gray-800/30 rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-3">Additional Metrics</div>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="text-gray-300">Fear & Greed Index:</span>
                      <span className={`ml-2 font-medium ${
                        socialData.fear_greed_index > 60 ? 'text-green-400' :
                        socialData.fear_greed_index < 40 ? 'text-red-400' : 'text-yellow-400'
                      }`}>
                        {socialData.fear_greed_index}/100
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-300">Volume Correlation:</span>
                      <span className="ml-2 text-white font-mono">
                        {socialData.volume_correlation.toFixed(3)}
                      </span>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-8">
                <div className="text-4xl mb-4">🌍</div>
                <div className="text-gray-400">No social sentiment data available</div>
                <div className="text-sm text-gray-500 mt-2">
                  Social sentiment for {selectedCoin} will appear here when available
                </div>
              </div>
            )}
          </div>
        );
      
      default:
        return <div>Content not found</div>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Background overlay */}
      <div className="fixed inset-0 bg-black/75 backdrop-blur-sm" />
      
      {/* Modal content */}
      <div 
        ref={modalRef}
        className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] mx-4 overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-blue/20 rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold text-blue">{selectedCoin?.slice(0, 2)}</span>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">{selectedCoin} Analysis</h2>
              <p className="text-gray-400 text-sm">Advanced crypto insights powered by real data</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-2"
            aria-label="Close modal"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-700">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-blue border-b-2 border-blue bg-blue/5'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
              {(tab.id === 'analysis' && loadingStates.technical) || (tab.id === 'news' && loadingStates.news) ? (
                <div className="w-2 h-2 bg-blue rounded-full animate-pulse ml-1" />
              ) : null}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {renderTabContent()}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 bg-gray-800/50 border-t border-gray-700">
          <div className="text-xs text-gray-500">
            Data updated: {technicalData?.last_updated ? new Date(technicalData.last_updated).toLocaleTimeString() : new Date().toLocaleTimeString()}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => {
                fetchTechnicalAnalysis(selectedCoin);
                fetchNews(selectedCoin);
                fetchSocialSentiment(selectedCoin);
              }}
              className="px-3 py-1 bg-gray-700 text-white rounded text-xs hover:bg-gray-600 transition-colors"
            >
              Refresh
            </button>
            <button
              onClick={() => window.open(`https://www.coinbase.com/advanced-trade/spot/${selectedCoin?.toLowerCase()}-USD`, '_blank')}
              className="px-4 py-2 bg-blue text-white rounded-lg hover:bg-blue-600 transition-colors text-sm font-medium"
            >
              Trade on Coinbase
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CodexPanel;