import { io } from 'socket.io-client';

const socket = io('http://127.0.0.1:5001', { transports: ['websocket', 'polling'], path:'/socket.io' });

socket.on('connect', () => { console.log('connected', socket.id) });
socket.on('disconnect', () => { console.log('disconnected') });

socket.on('crypto', (d) => {
  console.log('crypto keys', Object.keys(d||{}));
  try {
    if (Array.isArray(d)) console.log('crypto array length', d.length, 'first:', JSON.stringify(d[0], null, 2));
    else if (d && Array.isArray(d.gainers)) {
      console.log('gainers length', d.gainers.length, 'first:', JSON.stringify(d.gainers[0], null, 2));
      console.log('banner length', Array.isArray(d.banner) ? d.banner.length : 'none', 'banner sample:', JSON.stringify((d.banner||[])[0]||{}, null,2));
    } else if (d && Array.isArray(d.crypto)) {
      console.log('crypto.crypto length', d.crypto.length, 'first:', JSON.stringify(d.crypto[0], null,2));
    }
  } catch(e) { console.log('crypto inspect error', e) }
});

socket.on('crypto_update', (d) => { console.log('crypto_update keys', Object.keys(d||{})); });
socket.on('prices', (d) => { console.log('prices', Object.keys(d||{}).slice(0,5)); });
socket.on('price_update', (d) => { console.log('price_update', Object.keys(d||{}).slice(0,5)); });
socket.on('alerts', (d) => { console.log('alerts', Array.isArray(d) ? d.length : typeof d); });

// run for 20s to let crypto emit happen
setTimeout(() => { console.log('done'); socket.close(); process.exit(0); }, 20000);
