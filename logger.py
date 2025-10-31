"""
Logging utilities for the market maker bot
"""
from datetime import datetime


def log(message: str) -> None:
    """Print timestamped log message"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")
