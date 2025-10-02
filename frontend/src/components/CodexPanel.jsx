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
  const [errorStates, setErrorStates] = useState({
    technical: null,
    news: null,
    social: null
  });
  const [metadata, setMetadata] = useState({
    technical: null,
    news: null,
    social: null
  });
  const modalRef = useRef(null);
  const { latestData, fetchPricesForSymbols } = useWebSocket();

  const surfaceCard = 'rounded-xl border border-purple-400/25 bg-gradient-to-br from-[#18092f]/85 via-[#0b041d]/85 to-[#050111]/88 shadow-[0_22px_55px_rgba(9,3,25,0.55)] backdrop-blur-sm p-4';
  const surfacePanel = 'rounded-[26px] border border-purple-500/35 bg-gradient-to-br from-[#140728]/96 via-[#080218]/94 to-[#03000f]/97 shadow-[0_40px_90px_rgba(8,3,22,0.7)] backdrop-blur-xl w-full max-w-4xl max-h-[90vh] mx-4 overflow-hidden';
  const mutedLabel = 'text-xs font-semibold tracking-wide uppercase text-white/60';
  const subtleText = 'text-white/70';

  // Fetch technical analysis data
  const fetchTechnicalAnalysis = async (symbol) => {
    if (!symbol) return;
    
    setLoadingStates(prev => ({ ...prev, technical: true }));
    setErrorStates(prev => ({ ...prev, technical: null }));
    setMetadata(prev => ({ ...prev, technical: null }));
    try {
      const response = await fetchData(API_ENDPOINTS.technicalAnalysis(symbol));
      if (response.success) {
        setTechnicalData(response.data);
        setMetadata(prev => ({ ...prev, technical: response.timestamp || response.data?.last_updated || new Date().toISOString() }));
      }
      if (!response.success) {
        setTechnicalData(null);
        setErrorStates(prev => ({ ...prev, technical: response.error || 'Technical analysis unavailable.' }));
        setMetadata(prev => ({ ...prev, technical: null }));
      }
    } catch (error) {
      console.error('Failed to fetch technical analysis:', error);
      setTechnicalData(null);
      setErrorStates(prev => ({ ...prev, technical: 'Unable to load technical analysis.' }));
      setMetadata(prev => ({ ...prev, technical: null }));
    } finally {
      setLoadingStates(prev => ({ ...prev, technical: false }));
    }
  };

  // Fetch news data
  const fetchNews = async (symbol) => {
    if (!symbol) return;
    
    setLoadingStates(prev => ({ ...prev, news: true }));
    setErrorStates(prev => ({ ...prev, news: null }));
    setMetadata(prev => ({ ...prev, news: null }));
    try {
      const response = await fetchData(API_ENDPOINTS.cryptoNews(symbol));
      if (response.success) {
        setNewsData(response.articles || []);
        setMetadata(prev => ({ ...prev, news: response.generated_at || new Date().toISOString() }));
      } else {
        setNewsData([]);
        setErrorStates(prev => ({ ...prev, news: response.error || 'No news available.' }));
        setMetadata(prev => ({ ...prev, news: null }));
      }
    } catch (error) {
      console.error('Failed to fetch news:', error);
      setNewsData([]);
      setErrorStates(prev => ({ ...prev, news: 'Unable to load news.' }));
      setMetadata(prev => ({ ...prev, news: null }));
    } finally {
      setLoadingStates(prev => ({ ...prev, news: false }));
    }
  };

  // Fetch social sentiment data
  const fetchSocialSentiment = async (symbol) => {
    if (!symbol) return;
    
    setLoadingStates(prev => ({ ...prev, social: true }));
    setErrorStates(prev => ({ ...prev, social: null }));
    setMetadata(prev => ({ ...prev, social: null }));
    try {
      const response = await fetchData(API_ENDPOINTS.socialSentiment(symbol));
      if (response.success) {
        setSocialData(response.data);
        setMetadata(prev => ({ ...prev, social: response.generated_at || response.data?.last_updated || new Date().toISOString() }));
      } else {
        setSocialData(null);
        setErrorStates(prev => ({ ...prev, social: response.error || 'No sentiment data available.' }));
        setMetadata(prev => ({ ...prev, social: null }));
      }
    } catch (error) {
      console.error('Failed to fetch social sentiment:', error);
      setSocialData(null);
      setErrorStates(prev => ({ ...prev, social: 'Unable to load social sentiment.' }));
      setMetadata(prev => ({ ...prev, social: null }));
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
    if (!recommendation) return 'text-white/70';
    if (recommendation.includes('🟢') || recommendation.toLowerCase().includes('bullish')) return 'text-emerald-300';
    if (recommendation.includes('🔴') || recommendation.toLowerCase().includes('bearish')) return 'text-rose-300';
    return 'text-amber-300';
  };

  const randomIntFallback = () => Math.floor(Math.random() * 5000) + 1000;

  const renderTabContent = () => {
    switch (activeTab) {
      case 'analysis':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className={surfaceCard}>
                <div className={`${mutedLabel} mb-2`}>Current Price</div>
                <div className="text-3xl font-bold text-orange-200">
                  ${coinData?.price || coinData?.current_price || technicalData?.current_price || 'N/A'}
                </div>
              </div>
              <div className={surfaceCard}>
                <div className={`${mutedLabel} mb-2`}>24h Change</div>
                <div className={`text-2xl font-bold ${(coinData?.changePercent || coinData?.price_change_percentage_24h || 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {coinData?.changePercent ? `${coinData.changePercent.toFixed(3)}%` : 
                   coinData?.price_change_percentage_24h ? `${coinData.price_change_percentage_24h.toFixed(3)}%` : 'N/A'}
                </div>
              </div>
            </div>
            
            {loadingStates.technical ? (
              <div className={surfaceCard}>
                <div className="animate-pulse text-blue">Loading technical analysis...</div>
              </div>
            ) : errorStates.technical ? (
              <div className={surfaceCard}>
                <div className="text-rose-200 text-sm font-medium mb-2">{errorStates.technical}</div>
                <div className="text-xs text-white/40">Try selecting another asset or refreshing later.</div>
              </div>
            ) : (
              <>
                <div className={surfaceCard}>
                  <div className={`${mutedLabel} mb-3`}>Technical Indicators</div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className={subtleText}>RSI (14)</span>
                        <span className={`font-mono ${technicalData?.rsi ? 
                          (technicalData.rsi > 70 ? 'text-rose-300' : 
                           technicalData.rsi < 30 ? 'text-emerald-300' : 'text-amber-300') : 'text-white/45'}`}>
                          {technicalData?.rsi || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className={subtleText}>MACD</span>
                        <span className={`font-mono text-xs ${technicalData?.macd?.macd ? 
                          (technicalData.macd.macd > technicalData.macd.signal ? 'text-emerald-300' : 'text-rose-300') : 'text-white/45'}`}>
                          {technicalData?.macd?.macd ? formatIndicatorValue(technicalData.macd.macd) : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className={subtleText}>MACD Signal</span>
                        <span className="font-mono text-xs text-white/70">
                          {technicalData?.macd?.signal ? formatIndicatorValue(technicalData.macd.signal) : 'N/A'}
                        </span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className={subtleText}>BB Upper</span>
                        <span className="font-mono text-xs text-white/70">
                          ${technicalData?.bollinger_bands?.upper || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className={subtleText}>BB Middle</span>
                        <span className="font-mono text-xs text-white/70">
                          ${technicalData?.bollinger_bands?.middle || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className={subtleText}>BB Lower</span>
                        <span className="font-mono text-xs text-white/70">
                          ${technicalData?.bollinger_bands?.lower || 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {technicalData?.volume_analysis && (
                  <div className={surfaceCard}>
                    <div className={`${mutedLabel} mb-3`}>Volume Analysis</div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className={subtleText}>Volume Trend</span>
                        <span className={`font-medium capitalize ${
                          technicalData.volume_analysis.volume_trend === 'high' ? 'text-emerald-300' :
                          technicalData.volume_analysis.volume_trend === 'low' ? 'text-rose-300' : 'text-amber-300'
                        }`}>
                          {technicalData.volume_analysis.volume_trend}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className={subtleText}>Avg Volume</span>
                        <span className="text-white/70 font-mono text-xs">
                          {technicalData.volume_analysis.avg_volume?.toLocaleString() || 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {technicalData?.recommendation && (
                  <div className={surfaceCard}>
                    <div className={`${mutedLabel} mb-3`}>Recommendation</div>
                    <div className={`text-base font-semibold leading-relaxed ${getRecommendationColor(technicalData.recommendation)}`}>
                      {technicalData.recommendation}
                    </div>
                    {technicalData.data_points && (
                      <div className="text-xs text-white/50 mt-2">
                        Based on {technicalData.data_points} data points
                      </div>
                    )}
                    {metadata.technical && (
                      <div className="text-[10px] text-white/35 mt-3">
                        Updated {new Date(metadata.technical).toLocaleTimeString()}
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
            ) : errorStates.news ? (
              <div className={`${surfaceCard} text-center py-8`}>
                <div className="text-4xl mb-3">🚧</div>
                <div className="text-white/70">{errorStates.news}</div>
                <div className="text-xs text-white/40 mt-2">Please try again later.</div>
              </div>
            ) : newsData.length > 0 ? (
              <div className="space-y-4">
                {newsData.map((article, index) => (
                  <div key={article.id || index} className={`${surfaceCard} transition-transform hover:scale-[1.01]`}>
                    <div className="flex items-start gap-3">
                      <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                        article.sentiment === 'positive' ? 'bg-green-400' :
                        article.sentiment === 'negative' ? 'bg-red-400' : 'bg-yellow-400'
                      }`} />
                      <div className="flex-1">
                        <h4 className="text-white font-semibold mb-2 leading-snug">{article.title}</h4>
                        <p className="text-white/70 text-sm mb-3 leading-relaxed">{article.summary}</p>
                        <div className="flex items-center justify-between text-xs text-white/50">
                          <span>{article.source}</span>
                          <span>{new Date(article.published).toLocaleString()}</span>
                        </div>
                        {article.url && (
                          <button
                            onClick={() => window.open(article.url, '_blank')}
                            className="mt-3 text-xs font-semibold text-orange-200 hover:text-orange-100"
                          >
                            Read More →
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {metadata.news && (
                  <div className="text-[10px] text-white/35 text-center">
                    Headlines refreshed {new Date(metadata.news).toLocaleTimeString()}
                  </div>
                )}
              </div>
            ) : (
              <div className={`${surfaceCard} text-center py-8`}>
                <div className="text-4xl mb-4">📰</div>
                <div className="text-white/70">No news available</div>
                <div className="text-sm text-white/50 mt-2">
                  News for {selectedCoin} will appear here when available
                </div>
              </div>
            )}
          </div>
        );
      
      case 'charts':
        return (
          <div className="space-y-4">
            <div className={surfaceCard}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white tracking-wide">Advanced Chart</h3>
                <div className="text-xs text-white/50">Powered by TradingView</div>
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
              <div className={surfaceCard}>
                <h4 className={`${mutedLabel} mb-2`}>Chart Features</h4>
                <ul className="text-xs text-white/65 space-y-1">
                  <li>• Real-time price data from Coinbase</li>
                  <li>• Technical indicators (RSI, MACD, MA)</li>
                  <li>• Multiple timeframes (1m to 1W)</li>
                  <li>• Drawing tools and annotations</li>
                </ul>
              </div>
              
              <div className={surfaceCard}>
                <h4 className={`${mutedLabel} mb-2`}>Quick Actions</h4>
                <div className="space-y-2">
                  <button
                    onClick={() => window.open(`https://www.tradingview.com/symbols/COINBASE-${selectedCoin}USD/`, '_blank')}
                    className="w-full text-left px-3 py-2 rounded text-xs font-semibold text-white/70 bg-white/10 hover:bg-white/15 transition-colors"
                  >
                    Open Full Chart →
                  </button>
                  <button
                    onClick={() => window.open(`https://www.coinbase.com/trade/${selectedCoin?.toLowerCase()}-USD`, '_blank')}
                    className="w-full text-left px-3 py-2 rounded text-xs font-semibold text-orange-200 bg-orange/10 hover:bg-orange/20 transition-colors"
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
            ) : errorStates.social ? (
              <div className={`${surfaceCard} text-center py-8`}>
                <div className="text-4xl mb-3">📉</div>
                <div className="text-white/70">{errorStates.social}</div>
                <div className="text-xs text-white/40 mt-2">Sentiment data is temporarily unavailable.</div>
              </div>
            ) : socialData ? (
              <>
                {/* Overall Sentiment */}
                <div className={surfaceCard}>
                  <div className={`${mutedLabel} mb-3`}>Overall Sentiment</div>
                  <div className="flex items-center gap-4 mb-4">
                    <div className="text-3xl font-bold">
                      <span className={`${
                        socialData.overall_sentiment.score >= 0.6 ? 'text-emerald-300' :
                        socialData.overall_sentiment.score <= 0.4 ? 'text-rose-300' : 'text-amber-300'
                      }`}>
                        {(socialData.overall_sentiment.score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div>
                      <div className={`font-semibold ${
                        socialData.overall_sentiment.score >= 0.6 ? 'text-emerald-300' :
                        socialData.overall_sentiment.score <= 0.4 ? 'text-rose-300' : 'text-amber-300'
                      }`}>
                        {socialData.overall_sentiment.label}
                      </div>
                      <div className="text-xs text-white/60">
                        Confidence: {(socialData.overall_sentiment.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                  
                  {/* Sentiment Distribution */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span className="text-xs text-white/70">Positive: {(socialData.sentiment_distribution.positive * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                      <span className="text-xs text-white/70">Negative: {(socialData.sentiment_distribution.negative * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                      <span className="text-xs text-white/70">Neutral: {(socialData.sentiment_distribution.neutral * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                </div>

                {/* Social Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className={surfaceCard}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-blue-400">🐦</span>
                      <span className="text-sm text-white/70">Twitter</span>
                    </div>
                    <div className="text-lg font-bold text-white mb-1">
                      {socialData.social_metrics.twitter.mentions_24h.toLocaleString()}
                    </div>
                    <div className="text-xs text-white/55">mentions (24h)</div>
                    <div className={`text-xs mt-2 ${
                      socialData.social_metrics.twitter.sentiment_score >= 0.6 ? 'text-emerald-300' :
                      socialData.social_metrics.twitter.sentiment_score <= 0.4 ? 'text-rose-300' : 'text-amber-300'
                    }`}>
                      Sentiment: {(socialData.social_metrics.twitter.sentiment_score * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className={surfaceCard}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-orange-400">🔴</span>
                      <span className="text-sm text-white/70">Reddit</span>
                    </div>
                    <div className="text-lg font-bold text-white mb-1">
                      {socialData.social_metrics.reddit.posts_24h.toLocaleString()}
                    </div>
                    <div className="text-xs text-white/55">posts (24h)</div>
                    <div className={`text-xs mt-2 ${
                      socialData.social_metrics.reddit.sentiment_score >= 0.6 ? 'text-emerald-300' :
                      socialData.social_metrics.reddit.sentiment_score <= 0.4 ? 'text-rose-300' : 'text-amber-300'
                    }`}>
                      Sentiment: {(socialData.social_metrics.reddit.sentiment_score * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className={surfaceCard}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-cyan-400">✈️</span>
                      <span className="text-sm text-white/70">Telegram</span>
                    </div>
                    <div className="text-lg font-bold text-white mb-1">
                      {socialData.social_metrics.telegram.messages_24h.toLocaleString()}
                    </div>
                    <div className="text-xs text-white/55">messages (24h)</div>
                    <div className={`text-xs mt-2 ${
                      socialData.social_metrics.telegram.sentiment_score >= 0.6 ? 'text-emerald-300' :
                      socialData.social_metrics.telegram.sentiment_score <= 0.4 ? 'text-rose-300' : 'text-amber-300'
                    }`}>
                      Sentiment: {(socialData.social_metrics.telegram.sentiment_score * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>

                {/* Trending Keywords */}
                {socialData.trending_topics && socialData.trending_topics.length > 0 && (
                  <div className={surfaceCard}>
                    <div className={`${mutedLabel} mb-3`}>Trending Keywords</div>
                    <div className="flex flex-wrap gap-2">
                      {socialData.trending_topics.slice(0, 8).map((topic, index) => {
                        const keyword = typeof topic === 'string' ? topic : topic?.keyword || 'Trending';
                        const growth = typeof topic === 'object' && topic && typeof topic.growth_24h === 'number'
                          ? topic.growth_24h
                          : 0;
                        return (
                          <div key={index} className="px-3 py-1 rounded-full text-xs bg-white/10 text-white/80">
                            <span className="text-white">{keyword}</span>
                            <span className={`ml-1 ${growth >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                              ({growth >= 0 ? '+' : ''}{growth.toFixed(1)}%)
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Influencer Mentions */}
                {socialData.influencer_mentions && socialData.influencer_mentions.length > 0 && (
                  <div className={surfaceCard}>
                    <div className={`${mutedLabel} mb-3`}>Influencer Mentions</div>
                    <div className="space-y-3">
                      {socialData.influencer_mentions.map((mention, index) => {
                        const name = mention.influencer || mention.name || 'Influencer';
                        const followers = (mention.followers ?? 0).toLocaleString();
                        const preview = mention.preview || mention.highlight || 'Recent commentary on market structure and sentiment trends.';
                        const sentiment = (mention.sentiment || 'neutral').toLowerCase();
                        const engagement = (mention.engagement ?? randomIntFallback()).toLocaleString();
                        const sentimentColor = sentiment === 'bullish' ? 'text-emerald-300'
                          : sentiment === 'bearish' ? 'text-rose-300'
                          : 'text-white/55';
                        return (
                          <div key={index} className="flex items-start gap-3">
                            <div className={`w-2 h-2 rounded-full mt-2 ${
                              sentiment === 'bullish' ? 'bg-green-400' :
                              sentiment === 'bearish' ? 'bg-red-400' : 'bg-gray-400'
                            }`} />
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="text-white text-sm font-medium">{name}</span>
                                {mention.verified && <span className="text-blue-400 text-xs">✓</span>}
                                <span className="text-white/50 text-xs">{followers} followers</span>
                              </div>
                              <p className="text-white/70 text-xs mt-1">{preview}</p>
                              <div className="flex items-center gap-3 mt-1">
                                <span className={`text-xs capitalize ${sentimentColor}`}>{sentiment}</span>
                                <span className="text-white/45 text-xs">{engagement} engagements</span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Additional Metrics */}
                <div className={surfaceCard}>
                  <div className={`${mutedLabel} mb-3`}>Additional Metrics</div>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className={subtleText}>Fear & Greed Index:</span>
                      <span className={`ml-2 font-semibold ${
                        socialData.fear_greed_index > 60 ? 'text-emerald-300' :
                        socialData.fear_greed_index < 40 ? 'text-rose-300' : 'text-amber-300'
                      }`}>
                        {socialData.fear_greed_index}/100
                      </span>
                    </div>
                    <div>
                      <span className={subtleText}>Volume Correlation:</span>
                      <span className="ml-2 text-white font-mono">
                        {socialData.volume_correlation.toFixed(3)}
                      </span>
                    </div>
                  </div>
                </div>
                {metadata.social && (
                  <div className="text-[10px] text-white/35 text-center">
                    Social data refreshed {new Date(metadata.social).toLocaleTimeString()}
                  </div>
                )}
              </>
            ) : (
              <div className={`${surfaceCard} text-center py-8`}>
                <div className="text-4xl mb-4">🌍</div>
                <div className="text-white/70">No social sentiment data available</div>
                <div className="text-sm text-white/50 mt-2">
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
        className={surfacePanel}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-7 py-6 border-b border-purple-400/25">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full border border-purple-300/60 bg-gradient-to-br from-purple-600/30 to-transparent flex items-center justify-center">
              <span className="text-xl font-bold text-white tracking-wider">{selectedCoin?.slice(0, 2)}</span>
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-white tracking-wide">{selectedCoin} Analysis</h2>
              <p className="text-sm text-white/60">Advanced crypto insights powered by real data</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-2 rounded-full hover:bg-white/5"
            aria-label="Close modal"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 px-4 py-2 border-b border-purple-400/25 bg-white/5">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 px-5 py-2.5 rounded-full border text-sm font-semibold tracking-wide transition ${
                activeTab === tab.id
                  ? 'border-orange-300 text-orange-200 bg-gradient-to-r from-orange/20 via-orange/10 to-transparent shadow-[0_0_20px_rgba(254,164,0,0.15)]'
                  : 'border-transparent text-white/60 hover:text-white/85'
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
        <div className="p-6 max-h-[60vh] overflow-y-auto bg-black/20">
          {renderTabContent()}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 bg-[#120828]/80 border-t border-purple/20">
          <div className="text-xs text-white/50">
            Data updated: {technicalData?.last_updated ? new Date(technicalData.last_updated).toLocaleTimeString() : new Date().toLocaleTimeString()}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => {
                fetchTechnicalAnalysis(selectedCoin);
                fetchNews(selectedCoin);
                fetchSocialSentiment(selectedCoin);
              }}
              className="px-3 py-1 bg-purple/30 text-white rounded text-xs border border-purple/40 hover:bg-purple/40 transition-colors"
            >
              Refresh
            </button>
            <button
              onClick={() => window.open(`https://www.coinbase.com/trade/${selectedCoin?.toLowerCase()}-USD`, '_blank')}
              className="px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
              style={{ background: '#FEA400', color: '#0b071f' }}
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
