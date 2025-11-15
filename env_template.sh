# Moonwalking Sentiment API - Environment Variables
# Copy this file to .env and fill in your credentials

# ============================================================================
# REDDIT API (Required for Reddit data collection)
# ============================================================================
# Get credentials from: https://www.reddit.com/prefs/apps
# Create a "script" app and copy the credentials below

REDDIT_CLIENT_ID=your_reddit_client_id_here
REDDIT_CLIENT_SECRET=your_reddit_client_secret_here

# ============================================================================
# TWITTER/X API (Optional - for Twitter sentiment)
# ============================================================================
# Get credentials from: https://developer.twitter.com/en/portal/dashboard

# TWITTER_API_KEY=your_twitter_api_key
# TWITTER_API_SECRET=your_twitter_api_secret
# TWITTER_ACCESS_TOKEN=your_twitter_access_token
# TWITTER_ACCESS_SECRET=your_twitter_access_secret

# ============================================================================
# TELEGRAM BOT (Optional - for Telegram monitoring)
# ============================================================================
# Create bot with @BotFather on Telegram

# TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# ============================================================================
# LUNARCRUSH API (Optional - Premium social data)
# ============================================================================
# Get API key from: https://lunarcrush.com/developers/api

# LUNARCRUSH_API_KEY=your_lunarcrush_api_key

# ============================================================================
# CRYPTOPANIC API (Optional - News aggregator)
# ============================================================================
# Get API key from: https://cryptopanic.com/developers/api/

# CRYPTOPANIC_API_KEY=your_cryptopanic_api_key

# ============================================================================
# COINGECKO API (Optional - Pro tier for higher limits)
# ============================================================================
# Free tier works without key, Pro tier needs API key

# COINGECKO_API_KEY=your_coingecko_api_key

# ============================================================================
# DATABASE (Optional - for persistent storage)
# ============================================================================

# PostgreSQL
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_DB=moonwalking
# POSTGRES_USER=moonwalking
# POSTGRES_PASSWORD=your_secure_password

# ============================================================================
# REDIS CACHE (Optional - for distributed caching)
# ============================================================================

# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_PASSWORD=
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

# API_KEY=your_api_key_for_authenticated_endpoints
# WEBHOOK_SECRET=your_webhook_secret
