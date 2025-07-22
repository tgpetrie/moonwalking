import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './app.jsx';
import '../index.css';

// Responsive best practices: index.css already includes Tailwind and responsive settings.
// No changes needed here, but ensure root element is used for hydration.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
