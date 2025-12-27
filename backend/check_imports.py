import sys
import os

# Add current directory to sys.path
sys.path.append(os.getcwd())

print(f"Current working directory: {os.getcwd()}")
print(f"sys.path: {sys.path}")

try:
    from backend.chinese_sources import ChineseSourceHandler
    print("SUCCESS: Imported ChineseSourceHandler from backend.chinese_sources")
except ImportError as e:
    print(f"FAILED: Could not import ChineseSourceHandler from backend.chinese_sources: {e}")
    try:
        from chinese_sources import ChineseSourceHandler
        print("SUCCESS: Imported ChineseSourceHandler from chinese_sources")
    except ImportError as e2:
        print(f"FAILED: Could not import ChineseSourceHandler from chinese_sources: {e2}")

try:
    from backend.telegram_handler import TelegramHandler
    print("SUCCESS: Imported TelegramHandler from backend.telegram_handler")
except ImportError as e:
    print(f"FAILED: Could not import TelegramHandler from backend.telegram_handler: {e}")
    try:
        from telegram_handler import TelegramHandler
        print("SUCCESS: Imported TelegramHandler from telegram_handler")
    except ImportError as e2:
        print(f"FAILED: Could not import TelegramHandler from telegram_handler: {e2}")
