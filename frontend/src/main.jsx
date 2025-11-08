import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';
import './styles/animations.css';
import { WatchlistProvider } from './context/WatchlistContext.jsx';
import { WebSocketProvider } from './context/websocketcontext.jsx';

// Wrap the app with WebSocketProvider so any component calling useWebSocket()
// won't throw due to missing provider. WebSocketProvider should be above
// WatchlistProvider because some watchlist components call the websocket hook.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <WebSocketProvider>
      <WatchlistProvider>
        <App />
      </WatchlistProvider>
    </WebSocketProvider>
  </React.StrictMode>
);
