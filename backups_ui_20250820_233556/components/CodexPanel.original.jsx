import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../context/websocketcontext.jsx';

const CodexPanel = ({ isOpen, onClose, selectedCoin }) => {
  const [activeTab, setActiveTab] = useState('analysis');
  const [isLoading, setIsLoading] = useState(false);
  const modalRef = useRef(null);
  const { latestData, fetchPricesForSymbols } = useWebSocket();

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

  const renderTabContent = () => {
    switch (activeTab) {
      case 'analysis':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="text-sm text-gray-400 mb-2">Current Price</div>
                <div className="text-2xl font-bold text-teal">
                  ${coinData?.price || coinData?.current_price || 'N/A'}
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
            
            <div className="bg-gray-800/30 rounded-lg p-4">
              <div className="text-sm text-gray-400 mb-3">Technical Indicators</div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-300">RSI (14)</span>
                  <span className="text-yellow-400">Coming Soon</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300">MACD</span>
                  <span className="text-yellow-400">Coming Soon</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300">Volume</span>
                  <span className="text-yellow-400">Coming Soon</span>
                </div>
              </div>
            </div>
          </div>
        );
      
      case 'news':
        return (
          <div className="space-y-4">
            <div className="text-center py-8">
              <div className="text-4xl mb-4">📰</div>
              <div className="text-gray-400">News feed coming soon</div>
              <div className="text-sm text-gray-500 mt-2">
                Latest {selectedCoin} news and updates will appear here
              </div>
            </div>
          </div>
        );
      
      case 'charts':
        return (
          <div className="space-y-4">
            <div className="text-center py-8">
              <div className="text-4xl mb-4">📈</div>
              <div className="text-gray-400">Advanced charts coming soon</div>
              <div className="text-sm text-gray-500 mt-2">
                Interactive {selectedCoin} price charts with technical analysis
              </div>
            </div>
          </div>
        );
      
      case 'social':
        return (
          <div className="space-y-4">
            <div className="text-center py-8">
              <div className="text-4xl mb-4">🌍</div>
              <div className="text-gray-400">Social sentiment coming soon</div>
              <div className="text-sm text-gray-500 mt-2">
                Real-time social media sentiment for {selectedCoin}
              </div>
            </div>
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
              <p className="text-gray-400 text-sm">Advanced crypto insights</p>
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
            Data updated: {new Date().toLocaleTimeString()}
          </div>
          <div className="flex gap-2">
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