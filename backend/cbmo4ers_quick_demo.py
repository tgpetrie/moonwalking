#!/usr/bin/env python3
"""
CBMo4ers Sentiment Demo - Quick Implementation
Add this to your existing CBMo4ers Flask app to see sentiment integration in action
"""

from flask import Flask, jsonify, render_template_string
import requests
from datetime import datetime
import time

app = Flask(__name__)

class CBMo4ersSentimentDemo:
    """Demo sentiment integration for CBMo4ers"""
    
    def __init__(self):
        self.fear_greed_url = "https://api.alternative.me/fng/"
        self.binance_funding_url = "https://fapi.binance.com/fapi/v1/fundingRate"
        self.coinbase_products_url = "https://api.pro.coinbase.com/products"
        self.coinbase_ticker_url = "https://api.pro.coinbase.com/products/{}/ticker"
    
    def get_sentiment_data(self):
        """Get basic sentiment data for demo"""
        try:
            # Fear & Greed Index
            fg_response = requests.get(self.fear_greed_url, timeout=10)
            fg_data = fg_response.json()
            
            # BTC Funding Rate
            funding_response = requests.get(
                self.binance_funding_url, 
                params={'symbol': 'BTCUSDT', 'limit': 1},
                timeout=10
            )
            funding_data = funding_response.json()
            
            return {
                'fear_greed': {
                    'value': int(fg_data['data'][0]['value']),
                    'classification': fg_data['data'][0]['value_classification'],
                    'emoji': self.get_sentiment_emoji(int(fg_data['data'][0]['value']))
                },
                'btc_funding': {
                    'rate': float(funding_data[0]['fundingRate']),
                    'rate_percentage': float(funding_data[0]['fundingRate']) * 100,
                    'status': self.get_funding_status(float(funding_data[0]['fundingRate']))
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Sentiment fetch error: {e}")
            return None
    
    def get_sentiment_emoji(self, fear_greed_value):
        """Get emoji for fear/greed value"""
        if fear_greed_value < 25:
            return '😨'  # Extreme Fear
        elif fear_greed_value < 45:
            return '😟'  # Fear
        elif fear_greed_value < 55:
            return '😐'  # Neutral
        elif fear_greed_value < 75:
            return '😊'  # Greed
        else:
            return '🤑'  # Extreme Greed
    
    def get_funding_status(self, funding_rate):
        """Get funding rate status"""
        if funding_rate > 0.01:  # 1%
            return 'EXTREME_POSITIVE'
        elif funding_rate > 0.005:  # 0.5%
            return 'HIGH_POSITIVE'
        elif funding_rate < -0.01:
            return 'EXTREME_NEGATIVE'
        elif funding_rate < -0.005:
            return 'HIGH_NEGATIVE'
        else:
            return 'NORMAL'
    
    def get_enhanced_gainers(self):
        """Get Coinbase gainers with sentiment context (demo)"""
        try:
            # Get Coinbase products
            products_response = requests.get(self.coinbase_products_url, timeout=10)
            products = products_response.json()
            
            # Filter for USD pairs
            usd_pairs = [p for p in products if p['quote_currency'] == 'USD' and p['status'] == 'online'][:20]
            
            # Get price data for each
            enhanced_coins = []
            sentiment = self.get_sentiment_data()
            
            for product in usd_pairs[:10]:  # Limit to 10 for demo
                try:
                    ticker_response = requests.get(
                        self.coinbase_ticker_url.format(product['id']), 
                        timeout=5
                    )
                    ticker = ticker_response.json()
                    
                    if 'price' in ticker and 'volume' in ticker:
                        # Calculate 24h change (simplified for demo)
                        current_price = float(ticker['price'])
                        volume = float(ticker['volume'])
                        
                        # Mock percentage change for demo
                        import random
                        change_percent = round(random.uniform(-15, 15), 2)
                        
                        coin_data = {
                            'symbol': product['base_currency'],
                            'pair': product['id'],
                            'price': current_price,
                            'volume': volume,
                            'changePercent': change_percent,
                            'sentiment_flags': self.analyze_coin_sentiment({
                                'symbol': product['base_currency'],
                                'changePercent': change_percent
                            }, sentiment)
                        }
                        
                        enhanced_coins.append(coin_data)
                        
                except Exception as e:
                    print(f"Error fetching {product['id']}: {e}")
                    continue
                
                time.sleep(0.1)  # Rate limiting
            
            # Sort by change percent
            enhanced_coins.sort(key=lambda x: x['changePercent'], reverse=True)
            
            return enhanced_coins, sentiment
            
        except Exception as e:
            print(f"Enhanced gainers error: {e}")
            return [], None
    
    def analyze_coin_sentiment(self, coin, sentiment):
        """Analyze individual coin with sentiment context"""
        if not sentiment:
            return []
        
        flags = []
        fear_greed = sentiment['fear_greed']['value']
        change = coin['changePercent']
        funding_status = sentiment['btc_funding']['status']
        
        # Fear opportunity
        if fear_greed < 25 and change < -5:
            flags.append({
                'type': 'fear_opportunity',
                'icon': '💎',
                'message': 'Fear opportunity - potential bottom',
                'color': '#10b981'
            })
        
        # Greed warning  
        if fear_greed > 75 and change > 8:
            flags.append({
                'type': 'greed_warning',
                'icon': '⚠️',
                'message': 'Extreme greed - consider profit taking',
                'color': '#ef4444'
            })
        
        # Contrarian signal
        if fear_greed < 30 and change > 5:
            flags.append({
                'type': 'contrarian_strength',
                'icon': '💪',
                'message': 'Rising despite fear - strong signal',
                'color': '#8b5cf6'
            })
        
        # Funding correlation (for major coins)
        if coin['symbol'] in ['BTC', 'ETH'] and funding_status in ['EXTREME_POSITIVE', 'EXTREME_NEGATIVE']:
            flags.append({
                'type': 'funding_alert',
                'icon': '⚡',
                'message': f'Extreme funding detected - {funding_status.lower()}',
                'color': '#f97316'
            })
        
        return flags

# Initialize sentiment demo
sentiment_demo = CBMo4ersSentimentDemo()

@app.route('/api/sentiment-demo')
def sentiment_demo_endpoint():
    """Demo sentiment endpoint"""
    sentiment_data = sentiment_demo.get_sentiment_data()
    if sentiment_data:
        return jsonify(sentiment_data)
    return jsonify({'error': 'Sentiment data unavailable'}), 503

@app.route('/api/gainers-enhanced-demo')
def gainers_enhanced_demo():
    """Demo enhanced gainers with sentiment"""
    enhanced_coins, sentiment = sentiment_demo.get_enhanced_gainers()
    
    return jsonify({
        'coins': enhanced_coins,
        'market_sentiment': sentiment,
        'cbmo4ers_insights': generate_cbmo4ers_insights(sentiment),
        'timestamp': datetime.now().isoformat()
    })

def generate_cbmo4ers_insights(sentiment):
    """Generate CBMo4ers-specific insights"""
    if not sentiment:
        return {}
    
    fear_greed = sentiment['fear_greed']['value']
    funding_rate = sentiment['btc_funding']['rate']
    
    # Moonwalkin momentum context
    if fear_greed < 25:
        momentum_context = {
            'phase': 'FEAR_OPPORTUNITY',
            'action': 'Look for coins breaking higher despite fear',
            'confidence': 'MEDIUM',
            'moonwalkin_potential': 'HIGH'
        }
    elif fear_greed > 75:
        momentum_context = {
            'phase': 'GREED_CAUTION',
            'action': 'Take profits on extended moves',
            'confidence': 'HIGH',
            'moonwalkin_potential': 'LOW'
        }
    else:
        momentum_context = {
            'phase': 'NEUTRAL_TRENDING',
            'action': 'Follow momentum cleanly',
            'confidence': 'HIGH',
            'moonwalkin_potential': 'MEDIUM'
        }
    
    # Impulse intelligence
    impulse_advice = get_impulse_advice(fear_greed, funding_rate)
    
    return {
        'momentum_context': momentum_context,
        'impulse_advice': impulse_advice,
        'market_phase': classify_market_phase(fear_greed),
        'next_update': 'Updates every 5 minutes'
    }

def get_impulse_advice(fear_greed, funding_rate):
    """Get impulse trading advice"""
    if fear_greed > 80:
        return {
            'message': '⚠️ Extreme greed detected - resist FOMO impulses',
            'action': 'Set alerts instead of buying',
            'type': 'RESIST_IMPULSE'
        }
    elif fear_greed < 20:
        return {
            'message': '💎 Extreme fear - override panic selling impulse',
            'action': 'Research opportunities instead',
            'type': 'OVERRIDE_FEAR'
        }
    elif abs(funding_rate) > 0.01:
        return {
            'message': '⚡ Extreme funding detected - prepare for volatility',
            'action': 'Smaller position sizes recommended',
            'type': 'CAUTION'
        }
    else:
        return {
            'message': '✅ Neutral conditions - trade your plan',
            'action': 'Follow momentum signals',
            'type': 'NORMAL'
        }

def classify_market_phase(fear_greed):
    """Classify current market phase"""
    if fear_greed < 25:
        return 'ACCUMULATION'
    elif fear_greed < 45:
        return 'RECOVERY'
    elif fear_greed < 55:
        return 'TRENDING'
    elif fear_greed < 75:
        return 'EUPHORIA'
    else:
        return 'DISTRIBUTION'

@app.route('/')
def demo_dashboard():
    """Demo dashboard showing CBMo4ers with sentiment"""
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CBMo4ers + Sentiment Demo</title>
    <style>
        body {
            background: #000;
            color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo {
            background: linear-gradient(135deg, #8b5cf6, #ec4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2rem;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .tagline {
            color: #f97316;
            font-size: 1rem;
            margin-bottom: 20px;
        }
        .sentiment-bar {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 30px;
            padding: 15px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .sentiment-item {
            text-align: center;
        }
        .sentiment-emoji {
            font-size: 1.5rem;
            display: block;
            margin-bottom: 5px;
        }
        .sentiment-label {
            font-size: 0.9rem;
            color: #ccc;
        }
        .sentiment-value {
            font-weight: bold;
            color: #8b5cf6;
        }
        .coins-table {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            overflow: hidden;
        }
        .table-header {
            background: rgba(139, 92, 246, 0.2);
            padding: 15px;
            font-weight: bold;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 2fr;
            gap: 10px;
        }
        .coin-row {
            padding: 12px 15px;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 2fr;
            gap: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            transition: background 0.3s ease;
        }
        .coin-row:hover {
            background: rgba(255, 255, 255, 0.05);
        }
        .coin-symbol {
            font-weight: bold;
        }
        .change-positive {
            color: #10b981;
        }
        .change-negative {
            color: #ef4444;
        }
        .sentiment-flags {
            display: flex;
            gap: 5px;
            align-items: center;
        }
        .sentiment-flag {
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.8rem;
            border: 1px solid;
        }
        .loading {
            text-align: center;
            padding: 50px;
            color: #8b5cf6;
        }
        .insights-panel {
            margin-top: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .insight-item {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(139, 92, 246, 0.1);
            border-radius: 5px;
            border-left: 3px solid #8b5cf6;
        }
        .update-time {
            text-align: center;
            color: #666;
            font-size: 0.8rem;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">CBMo4ers</div>
            <div class="tagline">Profits Buy Impulse + Market Psychology</div>
        </div>
        
        <div id="sentiment-bar" class="sentiment-bar">
            <div class="loading">Loading sentiment data...</div>
        </div>
        
        <div class="coins-table">
            <div class="table-header">
                <div>Symbol</div>
                <div>Change %</div>
                <div>Volume</div>
                <div>Sentiment Signals</div>
            </div>
            <div id="coins-container">
                <div class="loading">Loading enhanced gainers...</div>
            </div>
        </div>
        
        <div id="insights-panel" class="insights-panel" style="display: none;">
            <h3>CBMo4ers Insights</h3>
            <div id="insights-content"></div>
        </div>
        
        <div class="update-time" id="update-time"></div>
    </div>

    <script>
        let updateInterval;
        
        async function fetchSentimentData() {
            try {
                const response = await fetch('/api/gainers-enhanced-demo');
                const data = await response.json();
                
                updateSentimentBar(data.market_sentiment);
                updateCoinsTable(data.coins);
                updateInsights(data.cbmo4ers_insights);
                
                document.getElementById('update-time').textContent = 
                    `Last updated: ${new Date().toLocaleTimeString()}`;
                    
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }
        
        function updateSentimentBar(sentiment) {
            if (!sentiment) return;
            
            const sentimentBar = document.getElementById('sentiment-bar');
            sentimentBar.innerHTML = `
                <div class="sentiment-item">
                    <span class="sentiment-emoji">${sentiment.fear_greed.emoji}</span>
                    <div class="sentiment-label">Market Mood</div>
                    <div class="sentiment-value">${sentiment.fear_greed.classification}</div>
                </div>
                <div class="sentiment-item">
                    <span class="sentiment-emoji">⚡</span>
                    <div class="sentiment-label">BTC Funding</div>
                    <div class="sentiment-value">${sentiment.btc_funding.rate_percentage.toFixed(3)}%</div>
                </div>
                <div class="sentiment-item">
                    <span class="sentiment-emoji">🧠</span>
                    <div class="sentiment-label">Fear/Greed</div>
                    <div class="sentiment-value">${sentiment.fear_greed.value}/100</div>
                </div>
            `;
        }
        
        function updateCoinsTable(coins) {
            const container = document.getElementById('coins-container');
            
            if (!coins || coins.length === 0) {
                container.innerHTML = '<div class="loading">No data available</div>';
                return;
            }
            
            container.innerHTML = coins.map(coin => `
                <div class="coin-row">
                    <div class="coin-symbol">${coin.symbol}</div>
                    <div class="${coin.changePercent >= 0 ? 'change-positive' : 'change-negative'}">
                        ${coin.changePercent >= 0 ? '+' : ''}${coin.changePercent}%
                    </div>
                    <div>${coin.volume.toLocaleString()}</div>
                    <div class="sentiment-flags">
                        ${coin.sentiment_flags.map(flag => `
                            <span class="sentiment-flag" style="border-color: ${flag.color}; color: ${flag.color};" title="${flag.message}">
                                ${flag.icon}
                            </span>
                        `).join('')}
                    </div>
                </div>
            `).join('');
        }
        
        function updateInsights(insights) {
            if (!insights) return;
            
            const panel = document.getElementById('insights-panel');
            const content = document.getElementById('insights-content');
            
            content.innerHTML = `
                <div class="insight-item">
                    <strong>Market Phase:</strong> ${insights.market_phase}
                </div>
                <div class="insight-item">
                    <strong>Momentum Context:</strong> ${insights.momentum_context.phase} - ${insights.momentum_context.action}
                </div>
                <div class="insight-item">
                    <strong>Impulse Intelligence:</strong> ${insights.impulse_advice.message}
                </div>
            `;
            
            panel.style.display = 'block';
        }
        
        // Initial load
        fetchSentimentData();
        
        // Update every 30 seconds for demo
        updateInterval = setInterval(fetchSentimentData, 30000);
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (updateInterval) {
                clearInterval(updateInterval);
            }
        });
    </script>
</body>
</html>
    """)

if __name__ == '__main__':
    print("🚀 CBMo4ers Sentiment Demo Starting...")
    print("📊 Visit http://localhost:5000 to see sentiment-enhanced momentum tracking")
    print("🧠 Features included:")
    print("   - Real-time Fear & Greed Index")
    print("   - BTC funding rate analysis")
    print("   - Sentiment flags on price movements") 
    print("   - CBMo4ers-specific trading insights")
    print("   - BHABIT design integration")
    
    app.run(debug=True, host='0.0.0.0', port=5000)