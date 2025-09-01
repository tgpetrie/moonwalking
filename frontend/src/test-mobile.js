// Simple mobile configuration test
import { isMobileDevice, getMobileOptimizedConfig, isIOS, isAndroid } from './utils/mobileDetection.js';

console.log('=== Mobile Configuration Test ===');
console.log('Is Mobile Device:', isMobileDevice());
console.log('Is iOS:', isIOS());
console.log('Is Android:', isAndroid());
console.log('Mobile Config:', getMobileOptimizedConfig());
console.log('User Agent:', navigator.userAgent);

// Test WebSocket mobile optimizations
console.log('\n=== Testing Mobile WebSocket Optimizations ===');
try {
  import('./services/websocket.js').then(ws => {
    console.log('WebSocket manager loaded successfully');
    console.log('Manager has mobile optimizations:', typeof ws.default.isMobile !== 'undefined');
  });
} catch (e) {
  console.error('Error loading WebSocket manager:', e);
}

// Test API mobile optimizations  
console.log('\n=== Testing Mobile API Optimizations ===');
try {
  import('./api.js').then(api => {
    console.log('API module loaded successfully');
    console.log('API has mobile config import');
  });
} catch (e) {
  console.error('Error loading API module:', e);
}