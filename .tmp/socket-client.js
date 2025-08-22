// Temporary socket.io-client script to listen for tables:update
const io = require('socket.io-client');
const socket = io('http://localhost:5001');

socket.on('connect', () => {
  console.log('connected to backend socket, id', socket.id);
});

socket.on('connect_error', (err) => {
  console.error('connect_error', err.message);
});

socket.on('tables:update', (payload) => {
  console.log('tables:update', typeof payload, payload && payload.length ? `len=${payload.length}` : payload);
});

socket.on('disconnect', () => console.log('disconnected'));

setTimeout(() => {
  console.log('exit after 30s');
  process.exit(0);
}, 30000);
