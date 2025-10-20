// Mobile detection and optimization utilities
// Heuristic: prefer explicit UA detection; only fall back to small-screen
// when touch is present to avoid misclassifying narrow desktop windows.
import { getEnv } from '../config.js';

export const isMobileDevice = () => {
  const env = getEnv();
  const forceMobile = (env.VITE_FORCE_MOBILE ?? 'false').toString().toLowerCase() === 'true';
  const forceDesktop = (env.VITE_FORCE_DESKTOP ?? 'false').toString().toLowerCase() === 'true';
  if (forceMobile) return true;
  if (forceDesktop) return false;

  // Check user agent for mobile devices
  const userAgent = navigator.userAgent || navigator.vendor || window.opera;
  const mobileRegex = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i;
  if (mobileRegex.test(userAgent)) return true;

  // Optional width threshold override (default 768)
  const maxW = Number(env.VITE_MOBILE_WIDTH_MAX || 768) || 768;
  const isSmallScreen = (window.innerWidth || 0) <= maxW;
  const hasTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints || 0) > 0;

  // Only treat as mobile when both small and touch-capable
  return isSmallScreen && hasTouch;
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
  if ('connection' in navigator) {
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
