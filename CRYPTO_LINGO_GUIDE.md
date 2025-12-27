# Crypto Terminology Guide - Sentiment UI

## Overview

The sentiment popup now uses authentic crypto terminology to make it more engaging and relatable for the community.

---

## Tier Labels (Before → After)

### Tier 1: Institutional → 🐋 Whales & Institutions
**Subtitle:** "Smart Money: CoinGecko, Fear & Greed, Binance"

**Why:**
- **Whales** = Large holders with significant capital (institutions, VCs, funds)
- **Smart Money** = Informed investors who move markets
- These sources represent the institutional/professional perspective

---

### Tier 2: Mainstream → 📰 Mainstream Normies
**Subtitle:** "News & Big Reddit: CoinDesk, r/CC"

**Why:**
- **Normies** = Regular people who follow mainstream news
- Not degens, not whales - just normal crypto participants
- r/CryptoCurrency = 7M+ mainstream crypto community

---

### Tier 3: Retail → 💎 Diamond Hands & Degens
**Subtitle:** "Apes Strong Together: r/SSB, CT, Telegram"

**Why:**
- **Diamond Hands** = HODLers who never sell regardless of price
- **Degens** = Degen traders who YOLO into risky plays
- **Apes** = Retail investors who buy and hold
- **CT** = Crypto Twitter (the degen version of finance twitter)
- r/SSB = SatoshiStreetBets (degen central)

---

### Tier 4: Fringe → 🌚 Moonboys & Schizos
**Subtitle:** "Anon Intel: /biz/, BitcoinTalk, Weibo"

