#!/usr/bin/env python3
"""
Moonwalking Notification Systems
Discord and Telegram bots for real-time alerts
"""

import asyncio
import logging
import json
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
import discord
from discord.ext import commands
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
from dataclasses import asdict

from moonwalking_alert_system import MoonwalkingAlert, AlertType, AlertSeverity


MOONWALKING_API_BASE = os.getenv("MOONWALKING_API_BASE", "http://127.0.0.1:5003").rstrip("/")

class DiscordNotifier:
    """Discord bot for Moonwalking alerts"""
    
    def __init__(self, bot_token: str, channel_id: int, webhook_url: Optional[str] = None):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.webhook_url = webhook_url
        self.logger = logging.getLogger(__name__)
        
        # Discord bot setup
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!moon ', intents=intents)
        
        self.setup_bot_commands()
        
        # Emoji mapping for alerts
        self.alert_emojis = {
            AlertType.MOONSHOT: "🚀",
            AlertType.CRATER: "📉", 
            AlertType.SENTIMENT_SPIKE: "🌊",
            AlertType.WHALE_MOVE: "🐋",
            AlertType.DIVERGENCE: "⚖️",
            AlertType.BREAKOUT: "📈",
            AlertType.FOMO_ALERT: "🔥",
            AlertType.STEALTH_MOVE: "👤",
            AlertType.NEWS_CATALYST: "📰",
            AlertType.ARBITRAGE: "💰"
        }
        
        self.severity_colors = {
            AlertSeverity.CRITICAL: 0xFF0000,  # Red
            AlertSeverity.HIGH: 0xFF8C00,      # Orange
            AlertSeverity.MEDIUM: 0xFFD700,    # Gold
            AlertSeverity.LOW: 0x00FF00,       # Green
            AlertSeverity.INFO: 0x0099FF       # Blue
        }
    
    def setup_bot_commands(self):
        """Setup Discord bot commands"""
        
        @self.bot.event
        async def on_ready():
            self.logger.info(f'🌙 Discord bot logged in as {self.bot.user}')
            
            # Set bot status
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name="crypto markets 👀"
            )
            await self.bot.change_presence(activity=activity)
        
        @self.bot.command(name='status')
        async def status(ctx):
            """Get Moonwalking system status"""
            try:
                # Get status from API
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{MOONWALKING_API_BASE}/health") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            embed = discord.Embed(
                                title="🌙 Moonwalking Status",
                                color=0x00FF00,
                                timestamp=datetime.now()
                            )
                            
                            embed.add_field(
                                name="System", 
                                value=f"✅ {data['status'].title()}", 
                                inline=True
                            )
                            embed.add_field(
                                name="WebSocket", 
                                value=f"🔗 {data['websocket_connections']} connections", 
                                inline=True
                            )
                            embed.add_field(
                                name="Detector", 
                                value="🔥 Active" if data['detector_active'] else "⚠️ Inactive", 
                                inline=True
                            )
                            
                            await ctx.send(embed=embed)
                        else:
                            await ctx.send("❌ Unable to connect to Moonwalking API")
                            
            except Exception as e:
                await ctx.send(f"❌ Error getting status: {str(e)}")
        
        @self.bot.command(name='alerts')
        async def alerts(ctx, limit: int = 5):
            """Get recent active alerts"""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{MOONWALKING_API_BASE}/alerts?limit={limit}") as resp:
                        if resp.status == 200:
                            alerts = await resp.json()
                            
                            if not alerts:
                                await ctx.send("🌙 No active alerts - markets are quiet!")
                                return
                            
                            embed = discord.Embed(
                                title="🚨 Active Alerts",
                                color=0xFF8C00,
                                timestamp=datetime.now()
                            )
                            
                            for alert in alerts[:5]:  # Show max 5
                                emoji = self.alert_emojis.get(AlertType(alert['alert_type']), "⚡")
                                
                                embed.add_field(
                                    name=f"{emoji} {alert['symbol']} - {alert['severity']}",
                                    value=f"{alert['message']}\n💪 Confidence: {alert['confidence']*100:.0f}%",
                                    inline=False
                                )
                            
                            await ctx.send(embed=embed)
                        else:
                            await ctx.send("❌ Unable to fetch alerts")
                            
            except Exception as e:
                await ctx.send(f"❌ Error getting alerts: {str(e)}")
        
        @self.bot.command(name='symbol')
        async def symbol_info(ctx, symbol: str):
            """Get detailed info for a symbol"""
            try:
                symbol = symbol.upper()
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{MOONWALKING_API_BASE}/symbols/{symbol}") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            # Determine color based on 24h change
                            change_24h = data['change_24h']
                            color = 0x00FF00 if change_24h >= 0 else 0xFF0000
                            
                            embed = discord.Embed(
                                title=f"📊 {symbol} Analysis",
                                color=color,
                                timestamp=datetime.now()
                            )
                            
                            embed.add_field(
                                name="💰 Price",
                                value=f"${data['current_price']:,.2f}",
                                inline=True
                            )
                            embed.add_field(
                                name="📈 24h Change",
                                value=f"{change_24h*100:+.2f}%",
                                inline=True
                            )
                            embed.add_field(
                                name="📊 Volume",
                                value=f"${data['volume_24h']:,.0f}",
                                inline=True
                            )
                            embed.add_field(
                                name="⚡ Momentum",
                                value=f"{data['momentum']:.3f}",
                                inline=True
                            )
                            embed.add_field(
                                name="📊 Volatility", 
                                value=f"{data['volatility']:.3f}",
                                inline=True
                            )
                            
                            # Recent alerts
                            if data['recent_alerts']:
                                recent = data['recent_alerts'][:3]
                                alerts_text = "\n".join([
                                    f"• {alert['alert_type']} ({alert['confidence']*100:.0f}%)"
                                    for alert in recent
                                ])
                                embed.add_field(
                                    name="🚨 Recent Alerts",
                                    value=alerts_text,
                                    inline=False
                                )
                            
                            await ctx.send(embed=embed)
                        else:
                            await ctx.send(f"❌ Symbol {symbol} not found")
                            
            except Exception as e:
                await ctx.send(f"❌ Error getting symbol info: {str(e)}")
        
        @self.bot.command(name='market')
        async def market_overview(ctx):
            """Get market overview"""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{MOONWALKING_API_BASE}/market") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            embed = discord.Embed(
                                title="🌍 Market Overview",
                                color=0x0099FF,
                                timestamp=datetime.now()
                            )
                            
                            # Fear & Greed meter
                            fng = data['fear_greed_index']
                            if fng <= 25:
                                fng_status = "😱 Extreme Fear"
                                fng_color = "🔴"
                            elif fng <= 45:
                                fng_status = "😰 Fear"
                                fng_color = "🟠"
                            elif fng <= 55:
                                fng_status = "😐 Neutral"
                                fng_color = "🟡"
                            elif fng <= 75:
                                fng_status = "😃 Greed"
                                fng_color = "🟢"
                            else:
                                fng_status = "🤑 Extreme Greed"
                                fng_color = "🔥"
                            
                            embed.add_field(
                                name="😱 Fear & Greed",
                                value=f"{fng_color} {fng}/100 - {fng_status}",
                                inline=False
                            )
                            embed.add_field(
                                name="₿ BTC Dominance",
                                value=f"{data['btc_dominance']:.1f}%",
                                inline=True
                            )
                            embed.add_field(
                                name="🌊 Overall Sentiment",
                                value=f"{data['overall_sentiment']*100:.0f}%",
                                inline=True
                            )
                            embed.add_field(
                                name="🌏 Active Session",
                                value=data['active_session'],
                                inline=True
                            )
                            
                            await ctx.send(embed=embed)
                        else:
                            await ctx.send("❌ Unable to fetch market data")
                            
            except Exception as e:
                await ctx.send(f"❌ Error getting market overview: {str(e)}")
    
    async def send_alert(self, alert: MoonwalkingAlert):
        """Send alert to Discord channel"""
        try:
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                self.logger.error(f"Discord channel {self.channel_id} not found")
                return
            
            # Get emoji and color for alert
            emoji = self.alert_emojis.get(alert.alert_type, "⚡")
            color = self.severity_colors.get(alert.severity, 0x0099FF)
            
            # Create embed
            embed = discord.Embed(
                title=f"{emoji} {alert.title}",
                description=alert.message,
                color=color,
                timestamp=alert.timestamp
            )
            
            # Add fields
            embed.add_field(
                name="💰 Price",
                value=f"${alert.current_price:,.2f}",
                inline=True
            )
            embed.add_field(
                name="📈 1h Change",
                value=f"{alert.price_change_1h*100:+.2f}%",
                inline=True
            )
            embed.add_field(
                name="📊 Volume Spike",
                value=f"{alert.volume_spike:.1f}x",
                inline=True
            )
            embed.add_field(
                name="🧠 Sentiment",
                value=f"{alert.sentiment_score*100:.0f}%",
                inline=True
            )
            embed.add_field(
                name="💪 Confidence",
                value=f"{alert.confidence*100:.0f}%",
                inline=True
            )
            embed.add_field(
                name="🎯 Action",
                value=alert.action,
                inline=True
            )
            
            # Add targets if available
            if alert.target_price:
                embed.add_field(
                    name="🎯 Target",
                    value=f"${alert.target_price:.2f}",
                    inline=True
                )
            if alert.stop_loss:
                embed.add_field(
                    name="🛑 Stop Loss",
                    value=f"${alert.stop_loss:.2f}",
                    inline=True
                )
            
            embed.add_field(
                name="⏱️ Time Horizon",
                value=alert.time_horizon,
                inline=True
            )
            
            # Footer with sources
            embed.set_footer(
                text=f"Sources: {', '.join(alert.sources)} | ID: {alert.id[:8]}",
                icon_url="https://cdn.discordapp.com/emojis/851461148810838016.png"
            )
            
            # Send the embed
            await channel.send(embed=embed)
            
            # Additional ping for critical alerts
            if alert.severity == AlertSeverity.CRITICAL:
                await channel.send(f"🚨 @everyone CRITICAL ALERT: {alert.symbol} {alert.alert_type.value}")
                
        except Exception as e:
            self.logger.error(f"Error sending Discord alert: {e}")
    
    async def send_webhook_alert(self, alert: MoonwalkingAlert):
        """Send alert via Discord webhook (faster alternative)"""
        if not self.webhook_url:
            return
        
        try:
            emoji = self.alert_emojis.get(alert.alert_type, "⚡")
            color = self.severity_colors.get(alert.severity, 0x0099FF)
            
            webhook_data = {
                "embeds": [{
                    "title": f"{emoji} {alert.title}",
                    "description": alert.message,
                    "color": color,
                    "timestamp": alert.timestamp.isoformat(),
                    "fields": [
                        {"name": "💰 Price", "value": f"${alert.current_price:,.2f}", "inline": True},
                        {"name": "📈 Change", "value": f"{alert.price_change_1h*100:+.2f}%", "inline": True},
                        {"name": "📊 Volume", "value": f"{alert.volume_spike:.1f}x", "inline": True},
                        {"name": "🎯 Action", "value": alert.action, "inline": True},
                        {"name": "💪 Confidence", "value": f"{alert.confidence*100:.0f}%", "inline": True}
                    ],
                    "footer": {
                        "text": f"Moonwalking by bhabit | {alert.id[:8]}"
                    }
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=webhook_data) as resp:
                    if resp.status == 204:
                        self.logger.info(f"Discord webhook alert sent for {alert.symbol}")
                    else:
                        self.logger.error(f"Discord webhook failed: {resp.status}")
                        
        except Exception as e:
            self.logger.error(f"Error sending Discord webhook: {e}")
    
    async def start(self):
        """Start the Discord bot"""
        try:
            await self.bot.start(self.bot_token)
        except Exception as e:
            self.logger.error(f"Error starting Discord bot: {e}")
    
    async def close(self):
        """Close the Discord bot"""
        await self.bot.close()


class TelegramNotifier:
    """Telegram bot for Moonwalking alerts"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger = logging.getLogger(__name__)
        
        # Initialize bot
        self.application = Application.builder().token(bot_token).build()
        
        # Setup commands
        self.setup_commands()
        
        # Emoji mapping
        self.alert_emojis = {
            AlertType.MOONSHOT: "🚀",
            AlertType.CRATER: "📉",
            AlertType.SENTIMENT_SPIKE: "🌊", 
            AlertType.WHALE_MOVE: "🐋",
            AlertType.DIVERGENCE: "⚖️",
            AlertType.BREAKOUT: "📈",
            AlertType.FOMO_ALERT: "🔥",
            AlertType.STEALTH_MOVE: "👤"
        }
    
    def setup_commands(self):
        """Setup Telegram bot commands"""
        
        async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Start command"""
            await update.message.reply_text(
                "🌙 *Moonwalking Alert Bot*\n\n"
                "Advanced crypto movement detection by bhabit\n\n"
                "*Commands:*\n"
                "/status - System status\n"
                "/alerts - Active alerts\n"
                "/symbol <SYMBOL> - Symbol info\n"
                "/market - Market overview\n"
                "/help - Show this help",
                parse_mode='Markdown'
            )
        
        async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Status command"""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{MOONWALKING_API_BASE}/health") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            status_text = (
                                f"🌙 *Moonwalking Status*\n\n"
                                f"🟢 System: {data['status'].title()}\n"
                                f"🔗 Connections: {data['websocket_connections']}\n"
                                f"🔥 Detector: {'Active' if data['detector_active'] else 'Inactive'}\n"
                                f"🕐 Updated: {datetime.now().strftime('%H:%M:%S UTC')}"
                            )
                            
                            await update.message.reply_text(status_text, parse_mode='Markdown')
                        else:
                            await update.message.reply_text("❌ Unable to connect to Moonwalking API")
                            
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")
        
        async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Alerts command"""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{MOONWALKING_API_BASE}/alerts?limit=5") as resp:
                        if resp.status == 200:
                            alerts = await resp.json()
                            
                            if not alerts:
                                await update.message.reply_text("🌙 No active alerts - markets are quiet!")
                                return
                            
                            alerts_text = "🚨 *Active Alerts*\n\n"
                            
                            for alert in alerts:
                                emoji = self.alert_emojis.get(AlertType(alert['alert_type']), "⚡")
                                alerts_text += (
                                    f"{emoji} *{alert['symbol']}* - {alert['severity']}\n"
                                    f"{alert['message']}\n"
                                    f"💪 Confidence: {alert['confidence']*100:.0f}%\n\n"
                                )
                            
                            await update.message.reply_text(alerts_text, parse_mode='Markdown')
                        else:
                            await update.message.reply_text("❌ Unable to fetch alerts")
                            
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")
        
        async def symbol_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Symbol info command"""
            if not context.args:
                await update.message.reply_text("Please provide a symbol: /symbol BTC")
                return
            
            symbol = context.args[0].upper()
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{MOONWALKING_API_BASE}/symbols/{symbol}") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            change_24h = data['change_24h']
                            change_emoji = "📈" if change_24h >= 0 else "📉"
                            
                            symbol_text = (
                                f"📊 *{symbol} Analysis*\n\n"
                                f"💰 Price: ${data['current_price']:,.2f}\n"
                                f"{change_emoji} 24h: {change_24h*100:+.2f}%\n"
                                f"📊 Volume: ${data['volume_24h']:,.0f}\n"
                                f"⚡ Momentum: {data['momentum']:.3f}\n"
                                f"📊 Volatility: {data['volatility']:.3f}"
                            )
                            
                            await update.message.reply_text(symbol_text, parse_mode='Markdown')
                        else:
                            await update.message.reply_text(f"❌ Symbol {symbol} not found")
                            
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", start_command))
        self.application.add_handler(CommandHandler("status", status_command))
        self.application.add_handler(CommandHandler("alerts", alerts_command))
        self.application.add_handler(CommandHandler("symbol", symbol_command))
    
    async def send_alert(self, alert: MoonwalkingAlert):
        """Send alert to Telegram chat"""
        try:
            emoji = self.alert_emojis.get(alert.alert_type, "⚡")
            
            # Create message text
            message_text = (
                f"{emoji} *{alert.title}*\n\n"
                f"{alert.message}\n\n"
                f"💰 Price: ${alert.current_price:,.2f}\n"
                f"📈 1h Change: {alert.price_change_1h*100:+.2f}%\n"
                f"📊 Volume: {alert.volume_spike:.1f}x\n"
                f"🧠 Sentiment: {alert.sentiment_score*100:.0f}%\n"
                f"💪 Confidence: {alert.confidence*100:.0f}%\n"
                f"🎯 Action: {alert.action}\n"
            )
            
            if alert.target_price:
                message_text += f"🎯 Target: ${alert.target_price:.2f}\n"
            if alert.stop_loss:
                message_text += f"🛑 Stop: ${alert.stop_loss:.2f}\n"
            
            message_text += f"\n⏱️ Horizon: {alert.time_horizon}"
            
            # Send message
            bot = Bot(token=self.bot_token)
            await bot.send_message(
                chat_id=self.chat_id,
                text=message_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            self.logger.info(f"Telegram alert sent for {alert.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error sending Telegram alert: {e}")
    
    async def start(self):
        """Start the Telegram bot"""
        try:
            await self.application.initialize()
            await self.application.start()
            self.logger.info("🌙 Telegram bot started")
        except Exception as e:
            self.logger.error(f"Error starting Telegram bot: {e}")
    
    async def stop(self):
        """Stop the Telegram bot"""
        try:
            await self.application.stop()
            await self.application.shutdown()
        except Exception as e:
            self.logger.error(f"Error stopping Telegram bot: {e}")


class NotificationManager:
    """Manages all notification systems"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize notifiers
        self.discord_notifier = None
        self.telegram_notifier = None
        
        # Setup notifiers based on config
        self._setup_notifiers()
    
    def _setup_notifiers(self):
        """Setup notification systems based on configuration"""
        
        # Discord setup
        discord_config = self.config.get('integrations', {}).get('discord', {})
        if discord_config.get('enabled', False):
            bot_token = discord_config.get('bot_token')
            channel_id = discord_config.get('channel_id')
            webhook_url = discord_config.get('webhook_url')
            
            if bot_token and channel_id:
                self.discord_notifier = DiscordNotifier(bot_token, int(channel_id), webhook_url)
                self.logger.info("Discord notifier configured")
        
        # Telegram setup
        telegram_config = self.config.get('integrations', {}).get('telegram', {})
        if telegram_config.get('enabled', False):
            bot_token = telegram_config.get('bot_token')
            chat_id = telegram_config.get('chat_id')
            
            if bot_token and chat_id:
                self.telegram_notifier = TelegramNotifier(bot_token, chat_id)
                self.logger.info("Telegram notifier configured")
    
    async def send_alert(self, alert: MoonwalkingAlert):
        """Send alert to all configured notification systems"""
        tasks = []
        
        # Discord notifications
        if self.discord_notifier:
            # Try webhook first (faster), fallback to bot
            if self.discord_notifier.webhook_url:
                tasks.append(self.discord_notifier.send_webhook_alert(alert))
            else:
                tasks.append(self.discord_notifier.send_alert(alert))
        
        # Telegram notifications
        if self.telegram_notifier:
            tasks.append(self.telegram_notifier.send_alert(alert))
        
        # Execute all notifications concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def start_all(self):
        """Start all notification services"""
        tasks = []
        
        if self.discord_notifier:
            tasks.append(self.discord_notifier.start())
        
        if self.telegram_notifier:
            tasks.append(self.telegram_notifier.start())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all(self):
        """Stop all notification services"""
        tasks = []
        
        if self.discord_notifier:
            tasks.append(self.discord_notifier.close())
        
        if self.telegram_notifier:
            tasks.append(self.telegram_notifier.stop())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Test notification systems
async def test_notifications():
    """Test notification systems"""
    from moonwalking_alert_system import MoonwalkingAlert, AlertType, AlertSeverity
    from datetime import datetime, timedelta
    
    # Create test alert
    test_alert = MoonwalkingAlert(
        id="test_moonshot_btc_123",
        timestamp=datetime.now(),
        symbol="BTC",
        alert_type=AlertType.MOONSHOT,
        severity=AlertSeverity.CRITICAL,
        title="🚀 BTC MOONSHOT DETECTED",
        message="BTC pumping 15.2% in 1h with 4.5x volume!",
        current_price=45250.0,
        price_change_1h=0.152,
        price_change_24h=0.089,
        volume_24h=2500000000,
        volume_spike=4.5,
        sentiment_score=0.85,
        sentiment_change=0.25,
        social_volume=15000,
        social_spike=3.2,
        momentum_score=0.78,
        volatility=0.045,
        liquidity_score=0.92,
        confidence=0.89,
        sources=['binance', 'sentiment_pipeline'],
        exchanges=['binance'],
        triggers=['price_pump_15.2%', 'volume_4.5x'],
        action="BUY",
        target_price=52000.0,
        stop_loss=40000.0,
        time_horizon="1h",
        market_cap=None,
        related_symbols=[],
        news_links=[],
        expires_at=datetime.now() + timedelta(hours=2)
    )
    
    # Test configuration
    config = {
        'integrations': {
            'discord': {
                'enabled': True,
                'bot_token': os.getenv('DISCORD_BOT_TOKEN'),
                'channel_id': os.getenv('DISCORD_CHANNEL_ID'),
                'webhook_url': os.getenv('DISCORD_WEBHOOK_URL')
            },
            'telegram': {
                'enabled': True,
                'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
                'chat_id': os.getenv('TELEGRAM_CHAT_ID')
            }
        }
    }
    
    # Initialize notification manager
    notifier = NotificationManager(config)
    
    # Send test alert
    await notifier.send_alert(test_alert)
    
    print("✅ Test notifications sent!")

if __name__ == "__main__":
    asyncio.run(test_notifications())