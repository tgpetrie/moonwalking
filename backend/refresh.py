"""
Background Refresh Module for Intelligence Reports
Uses ThreadPoolExecutor for non-blocking FinBERT inference
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from cache import (
    CachePolicy,
    set_cached_report,
    acquire_refresh_lock,
    release_refresh_lock,
    iso_now
)
from sentiment_intelligence import IntelligenceEngine, build_report

logger = logging.getLogger(__name__)


class Refresher:
    """
    Manages background updates for sentiment reports.

    Uses a ThreadPool to run M3/N100 inference without blocking the main API thread.
    Python threads work well here because PyTorch releases the GIL during inference,
    allowing true parallelism on the CPU/MPS.
    """

    def __init__(
        self,
        rds,
        engine: IntelligenceEngine,
        policy: CachePolicy,
        max_workers: int = 4
    ):
        self.rds = rds
        self.engine = engine
        self.policy = policy
        self.pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="intel_refresh"
        )
        logger.info(f"🔄 Refresher initialized with {max_workers} workers on {engine.device}")

    def _compute_and_store(self, symbol: str) -> None:
        """
        The worker task:
        1. Runs the heavy FinBERT inference (MPS/CPU)
        2. Builds the Intelligence Bundle
        3. Updates Redis with 'freshness: fresh'
        4. Releases the lock
        """
        symbol = symbol.upper()
        try:
            # This is the heavy lifting line (M3 or N100)
            logger.debug(f"🔨 Computing report for {symbol}")
            report = build_report(self.engine, symbol, ttl_seconds=self.policy.ttl_seconds)

            # Stamp it
            report["generated_at"] = iso_now()
            report["freshness"] = "fresh"

            # Save to Cache
            set_cached_report(self.rds, symbol, report, self.policy)
            logger.info(f"✅ Refreshed: {symbol} on {self.engine.device}")

        except Exception as e:
            logger.error(f"❌ Failed to refresh {symbol}: {e}")
        finally:
            # Always release lock so we don't block future updates
            release_refresh_lock(self.rds, symbol, self.policy)

    def trigger_refresh(self, symbol: str) -> bool:
        """
        Non-blocking: Checks if a refresh is needed and submits it to the pool.

        Returns:
            True if a task was submitted, False if locked/skipped.
        """
        symbol = symbol.upper()

        # 1. Try to acquire lock (prevents 100 requests for BTC starting 100 threads)
        if not acquire_refresh_lock(self.rds, symbol, self.policy):
            logger.debug(f"⏭️  Refresh already in progress for {symbol}, skipping")
            return False

        # 2. Fire and forget
        self.pool.submit(self._compute_and_store, symbol)
        logger.debug(f"🚀 Triggered refresh for {symbol}")
        return True

    def trigger_refresh_many(self, symbols: Iterable[str]) -> int:
        """
        Batch trigger for the Watchlist.

        Returns:
            Count of refreshes actually triggered (some may be locked).
        """
        count = 0
        for s in symbols:
            if self.trigger_refresh(s):
                count += 1
        if count > 0:
            logger.info(f"🚀 Triggered {count} refreshes")
        return count

    def shutdown(self, wait: bool = True):
        """Gracefully shut down the thread pool."""
        logger.info("🛑 Shutting down Refresher thread pool")
        self.pool.shutdown(wait=wait)
