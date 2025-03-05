import logging
import sys
from pathlib import Path

def setup_logger():
    """Configure and return a logger instance."""
    logger = logging.getLogger('wireless_ap_test')
    
    if not logger.handlers:  # Avoid adding handlers multiple times
        logger.setLevel(logging.INFO)
        
        # Create formatters and handlers
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / 'wireless_ap_test.log')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger