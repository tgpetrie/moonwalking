import React, { useState, useEffect } from 'react';
import { isMobileDevice, isIOS, isAndroid, isSafari, getMobileOptimizedConfig } from '../utils/mobileDetection.js';

export default function MobileDebugger() {
  const [networkInfo, setNetworkInfo] = useState(null);
  const [isVisible, setIsVisible] = useState(!document.hidden);
  
  // Only show debug info when debug param is present
  if (!window.location.search.includes('debug')) {
    return null;
  }

  useEffect(() => {
    // Monitor network changes
    if ('connection' in navigator) {
      const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      const updateNetworkInfo = () => {
        setNetworkInfo({
          effectiveType: connection.effectiveType,
          downlink: connection.downlink,
          rtt: connection.rtt,
          saveData: connection.saveData
        });
      };
      updateNetworkInfo();
      connection.addEventListener('change', updateNetworkInfo);
      
      return () => connection.removeEventListener('change', updateNetworkInfo);
    }
  }, []);

  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsVisible(!document.hidden);
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  const mobile = isMobileDevice();
  const config = getMobileOptimizedConfig();
  const userAgent = navigator.userAgent;
  
  return (
    <div className="fixed bottom-2 left-2 z-[9999] bg-black/90 text-white text-xs p-2 rounded max-w-xs max-h-48 overflow-y-auto">
      <div className="font-bold mb-1 text-yellow-300">📱 Mobile Debug</div>
      <div>Mobile: {mobile ? '✅' : '❌'} ({window.innerWidth}x{window.innerHeight})</div>
      <div>iOS: {isIOS() ? '✅' : '❌'} | Android: {isAndroid() ? '✅' : '❌'}</div>
      <div>Safari: {isSafari() ? '✅' : '❌'}</div>
      <div>Visible: {isVisible ? '✅' : '❌'}</div>
      
      {networkInfo && (
        <div className="mt-1 pt-1 border-t border-gray-600">
          <div>Network: {networkInfo.effectiveType}</div>
          <div>Speed: {networkInfo.downlink}Mbps</div>
          <div>RTT: {networkInfo.rtt}ms</div>
          {networkInfo.saveData && <div className="text-orange-300">Save Data: ON</div>}
        </div>
      )}
      
      <div className="mt-1 pt-1 border-t border-gray-600">
        <div>Fetch TO: {config.fetchTimeout}ms</div>
        <div>Poll: {config.pollingInterval}ms</div>
        <div>Cache: {config.cacheDuration}ms</div>
        <div>Throttle: {config.throttleMs}ms</div>
      </div>
      
      <div className="mt-1 pt-1 border-t border-gray-600 text-gray-400">
        {userAgent.substring(0, 40)}...
      </div>
    </div>
  );
}