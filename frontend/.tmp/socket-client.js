// Temporary socket.io-client script to listen for tables:update (ES module)
import { io } from 'socket.io-client';

const socket = io('http://localhost:5001');

socket.on('connect', () => {
  console.log('connected to backend socket, id', socket.id);
});

socket.on('connect_error', (err) => {
  console.error('connect_error', err.message);
});

// Listen for known backend event names
const events = ['tables:update','crypto','crypto_update','prices','price_update','alerts','alerts_update','alerts_log'];
events.forEach(e => {
  socket.on(e, (payload) => {
    try {
      const summary = (payload && typeof payload === 'object') ? JSON.stringify(payload).slice(0, 1000) : String(payload);
      console.log(`${e} -> type=${typeof payload} summary=`, summary);
    } catch (err) {
      console.log(`${e} -> (unserializable)`, payload);
    }
  });
});

socket.on('disconnect', () => console.log('disconnected'));

setTimeout(() => {
  console.log('exit after 120s');
  process.exit(0);
}, 120000);
