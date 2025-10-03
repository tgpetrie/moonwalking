import { randomUUID } from 'crypto';

export const logger = {
  info: (msg, meta = {}) => console.log(JSON.stringify({ level: 'info', msg, ...meta, t: Date.now() })),
  error: (msg, meta = {}) => console.error(JSON.stringify({ level: 'error', msg, ...meta, t: Date.now() })),
  debug: (msg, meta = {}) => {
    if (process.env.DEBUG) console.log(JSON.stringify({ level: 'debug', msg, ...meta, t: Date.now() }));
  }
};

export function reqIdMiddleware(req, _res, next) {
  req.id = req.headers['x-request-id'] || randomUUID();
  req.start = Date.now();
  logger.info('req.start', { path: req.path, method: req.method, reqId: req.id });
  next();
}
