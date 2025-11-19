# Moonwalking Sentiment API - Environment Variables
# Copy this file to .env and fill in your credentials

# ============================================================================
# REDDIT API (Required for Reddit data collection)
# ============================================================================
# Get credentials from: https://www.reddit.com/prefs/apps
# Create a "script" app and copy the credentials below

REDDIT_CLIENT_ID=YOUR_REDDIT_CLIENT_ID_HERE  # pragma: allowlist secret
REDDIT_CLIENT_SECRET=YOUR_REDDIT_CLIENT_SECRET_HERE  # pragma: allowlist secret

# ============================================================================
# TWITTER/X API (Optional - for Twitter sentiment)
# ============================================================================
# Get credentials from: https://developer.twitter.com/en/portal/dashboard

# TWITTER_API_KEY=EXAMPLE_TWITTER_API_KEY  # pragma: allowlist secret
# TWITTER_API_SECRET=EXAMPLE_TWITTER_API_SECRET  # pragma: allowlist secret
# TWITTER_ACCESS_TOKEN=EXAMPLE_TWITTER_ACCESS_TOKEN  # pragma: allowlist secret
# TWITTER_ACCESS_SECRET=EXAMPLE_TWITTER_ACCESS_SECRET  # pragma: allowlist secret

# ============================================================================
# TELEGRAM BOT (Optional - for Telegram monitoring)
# ============================================================================
# Create bot with @BotFather on Telegram

# TELEGRAM_BOT_TOKEN=EXAMPLE_TELEGRAM_BOT_TOKEN  # pragma: allowlist secret

# ============================================================================
# LUNARCRUSH API (Optional - Premium social data)
# ============================================================================
# Get API key from: https://lunarcrush.com/developers/api

# LUNARCRUSH_API_KEY=EXAMPLE_LUNARCRUSH_API_KEY  # pragma: allowlist secret

# ============================================================================
# CRYPTOPANIC API (Optional - News aggregator)
# ============================================================================
# Get API key from: https://cryptopanic.com/developers/api/

# CRYPTOPANIC_API_KEY=EXAMPLE_CRYPTOPANIC_API_KEY  # pragma: allowlist secret

# ============================================================================
# COINGECKO API (Optional - Pro tier for higher limits)
# ============================================================================
# Free tier works without key, Pro tier needs API key

# COINGECKO_API_KEY=EXAMPLE_COINGECKO_API_KEY  # pragma: allowlist secret

# ============================================================================
# DATABASE (Optional - for persistent storage)
# ============================================================================

# PostgreSQL
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_DB=moonwalking
# POSTGRES_USER=moonwalking
# POSTGRES_PASSWORD=EXAMPLE_POSTGRES_PASSWORD  # pragma: allowlist secret

# ============================================================================
# REDIS CACHE (Optional - for distributed caching)
# ============================================================================

# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_PASSWORD=EXAMPLE_REDIS_PASSWORD  # pragma: allowlist secret
# REDIS_DB=0

# ============================================================================
# API CONFIGURATION
# ============================================================================

# API_HOST=0.0.0.0
# API_PORT=8001
# API_DEBUG=false

# ============================================================================
# LOGGING
# ============================================================================

# LOG_LEVEL=INFO
# LOG_FILE=./logs/sentiment.log

# ============================================================================
# SECURITY (Optional)
# ============================================================================

# API_KEY=EXAMPLE_API_KEY_FOR_AUTHENTICATED_ENDPOINTS  # pragma: allowlist secret
# WEBHOOK_SECRET=EXAMPLE_WEBHOOK_SECRET  # pragma: allowlist secret