**Why:**
- **Moonboys** = Ultra-optimistic traders who think everything will moon
- **Schizos** = Paranoid/conspiracy-minded anons (term of endearment in crypto)
- **/biz/** = 4chan's business board (early adopters, contrarian takes)
- **Anon** = Anonymous users who sometimes have alpha

---

## Divergence Alert Messages

### Before:
> "Institutional sources (75%) more bullish than retail (42%)"

### After:
> "🐋 Whales (75%) more bullish than Degens (42%) - Smart money accumulating while apes panic sell?"

---

### Before:
> "Retail sources (78%) more bullish than institutional (45%)"

### After:
> "💎 Diamond Hands (78%) more bullish than Whales (45%) - Retail FOMO while smart money exits? Possible local top."

---

### Before:
> "Mainstream media more bullish than fringe sources"

### After:
> "📰 Normies (65%) more bullish than Anons (42%) - Mainstream catching up or /biz/ already priced in?"

---

### Before:
> "Fringe sources showing more bullish sentiment than mainstream"

### After:
> "🌚 Moonboys (72%) more bullish than Normies (48%) - Early signal or just schizo hopium?"

---

## Status Messages

### Pipeline Running (Before):
> "✓ Live data from sentiment pipeline (127 data points)"

### Pipeline Running (After):
> "📡 LIVE: Scanning 127 sources across all tiers - Data is SAFU"

**Terms:**
- **SAFU** = "Secure Asset Fund for Users" → means "safe" in crypto slang

---

### Pipeline Offline (Before):
> "⚠ Sentiment pipeline offline - showing cached data. Start with: ./start_sentiment_pipeline.sh"

### Pipeline Offline (After):
> "⚠ Pipeline rekt - running on cached hopium. DYOR: ./start_sentiment_pipeline.sh"

**Terms:**
- **Rekt** = Wrecked/destroyed (portfolio destroyed by bad trades)
- **Hopium** = False hope (portmanteau of "hope" + "opium")
- **DYOR** = Do Your Own Research

---

## Section Headers

### Before:
> "Tiered Sentiment Analysis"

### After:
> "Who's Buying? Whale vs Retail Sentiment"

---

### Before:
> "Understanding This Data"

### After:
> "How to Read the Tea Leaves"

---

## Explainer Text

### Before:
> "This analysis aggregates sentiment from 5+ real-time data sources, weighted by reliability tier. Tier 1 sources (institutional data) carry more weight than Tier 3 (retail/social). Click on the Live Sources tab to verify any data point yourself."

### After:
> "This analysis scans 5+ live sources from Whales to Anons. 🐋 Smart money gets more weight than 💎 degen sentiment. When whales buy while apes panic = accumulation zone. When retail FOMOs while whales sell = possible top. Click Live Sources to verify - trust, but verify anon."

**New Terms:**
- **FOMO** = Fear Of Missing Out (buying at tops due to hype)
- **Accumulation zone** = Price range where whales quietly buy
- **Trust, but verify** = Crypto ethos (verify on-chain, not just trust)

---

## Complete Crypto Glossary Used

| Term | Meaning | Usage Context |
|------|---------|---------------|
| **Whales** | Large holders with significant capital | Tier 1 label |
| **Smart Money** | Informed institutional investors | Tier 1 description |
| **Normies** | Mainstream/casual crypto participants | Tier 2 label |
| **Diamond Hands** 💎 | HODLers who never sell | Tier 3 label |
| **Degens** | Degen/reckless traders | Tier 3 label |
| **Apes** | Retail investors who buy and hold | Tier 3 description |
| **CT** | Crypto Twitter | Tier 3 description |
| **Moonboys** 🌚 | Ultra-optimistic bulls | Tier 4 label |
| **Schizos** | Paranoid/conspiracy theorists (affectionate) | Tier 4 label |
| **Anon** | Anonymous users | Tier 4 description |
| **FOMO** | Fear Of Missing Out | Divergence alerts |
| **Rekt** | Wrecked/destroyed | Pipeline offline message |
| **Hopium** | False hope/optimism | Pipeline offline message |
| **SAFU** | Safe (Secure Asset Fund) | Pipeline running message |
| **DYOR** | Do Your Own Research | Explainer text |
| **Accumulation zone** | Price range where whales buy | Explainer text |
| **Local top** | Temporary price peak | Divergence alert |
| **Alpha** | Insider info/edge | Implicit in fringe sources |
| **Priced in** | Already reflected in price | Divergence alert |

---

## Example UI Flow

### Scenario 1: Whales Bullish, Retail Bearish (Contrarian Buy Signal)

```
┌─ Who's Buying? Whale vs Retail Sentiment ──────┐
│                                                 │
│ 🐋 Whales & Institutions         75%          │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░                          │
│ Smart Money: CoinGecko, Fear & Greed, Binance  │
│                                                 │
│ 📰 Mainstream Normies             52%          │
│ ▓▓▓▓▓▓▓▓░░░░░░░░░░░░                          │
│ News & Big Reddit: CoinDesk, r/CC              │
│                                                 │
│ 💎 Diamond Hands & Degens         38%          │
│ ▓▓▓░░░░░░░░░░░░░░░░░                          │
│ Apes Strong Together: r/SSB, CT, Telegram      │
│                                                 │
│ 🌚 Moonboys & Schizos             28%          │
│ ▓▓░░░░░░░░░░░░░░░░░░                          │
│ Anon Intel: /biz/, BitcoinTalk, Weibo          │
│                                                 │
│ 📡 LIVE: Scanning 127 sources - Data is SAFU  │
└─────────────────────────────────────────────────┘

┌─ Divergence Alerts ─────────────────────────────┐
│                                                 │
│ 🚨 Whales (75%) more bullish than Degens (38%) │
│    Smart money accumulating while apes panic   │
│    sell?                                        │
└─────────────────────────────────────────────────┘
```

**Interpretation:** Classic accumulation phase - whales buying while retail capitulates. Historically a good entry zone.

---

### Scenario 2: Retail Euphoric, Whales Cautious (Possible Top)

```
┌─ Who's Buying? Whale vs Retail Sentiment ──────┐
│                                                 │
│ 🐋 Whales & Institutions         42%          │
│ ▓▓▓▓░░░░░░░░░░░░░░░░                          │
│ Smart Money: CoinGecko, Fear & Greed, Binance  │
│                                                 │
│ 📰 Mainstream Normies             68%          │
│ ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░                          │
│ News & Big Reddit: CoinDesk, r/CC              │
│                                                 │
│ 💎 Diamond Hands & Degens         82%          │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░                          │
│ Apes Strong Together: r/SSB, CT, Telegram      │
│                                                 │
│ 🌚 Moonboys & Schizos             91%          │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░                          │
│ Anon Intel: /biz/, BitcoinTalk, Weibo          │
│                                                 │
│ 📡 LIVE: Scanning 127 sources - Data is SAFU  │
└─────────────────────────────────────────────────┘

┌─ Divergence Alerts ─────────────────────────────┐
│                                                 │
│ 🚨 Diamond Hands (82%) more bullish than       │
│    Whales (42%) - Retail FOMO while smart      │
│    money exits? Possible local top.             │
│                                                 │
│ ℹ️  Moonboys (91%) more bullish than Normies   │
│    (68%) - Early signal or just schizo hopium? │
└─────────────────────────────────────────────────┘
```

**Interpretation:** Retail euphoria while institutions exit - classic top signal. Time to consider taking profits.

---

### Scenario 3: Alignment (Confirmation)

```
┌─ Who's Buying? Whale vs Retail Sentiment ──────┐
│                                                 │
│ 🐋 Whales & Institutions         72%          │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░                          │
│                                                 │
│ 📰 Mainstream Normies             68%          │
│ ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░                          │
│                                                 │
│ 💎 Diamond Hands & Degens         71%          │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░                          │
│                                                 │
│ 🌚 Moonboys & Schizos             69%          │
│ ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░                          │
│                                                 │
│ 📡 LIVE: Scanning 127 sources - Data is SAFU  │
└─────────────────────────────────────────────────┘

(No divergence alerts - all tiers aligned)
```

**Interpretation:** All tiers aligned around bullish sentiment - strong confirmation of uptrend.

---

## Why This Matters

### Engagement
- **Relatable language** - Speaks the community's language
- **Fun & memorable** - More likely to share screenshots
- **Educational** - Teaches users to read market structure

### Credibility
- **Authentic** - Shows understanding of crypto culture
- **Not corporate** - Avoids sterile financial jargon
- **Community-first** - Built by degens, for degens

### Actionable
- **Clear signals** - "Whales buying while apes panic" = BUY
- **Risk awareness** - "Retail FOMO" = possible top
- **DYOR culture** - Encourages users to verify

---

## User Reactions (Expected)

### Good Divergence Alert:
**User sees:** "🐋 Whales (75%) more bullish than Degens (38%)"

**User thinks:** "Hmm, smart money accumulating while retail panics? Maybe I should buy this dip instead of panic selling with the apes."

**Action:** Contrarian buy opportunity identified ✅

---

### Top Signal Alert:
**User sees:** "💎 Diamond Hands (82%) more bullish than Whales (42%) - Retail FOMO while smart money exits? Possible local top."

**User thinks:** "Uh oh, everyone's euphoric except whales. They're probably selling to retail. Time to take profits."

**Action:** Risk management triggered ✅

---

### Schizo Hopium Alert:
**User sees:** "🌚 Moonboys (91%) more bullish than Normies (68%) - Early signal or just schizo hopium?"

**User thinks:** "LOL /biz/ is always maximum hopium. But sometimes they're early... I'll keep an eye on this."

**Action:** Early signal awareness ✅

---

## Technical Implementation

All changes are in these files:

1. **[SentimentPopupAdvanced.jsx](frontend/src/components/SentimentPopupAdvanced.jsx)**
   - Tier labels: Lines 728-792
   - Status messages: Lines 797-808
   - Section headers: Lines 720, 860
   - Explainer: Line 863

2. **[useTieredSentiment.js](frontend/src/hooks/useTieredSentiment.js)**
   - Divergence logic: Lines 127-152
   - Alert messages use crypto terminology

---

## Easter Eggs & Hidden Details

- **"Apes Strong Together"** - r/WallStreetBets meme adapted to crypto
- **"Trust, but verify"** - Bitcoin ethos (don't trust, verify)
- **"Data is SAFU"** - Binance CEO CZ's famous typo that became a meme
- **/biz/** - 4chan's business board where early Bitcoin discussions happened
- **CT** - Crypto Twitter (where all the alpha leaks first)

---

**Status:** ✅ Fully implemented and ready to moon 🚀

**Maintainer:** Moonwalking Degens

**WAGMI** 🌙
