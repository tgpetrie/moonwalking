import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = os.environ.get('LOG_DIR', 'backend')
LOG_FILE = os.path.join(LOG_DIR, 'server.log')

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Clear existing handlers to avoid duplicate logs in reloads
    root.handlers = []
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)
    # Rotating file handler (5 MB, keep 3 backups)
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception:
        root.warning('Could not attach rotating file handler; continuing with console only')

def log_config(config):
    """Log current configuration"""
    logging.info("=== CBMo4ers Configuration ===")
    for key, value in config.items():
        logging.info(f"{key}: {value}")
    logging.info("===============================")
