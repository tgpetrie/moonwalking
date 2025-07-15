import logging

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_config(config):
    """Log current configuration"""
    logging.info("=== CBMo4ers Configuration ===")
    for key, value in config.items():
        logging.info(f"{key}: {value}")
    logging.info("===============================")
