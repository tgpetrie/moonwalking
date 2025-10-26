// Minimal shim so TS doesn't complain if socket.io-client types are absent.
declare module 'socket.io-client' {
  export function io(url: string, opts?: any): any;
}
