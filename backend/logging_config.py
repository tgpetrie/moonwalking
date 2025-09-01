import logging, json, os
from logging.handlers import RotatingFileHandler
from contextvars import ContextVar

# Context variable for per-request correlation id
REQUEST_ID_CTX: ContextVar[str | None] = ContextVar('request_id', default=None)

LOG_DIR = os.environ.get('LOG_DIR', 'backend')
LOG_FILE = os.path.join(LOG_DIR, 'server.log')

class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        rid = None
        try:
            rid = REQUEST_ID_CTX.get()
        except Exception:
            rid = None
        # Attach even if None for uniformity
        record.correlation_id = rid
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        base = {
            'ts': self.formatTime(record, datefmt='%Y-%m-%dT%H:%M:%S.%fZ'),
            'level': record.levelname,
            'msg': record.getMessage(),
            'logger': record.name,
            'correlation_id': getattr(record, 'correlation_id', None),
        }
        if record.exc_info:
            base['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Clear existing handlers to avoid duplicate logs in reloads
    root.handlers = []
    use_json = os.environ.get('LOG_FORMAT','').lower() == 'json'
    if use_json:
        fmt = JsonFormatter()
    else:
        fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(correlation_id)s - %(message)s')
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.addFilter(CorrelationIdFilter())
    root.addHandler(ch)
    # Rotating file handler (5 MB, keep 3 backups)
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
        fh.setFormatter(fmt)
        fh.addFilter(CorrelationIdFilter())
        root.addHandler(fh)
    except Exception:
        root.warning('Could not attach rotating file handler; continuing with console only')

def log_config(config):
    """Log current configuration"""
    logging.info("=== CBMo4ers Configuration ===")
    for key, value in config.items():
        logging.info(f"{key}: {value}")
    logging.info("===============================")
