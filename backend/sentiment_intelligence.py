import os
import logging
from typing import List, Dict

import torch
import google.generativeai as genai
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger(__name__)


class HybridIntelligence:
    def __init__(self):
        self.device = self._get_device()
        self.tokenizer = None
        self.model = None
        self.gemini_configured = False

        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
            self.gemini_configured = True
            logger.info("✅ Gemini 1.5 Flash connected for narrative analysis")
        else:
            logger.warning("⚠️ GEMINI_API_KEY not found. Narrative analysis will be disabled.")

        # Note: FinBERT/transformers model loading is expensive. Defer loading
        # until first use (lazy) to avoid blocking app startup.

    def _get_device(self):
        if torch.backends.mps.is_available():
            logger.info("🚀 Running AI on Apple Metal (MPS) - Optimized for M3")
            return torch.device("mps")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    def _load_finbert(self):
        try:
            logger.info("Loading local FinBERT model...")
            self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            self.model = AutoModelForSequenceClassification.from_pretrained(
                "ProsusAI/finbert"
            ).to(self.device)
            self.model.eval()
            logger.info("✅ FinBERT loaded successfully on " + str(self.device))
        except Exception as e:
            logger.error(f"❌ Failed to load FinBERT: {e}")

    def ensure_finbert_loaded(self):
        """Load FinBERT on first use. Safe to call multiple times."""
        if self.model is None:
            self._load_finbert()

    def score_headlines_local(self, headlines: List[str]) -> Dict:
        if not headlines:
            return {"score": 0, "label": "Neutral", "confidence": 0}

        # Ensure model is available; this triggers lazy loading if needed.
        try:
            self.ensure_finbert_loaded()
        except Exception:
            # If model fails to load, degrade gracefully.
            return {"score": 0, "label": "Neutral", "confidence": 0}

        inputs = self.tokenizer(
            headlines,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=64,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

        avg_probs = predictions.mean(dim=0).cpu().numpy()
        composite_score = (avg_probs[0] * 1.0) + (avg_probs[1] * -1.0)

        return {
            "score": round(float(composite_score), 3),
            "label": "Bullish" if composite_score > 0.15 else "Bearish"
            if composite_score < -0.15
            else "Neutral",
            "confidence": round(float(max(avg_probs)), 2),
        }

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


_AI_ENGINE = None

def get_ai_engine() -> HybridIntelligence:
    """Return a singleton HybridIntelligence instance, creating it lazily."""
    global _AI_ENGINE
    if _AI_ENGINE is None:
        _AI_ENGINE = HybridIntelligence()
    return _AI_ENGINE
