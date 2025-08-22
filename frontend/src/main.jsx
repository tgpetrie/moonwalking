// frontend/src/main.jsx
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './app.jsx';
import './index.css';
import injectPreconnectFromEnv from './env-preconnect.js';

injectPreconnectFromEnv(); // safe no-op if env invalid

createRoot(document.getElementById('root')).render(<App />);