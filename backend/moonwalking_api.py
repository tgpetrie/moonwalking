#!/usr/bin/env python3
"""
Moonwalking API - Dashboard Integration
FastAPI endpoints for the Moonwalking alert system
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import redis
import uvicorn

# Import our Moonwalking components
from moonwalking_alert_system import MoonwalkingDetector, MoonwalkingAlert, AlertType, AlertSeverity

# Pydantic models for API
class AlertResponse(BaseModel):
    id: str
    timestamp: datetime
    symbol: str
    alert_type: str
    severity: str
    title: str
    message: str
    current_price: float
    price_change_1h: float
    price_change_24h: float
    volume_spike: float
    sentiment_score: float
    confidence: float
    action: str
    expires_at: datetime

class MarketOverview(BaseModel):
    fear_greed_index: int
    btc_dominance: float
    overall_sentiment: float
    active_session: str
    total_market_cap: Optional[float] = None
    market_trend: str = "neutral"

class SymbolPrice(BaseModel):
    symbol: str
    price: float
    change_1h: float
    change_24h: float
    volume_24h: float
    market_cap: Optional[float] = None

class AlertSettings(BaseModel):
    moonshot_threshold: float = Field(default=0.15, ge=0.05, le=0.5)
    crater_threshold: float = Field(default=-0.12, ge=-0.5, le=-0.05)
    volume_spike_threshold: float = Field(default=3.0, ge=1.5, le=10.0)
    sentiment_spike_threshold: float = Field(default=0.25, ge=0.1, le=0.5)
    fomo_threshold: float = Field(default=0.8, ge=0.6, le=0.95)
    confidence_threshold: float = Field(default=0.6, ge=0.3, le=0.9)
    notifications_enabled: bool = True
    sound_enabled: bool = True
    auto_acknowledge: bool = False

class MoonwalkingAPI:
    """FastAPI application for Moonwalking dashboard"""
    
    def __init__(self):
        self.app = FastAPI(
            title="🌙 Moonwalking API",
            description="Advanced Crypto Movement Detection by bhabit",
            version="1.0.0"
        )
        
        # CORS middleware for frontend
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Initialize components
        self.detector = None
        self.redis_client = redis.Redis(decode_responses=True)
        self.websocket_connections: List[WebSocket] = []
        self.logger = logging.getLogger(__name__)
        
        # Setup routes
        self._setup_routes()
        
        # Background tasks
        self.background_tasks = set()
    
    def _setup_routes(self):
        """Setup all API routes"""
        
        @self.app.on_event("startup")
        async def startup_event():
            """Initialize the Moonwalking detector on startup"""
            await self.initialize_detector()
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            """Cleanup on shutdown"""
            await self.cleanup()
        
        @self.app.get("/")
        async def root():
            """Root endpoint with API information"""
            return {
                "name": "🌙 Moonwalking API",
                "description": "Advanced Crypto Movement Detection by bhabit",
                "version": "1.0.0",
                "status": "active" if self.detector else "initializing",
                "endpoints": {
                    "alerts": "/alerts",
                    "market": "/market",
                    "symbols": "/symbols",
                    "settings": "/settings",
                    "websocket": "/ws/alerts"
                }
            }
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            status = "healthy" if self.detector else "initializing"
            return {
                "status": status,
                "timestamp": datetime.now(),
                "detector_active": bool(self.detector),
                "websocket_connections": len(self.websocket_connections)
            }
        
        @self.app.get("/alerts", response_model=List[AlertResponse])
        async def get_active_alerts(
            limit: int = 50,
            severity: Optional[str] = None,
            symbol: Optional[str] = None,
            alert_type: Optional[str] = None
        ):
            """Get active alerts with optional filtering"""
            if not self.detector:
                raise HTTPException(status_code=503, detail="Detector not initialized")
            
            alerts = self.detector.get_active_alerts()
            
            # Apply filters
            if severity:
                alerts = [a for a in alerts if severity.upper() in a.severity.value]
            if symbol:
                alerts = [a for a in alerts if a.symbol.upper() == symbol.upper()]
            if alert_type:
                alerts = [a for a in alerts if alert_type.upper() in a.alert_type.value]
            
            # Convert to response format
            alert_responses = []
            for alert in alerts[:limit]:
                alert_responses.append(AlertResponse(
                    id=alert.id,
                    timestamp=alert.timestamp,
                    symbol=alert.symbol,
                    alert_type=alert.alert_type.value,
                    severity=alert.severity.value,
                    title=alert.title,
                    message=alert.message,
                    current_price=alert.current_price,
                    price_change_1h=alert.price_change_1h,
                    price_change_24h=alert.price_change_24h,
                    volume_spike=alert.volume_spike,
                    sentiment_score=alert.sentiment_score,
                    confidence=alert.confidence,
                    action=alert.action,
                    expires_at=alert.expires_at
                ))
            
            return alert_responses
        
        @self.app.get("/alerts/history")
        async def get_alert_history(limit: int = 100):
            """Get historical alerts"""
            if not self.detector:
                raise HTTPException(status_code=503, detail="Detector not initialized")
            
            history = self.detector.get_alert_history(limit)
            
            return {
                "count": len(history),
                "alerts": [
                    {
                        "id": alert.id,
                        "timestamp": alert.timestamp,
                        "symbol": alert.symbol,
                        "alert_type": alert.alert_type.value,
                        "severity": alert.severity.value,
                        "title": alert.title,
                        "action": alert.action,
                        "confidence": alert.confidence,
                        "acknowledged": alert.acknowledged,
                        "resolved": alert.resolved
                    }
                    for alert in history
                ]
            }
        
        @self.app.get("/alerts/{alert_id}")
        async def get_alert_details(alert_id: str):
            """Get detailed information about a specific alert"""
            if not self.detector:
                raise HTTPException(status_code=503, detail="Detector not initialized")
            
            # Try to get from active alerts first
            alert = self.detector.active_alerts.get(alert_id)
            
            if not alert:
                # Try Redis cache
                try:
                    alert_data = self.redis_client.get(f"alert:{alert_id}")
                    if alert_data:
                        alert_dict = json.loads(alert_data)
                        return alert_dict
                except Exception as e:
                    self.logger.error(f"Error fetching alert from Redis: {e}")
                
                raise HTTPException(status_code=404, detail="Alert not found")
            
            return {
                "id": alert.id,
                "timestamp": alert.timestamp,
                "symbol": alert.symbol,
                "alert_type": alert.alert_type.value,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "current_price": alert.current_price,
                "price_change_1h": alert.price_change_1h,
                "price_change_24h": alert.price_change_24h,
                "volume_24h": alert.volume_24h,
                "volume_spike": alert.volume_spike,
                "sentiment_score": alert.sentiment_score,
                "sentiment_change": alert.sentiment_change,
                "social_volume": alert.social_volume,
                "momentum_score": alert.momentum_score,
                "volatility": alert.volatility,
                "liquidity_score": alert.liquidity_score,
                "confidence": alert.confidence,
                "sources": alert.sources,
                "exchanges": alert.exchanges,
                "triggers": alert.triggers,
                "action": alert.action,
                "target_price": alert.target_price,
                "stop_loss": alert.stop_loss,
                "time_horizon": alert.time_horizon,
                "related_symbols": alert.related_symbols,
                "expires_at": alert.expires_at,
                "acknowledged": alert.acknowledged,
                "resolved": alert.resolved
            }
        
        @self.app.post("/alerts/{alert_id}/acknowledge")
        async def acknowledge_alert(alert_id: str):
            """Acknowledge an alert"""
            if not self.detector:
                raise HTTPException(status_code=503, detail="Detector not initialized")
            
            await self.detector.acknowledge_alert(alert_id)
            
            # Notify WebSocket clients
            await self._broadcast_alert_update(alert_id, "acknowledged")
            
            return {"status": "acknowledged", "alert_id": alert_id}
        
        @self.app.post("/alerts/{alert_id}/resolve")
        async def resolve_alert(alert_id: str):
            """Resolve an alert"""
            if not self.detector:
                raise HTTPException(status_code=503, detail="Detector not initialized")
            
            await self.detector.resolve_alert(alert_id)
            
            # Notify WebSocket clients
            await self._broadcast_alert_update(alert_id, "resolved")
            
            return {"status": "resolved", "alert_id": alert_id}
        
        @self.app.get("/market", response_model=MarketOverview)
        async def get_market_overview():
            """Get overall market overview"""
            try:
                # Get from detector's market state
                market_state = {}
                if self.detector:
                    market_state = self.detector.market_state
                
                # Get Fear & Greed Index
                fear_greed = await self._get_fear_greed_index()
                
                return MarketOverview(
                    fear_greed_index=fear_greed,
                    btc_dominance=market_state.get('btc_dominance', 52.0),
                    overall_sentiment=market_state.get('overall_sentiment', 0.5),
                    active_session=market_state.get('active_session', 'US'),
                    total_market_cap=market_state.get('total_market_cap'),
                    market_trend=self._determine_market_trend(market_state)
                )
                
            except Exception as e:
                self.logger.error(f"Error getting market overview: {e}")
                raise HTTPException(status_code=500, detail="Error fetching market data")
        
        @self.app.get("/symbols", response_model=List[SymbolPrice])
        async def get_symbol_prices(symbols: Optional[str] = None):
            """Get current prices for tracked symbols"""
            if not self.detector:
                raise HTTPException(status_code=503, detail="Detector not initialized")
            
            # Use provided symbols or default tracked symbols
            if symbols:
                symbol_list = [s.strip().upper() for s in symbols.split(',')]
            else:
                symbol_list = self.detector.tracked_symbols
            
            symbol_prices = []
            
            for symbol in symbol_list:
                try:
                    # Get price data from Redis cache
                    price_data = self.redis_client.get(f"price:{symbol}")
                    if price_data:
                        data = json.loads(price_data)
                        symbol_prices.append(SymbolPrice(
                            symbol=symbol,
                            price=data['price'],
                            change_1h=data.get('change_1h', 0),
                            change_24h=data.get('change_24h', 0),
                            volume_24h=data.get('volume_24h', 0)
                        ))
                except Exception as e:
                    self.logger.error(f"Error getting price for {symbol}: {e}")
            
            return symbol_prices
        
        @self.app.get("/symbols/{symbol}")
        async def get_symbol_details(symbol: str):
            """Get detailed information for a specific symbol"""
            symbol = symbol.upper()
            
            try:
                # Get current price data
                price_data = self.redis_client.get(f"price:{symbol}")
                if not price_data:
                    raise HTTPException(status_code=404, detail="Symbol not found")
                
                data = json.loads(price_data)
                
                # Get recent alerts for this symbol
                recent_alerts = []
                if self.detector:
                    all_alerts = self.detector.get_alert_history(50)
                    recent_alerts = [
                        {
                            "id": alert.id,
                            "timestamp": alert.timestamp,
                            "alert_type": alert.alert_type.value,
                            "severity": alert.severity.value,
                            "title": alert.title,
                            "confidence": alert.confidence
                        }
                        for alert in all_alerts
                        if alert.symbol == symbol
                    ][:10]  # Last 10 alerts
                
                return {
                    "symbol": symbol,
                    "current_price": data['price'],
                    "change_1h": data.get('change_1h', 0),
                    "change_24h": data.get('change_24h', 0),
                    "volume_24h": data.get('volume_24h', 0),
                    "last_updated": data.get('timestamp'),
                    "recent_alerts": recent_alerts,
                    "momentum": await self._calculate_symbol_momentum(symbol),
                    "volatility": await self._calculate_symbol_volatility(symbol)
                }
                
            except Exception as e:
                self.logger.error(f"Error getting details for {symbol}: {e}")
                raise HTTPException(status_code=500, detail="Error fetching symbol data")
        
        @self.app.get("/settings", response_model=AlertSettings)
        async def get_alert_settings():
            """Get current alert settings"""
            try:
                # Get settings from Redis or use defaults
                settings_data = self.redis_client.get("moonwalking:settings")
                if settings_data:
                    settings_dict = json.loads(settings_data)
                    return AlertSettings(**settings_dict)
                else:
                    return AlertSettings()  # Default settings
            except Exception as e:
                self.logger.error(f"Error getting settings: {e}")
                return AlertSettings()
        
        @self.app.post("/settings", response_model=AlertSettings)
        async def update_alert_settings(settings: AlertSettings):
            """Update alert settings"""
            try:
                # Save settings to Redis
                settings_dict = settings.dict()
                self.redis_client.setex(
                    "moonwalking:settings",
                    86400 * 7,  # 7 days
                    json.dumps(settings_dict)
                )
                
                # Update detector thresholds if available
                if self.detector:
                    self.detector.thresholds.update({
                        'moonshot_pump': settings.moonshot_threshold,
                        'crater_dump': settings.crater_threshold,
                        'volume_spike': settings.volume_spike_threshold,
                        'sentiment_spike': settings.sentiment_spike_threshold,
                        'fomo_threshold': settings.fomo_threshold
                    })
                
                return settings
                
            except Exception as e:
                self.logger.error(f"Error updating settings: {e}")
                raise HTTPException(status_code=500, detail="Error updating settings")
        
        @self.app.get("/stats")
        async def get_system_stats():
            """Get system statistics"""
            if not self.detector:
                raise HTTPException(status_code=503, detail="Detector not initialized")
            
            active_alerts = self.detector.get_active_alerts()
            alert_history = self.detector.get_alert_history(100)
            
            # Count alerts by type and severity
            type_counts = {}
            severity_counts = {}
            
            for alert in active_alerts:
                alert_type = alert.alert_type.value
                severity = alert.severity.value
                
                type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Calculate average confidence
            avg_confidence = 0
            if active_alerts:
                avg_confidence = sum(alert.confidence for alert in active_alerts) / len(active_alerts)
            
            return {
                "system_status": "active",
                "active_alerts_count": len(active_alerts),
                "total_alerts_today": len([a for a in alert_history if a.timestamp.date() == datetime.now().date()]),
                "tracked_symbols": len(self.detector.tracked_symbols),
                "websocket_connections": len(self.websocket_connections),
                "average_confidence": round(avg_confidence, 3),
                "alerts_by_type": type_counts,
                "alerts_by_severity": severity_counts,
                "uptime": "active",  # Could track actual uptime
                "last_alert": max([a.timestamp for a in active_alerts]) if active_alerts else None
            }
        
        @self.app.websocket("/ws/alerts")
        async def websocket_alerts(websocket: WebSocket):
            """WebSocket endpoint for real-time alerts"""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            try:
                self.logger.info(f"New WebSocket connection. Total: {len(self.websocket_connections)}")
                
                # Send initial data
                await websocket.send_json({
                    "type": "connection",
                    "message": "Connected to Moonwalking alerts",
                    "timestamp": datetime.now().isoformat()
                })
                
                # Keep connection alive and handle messages
                while True:
                    try:
                        # Wait for client messages (ping, etc.)
                        message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                        
                        # Handle client messages
                        try:
                            data = json.loads(message)
                            await self._handle_websocket_message(websocket, data)
                        except json.JSONDecodeError:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Invalid JSON format"
                            })
                            
                    except asyncio.TimeoutError:
                        # Send ping to keep connection alive
                        await websocket.send_json({
                            "type": "ping",
                            "timestamp": datetime.now().isoformat()
                        })
                        
            except WebSocketDisconnect:
                self.logger.info("WebSocket disconnected")
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
            finally:
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
                self.logger.info(f"WebSocket removed. Total: {len(self.websocket_connections)}")
    
    async def initialize_detector(self):
        """Initialize the Moonwalking detector"""
        try:
            self.logger.info("🌙 Initializing Moonwalking Detector...")
            
            config = {
                'tracked_symbols': ['BTC', 'ETH', 'SOL', 'AVAX', 'MATIC', 'ADA', 'DOT', 'LINK', 'UNI', 'AAVE'],
                'api_endpoints': {
                    'sentiment': 'http://localhost:8000'
                }
            }
            
            self.detector = MoonwalkingDetector(config)
            await self.detector.initialize()
            
            # Start background alert monitoring
            task = asyncio.create_task(self._monitor_new_alerts())
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)
            
            self.logger.info("✅ Moonwalking Detector initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize detector: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        self.logger.info("🧹 Cleaning up Moonwalking API...")
        
        # Close WebSocket connections
        for ws in self.websocket_connections:
            try:
                await ws.close()
            except:
                pass
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        self.logger.info("✅ Cleanup completed")
    
    async def _monitor_new_alerts(self):
        """Monitor for new alerts and broadcast to WebSocket clients"""
        last_alert_count = 0
        
        while True:
            try:
                if self.detector:
                    current_alerts = self.detector.get_active_alerts()
                    current_count = len(current_alerts)
                    
                    # Check if new alerts were added
                    if current_count > last_alert_count:
                        # Get the newest alerts
                        newest_alerts = sorted(current_alerts, key=lambda a: a.timestamp, reverse=True)
                        new_alerts = newest_alerts[:current_count - last_alert_count]
                        
                        # Broadcast new alerts
                        for alert in new_alerts:
                            await self._broadcast_new_alert(alert)
                        
                        last_alert_count = current_count
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error monitoring alerts: {e}")
                await asyncio.sleep(10)
    
    async def _broadcast_new_alert(self, alert: MoonwalkingAlert):
        """Broadcast new alert to all WebSocket clients"""
        if not self.websocket_connections:
            return
        
        alert_data = {
            "type": "new_alert",
            "alert": {
                "id": alert.id,
                "timestamp": alert.timestamp.isoformat(),
                "symbol": alert.symbol,
                "alert_type": alert.alert_type.value,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "confidence": alert.confidence,
                "action": alert.action
            }
        }
        
        # Send to all connected clients
        disconnected = []
        for ws in self.websocket_connections:
            try:
                await ws.send_json(alert_data)
            except:
                disconnected.append(ws)
        
        # Remove disconnected clients
        for ws in disconnected:
            self.websocket_connections.remove(ws)
    
    async def _broadcast_alert_update(self, alert_id: str, action: str):
        """Broadcast alert update to WebSocket clients"""
        if not self.websocket_connections:
            return
        
        update_data = {
            "type": "alert_update",
            "alert_id": alert_id,
            "action": action,
            "timestamp": datetime.now().isoformat()
        }
        
        disconnected = []
        for ws in self.websocket_connections:
            try:
                await ws.send_json(update_data)
            except:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.websocket_connections.remove(ws)
    
    async def _handle_websocket_message(self, websocket: WebSocket, data: Dict):
        """Handle incoming WebSocket messages"""
        message_type = data.get('type')
        
        if message_type == 'ping':
            await websocket.send_json({
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            })
        elif message_type == 'subscribe':
            # Handle subscription to specific symbols or alert types
            await websocket.send_json({
                "type": "subscribed",
                "message": "Subscription updated"
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            })
    
    async def _get_fear_greed_index(self) -> int:
        """Get Fear & Greed Index from API"""
        try:
            # This would call the actual Fear & Greed API
            # For now, return a simulated value
            return 67
        except:
            return 50  # Default neutral value
    
    def _determine_market_trend(self, market_state: Dict) -> str:
        """Determine overall market trend"""
        sentiment = market_state.get('overall_sentiment', 0.5)
        
        if sentiment > 0.7:
            return "bullish"
        elif sentiment < 0.3:
            return "bearish"
        else:
            return "neutral"
    
    async def _calculate_symbol_momentum(self, symbol: str) -> float:
        """Calculate momentum for a symbol"""
        if self.detector:
            return await self.detector._calculate_momentum(symbol)
        return 0.0
    
    async def _calculate_symbol_volatility(self, symbol: str) -> float:
        """Calculate volatility for a symbol"""
        if self.detector:
            return await self.detector._calculate_volatility(symbol)
        return 0.0

# Create the API instance
moonwalking_api = MoonwalkingAPI()
app = moonwalking_api.app

# Run the server
if __name__ == "__main__":
    uvicorn.run(
        "moonwalking_api:app",
        host="0.0.0.0",
        port=int(os.environ.get("MOONWALKING_API_PORT", "5002")),
        reload=True,
        log_level="info"
    )