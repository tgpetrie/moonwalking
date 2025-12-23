import os
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

import torch
import google.generativeai as genai
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger(__name__)

MODEL_NAME = "ProsusAI/finbert"
LABELS = {0: "Bearish", 1: "Neutral", 2: "Bullish"}


def detect_device() -> str:
    """Auto-detect best available device: MPS (M3) > CUDA > CPU (N100)."""
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


@dataclass
class IntelligenceEngine:
    """Container for the loaded FinBERT model and tokenizer."""
    tokenizer: any
    model: any
    device: str
    gemini_model: any = None
    gemini_configured: bool = False


def load_engine() -> IntelligenceEngine:
    """
    One-time model load at process start.
    Device-agnostic: works on M3 (MPS) and N100 (CPU).
    """
    device = detect_device()
    logger.info(f"📍 Loading FinBERT on device: {device.upper()}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()
    model.to(device)

    logger.info(f"✅ FinBERT loaded successfully on {device}")

    # Optional Gemini setup
    gemini_model = None
    gemini_configured = False
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        gemini_configured = True
        logger.info("✅ Gemini 1.5 Flash connected for narrative analysis")
    else:
        logger.warning("⚠️ GEMINI_API_KEY not found. Narrative analysis disabled.")

    return IntelligenceEngine(
        tokenizer=tokenizer,
        model=model,
        device=device,
        gemini_model=gemini_model,
        gemini_configured=gemini_configured
    )


def finbert_score(engine: IntelligenceEngine, headlines: List[str]) -> Dict[str, any]:
    """
    Scores a list of headlines using FinBERT.

    Returns:
        {
            "score": float (-1.0 to 1.0, bearish to bullish),
            "label": str ("Bearish" | "Neutral" | "Bullish"),
            "confidence": float (0.0 to 1.0)
        }
    """
    if not headlines:
        return {"score": 0.0, "label": "Neutral", "confidence": 0.0}

    # Combine headlines and clamp length
    text = " ".join(headlines[:8])
    inputs = engine.tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
    inputs = {k: v.to(engine.device) for k, v in inputs.items()}

    with torch.inference_mode():
        logits = engine.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).squeeze(0)

    bearish, neutral, bullish = probs.tolist()
    score = float(bullish - bearish)  # range roughly [-1, 1]
    confidence = float(max(bearish, neutral, bullish))
    label = LABELS[int(torch.argmax(probs).item())]

    return {"score": score, "label": label, "confidence": confidence}


def classify_divergence(finbert_score_val: float, fear_greed: Optional[int]) -> str:
    """
    Deterministic divergence classification.

    Returns:
        "bullish_divergence" | "bearish_divergence" | "none"
    """
    if fear_greed is None:
        return "none"
    if finbert_score_val > 0.4 and fear_greed < 35:
        return "bullish_divergence"
    if finbert_score_val < -0.4 and fear_greed > 65:
        return "bearish_divergence"
    return "none"


# -----------------------------
# Data Source Functions
# Replace these with your real integrations
# -----------------------------

def fetch_price_usd(symbol: str) -> Optional[float]:
    """Fetch current USD price for symbol (Coinbase/CoinGecko)."""
    try:
        import requests
        resp = requests.get(f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot", timeout=3)
        data = resp.json()
        return float(data['data']['amount']) if data.get('data') else None
    except Exception as e:
        logger.warning(f"Failed to fetch price for {symbol}: {e}")
        return None


def fetch_top_headlines(symbol: str) -> List[str]:
    """Fetch top news headlines for symbol (RSS/news aggregator)."""
    # TODO: Integrate with your existing RSS aggregator
    # Placeholder mock data
    return [
        f"{symbol} institutional adoption accelerates as major funds enter",
        f"Regulatory clarity improves for {symbol} trading infrastructure",
        f"{symbol} network activity reaches new highs amid market uncertainty",
    ]


def fetch_social_volume(symbol: str) -> Optional[int]:
    """Fetch social media mention count (Reddit/Twitter)."""
    # TODO: Integrate with your Reddit/Twitter counters
    # Placeholder
    return None


def fetch_fear_greed_index() -> Optional[int]:
    """Fetch Fear & Greed Index from alternative.me."""
    try:
        from sentiment_data_sources import fetch_fear_and_greed_index
        fg_data = fetch_fear_and_greed_index()
        return fg_data['value'] if fg_data else None
    except Exception as e:
        logger.warning(f"Failed to fetch Fear & Greed: {e}")
        return None


def build_report(engine: IntelligenceEngine, symbol: str, ttl_seconds: int = 300) -> Dict[str, any]:
    """
    Builds a complete intelligence report for a symbol.

    This is the heavy lifting function that runs:
    1. Price fetch
    2. Headlines fetch
    3. FinBERT inference
    4. Divergence classification

    Note: Narrative generation is gated (not called here by default).
    """
    symbol = symbol.upper()

    price = fetch_price_usd(symbol)
    headlines = fetch_top_headlines(symbol)
    social = fetch_social_volume(symbol)
    fg = fetch_fear_greed_index()

    fb = finbert_score(engine, headlines)
    divergence = classify_divergence(fb["score"], fg)

    return {
        "symbol": symbol,
        "price": price,
        "metrics": {
            "finbert_score": fb["score"],
            "finbert_label": fb["label"],
            "fear_greed_index": fg,
            "social_volume": social,
            "confidence": fb["confidence"],
            "divergence": divergence,
        },
        "narrative": None,  # Gated LLM call, added on-demand
        "raw_context": {"top_headlines": headlines[:3]},
        "ttl_seconds": ttl_seconds,
        "model": {"name": MODEL_NAME, "device": engine.device, "quantized": False},
    }


# Legacy compatibility: Keep old HybridIntelligence class for existing code
class HybridIntelligence:
    """Legacy wrapper for backward compatibility."""
    def __init__(self):
        engine = load_engine()
        self.device = torch.device(engine.device)
        self.tokenizer = engine.tokenizer
        self.model = engine.model
        self.gemini_model = engine.gemini_model
        self.gemini_configured = engine.gemini_configured

    def score_headlines_local(self, headlines: List[str]) -> Dict:
        engine = IntelligenceEngine(
            tokenizer=self.tokenizer,
            model=self.model,
            device=str(self.device),
            gemini_model=self.gemini_model,
            gemini_configured=self.gemini_configured
        )
        return finbert_score(engine, headlines)

    def generate_narrative(self, symbol: str, headlines: List[str], current_price: float) -> str:
        if not self.gemini_configured or not headlines:
            return "Narrative analysis unavailable (Missing API Key or Data)."

        context_text = "\n".join(headlines[:5])
        prompt = (
            f"You are a crypto analyst. {symbol} is at ${current_price}. "
            f"Analyze these news headlines and write a ONE sentence summary "
            f"explaining the primary driver of market sentiment right now. "
            f"Be specific (e.g., mention 'ETF approval' or 'regulatory fears').\n\n"
            f"Headlines:\n{context_text}"
        )

        try:
            response = self.gemini_model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "Market narrative currently unavailable."


ai_engine = HybridIntelligence()
