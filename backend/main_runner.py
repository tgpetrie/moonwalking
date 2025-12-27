#!/usr/bin/env python3
"""
Main Application Runner for Crypto Sentiment Pipeline
Entry point for running the complete sentiment collection system
"""

import asyncio
import argparse
import logging
import signal
import sys
import json
from datetime import datetime
from pathlib import Path
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import schedule
import time
from threading import Thread

# Import our modules
from sentiment_orchestrator import SentimentOrchestrator
from utils.rate_limiter import RateLimiter, CacheManager

# Setup logging
def setup_logging(log_level: str = "INFO"):
    """Setup application logging"""
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler('logs/crypto_sentiment.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

class SentimentApplication:
    """Main application class"""
    
    def __init__(self, config_path: str = "config/sentiment_config.yaml"):
        self.config_path = config_path
        self.orchestrator = None
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        
        # Setup FastAPI for web interface
        self.app = FastAPI(
            title="Crypto Sentiment API",
            description="Real-time cryptocurrency sentiment analysis from multiple sources",
            version="1.0.0"
        )
        self._setup_api_routes()
        
        # Latest results storage
        self.latest_results = {}
        self.results_history = []
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.is_running = False
    
    def _setup_api_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/")
        async def root():
            return {
                "message": "Crypto Sentiment Analysis API",
                "status": "running" if self.is_running else "stopped",
                "version": "1.0.0",
                "endpoints": ["/sentiment/latest", "/sentiment/history", "/stats", "/health"]
            }
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            if not self.orchestrator:
                raise HTTPException(status_code=503, detail="Orchestrator not initialized")
            
            return {
                "status": "healthy" if self.is_running else "stopped",
                "timestamp": datetime.now(),
                "orchestrator_status": "running" if self.orchestrator else "not_initialized"
            }
        
        @self.app.get("/sentiment/latest")
        async def get_latest_sentiment():
            """Get the latest sentiment analysis results"""
            if not self.latest_results:
                raise HTTPException(status_code=404, detail="No sentiment data available yet")
            
            return self.latest_results
        
        @self.app.get("/sentiment/history")
        async def get_sentiment_history(limit: int = 10):
            """Get historical sentiment data"""
            limited_history = self.results_history[-limit:] if limit > 0 else self.results_history
            return {
                "count": len(limited_history),
                "history": limited_history
            }
        
        @self.app.get("/stats")
        async def get_system_stats():
            """Get system statistics"""
            if not self.orchestrator:
                raise HTTPException(status_code=503, detail="Orchestrator not initialized")
            
            # Get stats from various components
            rss_stats = self.orchestrator.rss_handler.get_feed_stats()
            reddit_stats = self.orchestrator.reddit_handler.get_reddit_stats()
            cache_stats = self.orchestrator.cache.get_cache_stats()
            rate_limit_stats = self.orchestrator.rate_limiter.get_rate_limit_status()
            
            return {
                "rss_feeds": rss_stats,
                "reddit": reddit_stats,
                "cache": cache_stats,
                "rate_limits": rate_limit_stats,
                "results_history_count": len(self.results_history)
            }
        
        @self.app.post("/sentiment/manual-run")
        async def trigger_manual_run():
            """Manually trigger a sentiment collection run"""
            if not self.orchestrator:
                raise HTTPException(status_code=503, detail="Orchestrator not initialized")
            
            try:
                self.logger.info("Manual sentiment collection triggered via API")
                results = await self.orchestrator.run_collection_cycle()
                
                if results:
                    self._store_results(results)
                    return {"status": "success", "results": results}
                else:
                    raise HTTPException(status_code=500, detail="Collection failed")
                    
            except Exception as e:
                self.logger.error(f"Manual run failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/sentiment/config")
        async def get_configuration():
            """Get current configuration (sanitized)"""
            if not self.orchestrator:
                raise HTTPException(status_code=503, detail="Orchestrator not initialized")
            
            # Return sanitized config (remove API keys)
            sanitized_config = self._sanitize_config(self.orchestrator.config)
            return sanitized_config
    
    def _sanitize_config(self, config: dict) -> dict:
        """Remove sensitive information from config"""
        sanitized = config.copy()
        
        # Remove API keys and sensitive data
        sensitive_keys = ['api_key', 'token', 'password', 'secret', 'auth']
        
        def remove_sensitive(obj):
            if isinstance(obj, dict):
                return {k: remove_sensitive(v) for k, v in obj.items() 
                       if not any(sensitive in k.lower() for sensitive in sensitive_keys)}
            elif isinstance(obj, list):
                return [remove_sensitive(item) for item in obj]
            else:
                return obj
        
        return remove_sensitive(sanitized)
    
    def _store_results(self, results: dict):
        """Store results in memory"""
        # Update latest results
        self.latest_results = results
        
        # Add to history
        self.results_history.append({
            "timestamp": results.get("timestamp", datetime.now()),
            "overall_sentiment": results.get("overall_metrics", {}).get("weighted_sentiment", 0.5),
            "confidence": results.get("overall_metrics", {}).get("confidence", 0.0),
            "data_points": results.get("total_data_points", 0),
            "divergences_count": len(results.get("divergences", []))
        })
        
        # Keep only last 100 results in memory
        if len(self.results_history) > 100:
            self.results_history = self.results_history[-100:]
    
    async def initialize(self):
        """Initialize the application"""
        try:
            self.logger.info("Initializing Crypto Sentiment Application...")
            
            # Initialize orchestrator
            self.orchestrator = SentimentOrchestrator(self.config_path)
            
            self.logger.info("Application initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize application: {e}")
            return False
    
    async def run_single_collection(self):
        """Run a single sentiment collection cycle"""
        if not self.orchestrator:
            self.logger.error("Orchestrator not initialized")
            return None
        
        try:
            results = await self.orchestrator.run_collection_cycle()
            
            if results:
                self._store_results(results)
                self.logger.info(f"Collection completed successfully: "
                               f"{results['total_data_points']} data points, "
                               f"sentiment: {results['overall_metrics']['weighted_sentiment']:.3f}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Collection cycle failed: {e}")
            return None
    
    async def run_continuous_collection(self, interval_minutes: int = 30):
        """Run continuous sentiment collection"""
        if not self.orchestrator:
            self.logger.error("Orchestrator not initialized")
            return
        
        self.is_running = True
        self.logger.info(f"Starting continuous collection every {interval_minutes} minutes")
        
        try:
            await self.orchestrator.start_continuous_collection(interval_minutes)
        except Exception as e:
            self.logger.error(f"Continuous collection failed: {e}")
        finally:
            self.is_running = False
    
    def run_api_server(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the FastAPI server"""
        self.logger.info(f"Starting API server on {host}:{port}")
        
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info",
            access_log=False  # We have our own logging
        )
    
    async def run_scheduled_collection(self, schedule_cron: str = "*/30 * * * *"):
        """Run sentiment collection on a schedule"""
        self.logger.info(f"Setting up scheduled collection: {schedule_cron}")
        
        # Simple scheduler - run every N minutes
        # For production, consider using celery or similar
        interval_minutes = 30  # Parse from cron if needed
        
        while self.is_running:
            try:
                await self.run_single_collection()
                await asyncio.sleep(interval_minutes * 60)
            except Exception as e:
                self.logger.error(f"Scheduled collection error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Crypto Sentiment Analysis Pipeline")
    parser.add_argument("--config", default="config/sentiment_config.yaml",
                       help="Path to configuration file")
    parser.add_argument("--mode", choices=["single", "continuous", "api", "scheduled"],
                       default="continuous", help="Run mode")
    parser.add_argument("--interval", type=int, default=30,
                       help="Collection interval in minutes (for continuous mode)")
    parser.add_argument("--api-host", default="0.0.0.0", help="API server host")
    parser.add_argument("--api-port", type=int, default=8000, help="API server port")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Create application
    app = SentimentApplication(args.config)
    
    # Initialize
    if not await app.initialize():
        logger.error("Failed to initialize application")
        sys.exit(1)
    
    try:
        if args.mode == "single":
            logger.info("Running single collection cycle...")
            results = await app.run_single_collection()
            if results:
                print(json.dumps(results, indent=2, default=str))
            else:
                sys.exit(1)
                
        elif args.mode == "continuous":
            logger.info(f"Running continuous collection every {args.interval} minutes...")
            await app.run_continuous_collection(args.interval)
            
        elif args.mode == "api":
            logger.info("Starting API server...")
            # Run API server in a thread
            import threading
            api_thread = threading.Thread(
                target=app.run_api_server,
                args=(args.api_host, args.api_port),
                daemon=True
            )
            api_thread.start()
            
            # Also run collection in background
            await app.run_continuous_collection(args.interval)
            
        elif args.mode == "scheduled":
            logger.info("Running scheduled collection...")
            await app.run_scheduled_collection()
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        logger.info("Application shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())