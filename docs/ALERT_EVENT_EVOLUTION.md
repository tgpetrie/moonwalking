# Alert Event Evolution

Status: Active contract

Date: 2026-07-14

Moonwalkings keeps raw detector output, but it does not present every detector firing as a separate user event. Raw detections form the `Pulse`; related detections for one asset are grouped into a live `Signal` that evolves as evidence changes.

## Event states

The primary event sequence is:

```text
Building -> Breakout -> Moonwalking -> Reversal Risk
```

- `Building`: participation, volatility, or persistence is emerging without a confirmed directional break.
- `Breakout`: price or structure has broken with at least one supporting detector.
- `Moonwalking`: the event reached the strongest current momentum family.
- `Reversal Risk`: a reversal, fakeout, exhaustion, downside impulse, or opposing direction invalidated clean continuation.

An event may skip states when the first trustworthy observation is already strong. A later explicit recovery/reversal-up detector may begin a new bullish progression.

## Grouping contract

- Group by canonical Coinbase product id.
- Keep detections in the same event while the gap between observations is no more than ten minutes.
- Retain event evidence for twenty minutes after the latest observation.
- Keep one current primary state and at most one visible modifier.
- Preserve the raw contributing alert ids and detector families.
- Add a transition only when the primary state changes or materially strengthens.
- The event id is stable for the lifetime of the grouped event. The published signal id changes with the latest transition so unread and notification systems react to evolution, not every poll.

## Modifiers

- `Flow`: whale, stealth, absorption, or liquidity-shock evidence.
- `Heating`: FOMO, breadth thrust, squeeze break, persistent gain, or bullish trend evidence.
- `Social`: real coin-specific social or sentiment evidence.
- `Derivatives`: funding, open-interest, liquidation, or taker-flow evidence.

## Surfaces

- `pulse`: raw, trustworthy detector output.
- `signals`: grouped live events with state, modifier, confidence, evidence families, and transition history.
- `notify`: the subset of signals that crosses the configured high-conviction or confirmed-risk delivery gate.

The canonical `/api/alerts` response retains `active` and `recent` for compatibility and adds `pulse`, `signals`, and `notify`.

## The Read

Every grouped Signal includes a `the_read` object that compresses the evidence into a conditional, plain-language market interpretation. It contains a label, condition, summary, tone, confirmations, and historical-result status. It never emits buy/sell instructions, never invents an invalidation price, and reports comparable-event history as `collecting` until a measured sample is actually attached.

Examples include `EARLY — WATCH FOR CONFIRMATION`, `CONTINUATION FAVORED`, `MIXED — NO CLEAR EDGE`, `REVERSAL RISK RISING`, and `BREAKDOWN CONFIRMED`.

### Context tags

Signals may show at most two short context tags. They explain an existing event and never create a new alert:

- `BREAKING AWAY`: the coin is moving unusually far beyond the full-market median.
- `MARKET CARRIED`: most of the move is also happening across the wider market.
- `SPOT BUYING` / `SPOT SELLING`: Coinbase's sampled ticker flow shows enough observed dollar activity and a strong aggressive-side imbalance. This is an honest sample, not total exchange volume.
- `WIDE SPREAD` / `THIN AIR`: the live Coinbase bid/ask spread implies elevated execution risk.

Independent movement has first display priority, followed by sampled spot flow and liquidity risk. Ordinary market-following context has the lowest priority. No more than two tags are shown so the event remains glanceable.

### Measured history

Each published signal transition is stored in a durable local SQLite database and followed for 60 minutes. The default outcome asks whether the price moved 2% in the signal direction before moving 1% against it. The app records 5, 15, 30, and 60 minute returns plus maximum favorable and adverse movement.

`The Read` says history is collecting until at least 20 comparable completed events exist. It then displays the measured rate, sample size, target, and adverse boundary. The rule is configurable, versioned in configuration, and exposed through the read-only `/api/signals/outcomes/status` endpoint.

## Confidence

The first active implementation uses an explicitly versioned explanation score, not a probability of profit. It combines:

- current state strength;
- highest detector severity;
- number of independent detector families;
- corroborating modifiers;
- data quality and recency.

The score and its component breakdown are included on every event. Threshold calibration remains part of the v1 shadow-evaluation work.

## Notification behavior

- Notify on a newly eligible event transition, not on every detector poll.
- Browser notification dedupe uses the published signal id.
- Backend delivery dedupe uses the event id plus transition timestamp.
- Default backend cooldown is fifteen minutes per symbol.
- Default global delivery budget is six messages per hour.
- Email, Telegram, and Discord are optional backend channels; browser notifications are an opt-in frontend channel.

Backend delivery is disabled by default. Set `MW_ALERT_NOTIFY_ENABLED=1`, then configure at least one channel:

- Email: `MW_SMTP_HOST`, `MW_SMTP_PORT`, `MW_SMTP_USERNAME`, `MW_SMTP_PASSWORD`, `MW_ALERT_EMAIL_FROM`, and `MW_ALERT_EMAIL_TO`.
- Telegram: `MW_TELEGRAM_BOT_TOKEN` and `MW_TELEGRAM_CHAT_ID`.
- Discord: `MW_DISCORD_WEBHOOK_URL`.

Optional controls are `MW_NOTIFY_MAX_PER_HOUR` (default `6`), `MW_NOTIFY_SYMBOL_COOLDOWN_SECONDS` (default `900`), and `MW_NOTIFY_MAX_EVENT_AGE_SECONDS` (default `120`). The read-only `/api/notifications/status` endpoint reports channel readiness without returning secrets.
