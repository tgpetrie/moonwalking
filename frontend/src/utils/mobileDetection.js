// Mobile detection and optimization utilities
export const isMobileDevice = () => {
  // Check user agent for mobile devices
  const userAgent = navigator.userAgent || navigator.vendor || window.opera;
  const mobileRegex = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i;
  
  // Also check screen size as backup
  const isSmallScreen = window.innerWidth <= 768;
  
  return mobileRegex.test(userAgent) || isSmallScreen;
};

export const isIOS = () => {
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
};

export const isAndroid = () => {
  return /Android/.test(navigator.userAgent);
};

export const isSafari = () => {
  return /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
};

// Mobile-optimized timeouts and intervals
export const getMobileOptimizedConfig = () => {
  const isMobile = isMobileDevice();
  
  return {
    // Longer timeouts for mobile networks
    fetchTimeout: isMobile ? 8000 : 5000,
    
    // More frequent polling for mobile (shorter intervals to catch network changes)
    pollingInterval: isMobile ? 8000 : 10000,
    
    // Shorter WebSocket reconnect attempts on mobile
    maxReconnectAttempts: isMobile ? 3 : 5,
    
    // Faster reconnect on mobile (network switches happen more often)
    reconnectDelay: isMobile ? 2000 : 5000,
    
    // Longer cache duration on mobile to reduce network requests
    cacheDuration: isMobile ? 15000 : 10000,
    
    // Reduced throttle time for mobile responsiveness
    throttleMs: isMobile ? 5000 : 15000
  };
};

// Check if device is in background/foreground
export const addVisibilityChangeListener = (callback) => {
  const handleVisibilityChange = () => {
    callback(!document.hidden);
  };
  
  document.addEventListener('visibilitychange', handleVisibilityChange);
  
  // Return cleanup function
  return () => {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  };
};

// Network change detection for mobile
export const addNetworkChangeListener = (callback) => {
  // Check for the existence of the API. `navigator.connection` can exist but be `null` or `undefined` in some test environments.
  if ('connection' in navigator && navigator.connection) {
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    
    const handleConnectionChange = () => {
      callback({
        effectiveType: connection.effectiveType,
        downlink: connection.downlink,
        rtt: connection.rtt
      });
    };
    
    connection.addEventListener('change', handleConnectionChange);
    
    return () => {
      connection.removeEventListener('change', handleConnectionChange);
    };
  }
  
  // Fallback for browsers without Network Information API
  return () => {};
};