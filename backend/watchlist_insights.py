class Memory:
    """Simple in-memory log storage with search capability."""
    def __init__(self, logs=None):
        self.logs = logs or []

    def add(self, entry: str) -> None:
        self.logs.append(entry)

    def search(self, term: str):
        """Return all log entries containing the given term."""
        return [log for log in self.logs if term in log]


def smart_watchlist_insights(memory: Memory) -> str:
    import re

    added = memory.search("User added")
    updates = memory.search("is now at")

    tracked = {}
    for entry in added:
        match = re.search(r"User added (\w+) to their watchlist at \$([\d.]+)", entry)
        if match:
            symbol, price = match.group(1), float(match.group(2))
            tracked[symbol] = {"addedAtPrice": price, "updates": []}

    for entry in updates:
        match = re.search(r"(\w+) is now at \$([\d.]+) \(([+-]?\d+\.\d+)%\)", entry)
        if not match:
            continue
        symbol, price, delta = match.group(1), float(match.group(2)), float(match.group(3))
        if symbol not in tracked:
            continue
        tracked[symbol]["updates"].append({"price": price, "delta": delta})

    risk_alerts = []
    suggestions = []

    for symbol, data in tracked.items():
        if not data["updates"]:
            continue
        recent = data["updates"][-1]
        net_change = ((recent["price"] - data["addedAtPrice"]) / data["addedAtPrice"]) * 100

        if net_change <= -5:
            risk_alerts.append(f"⚠️ {symbol} has dropped {net_change:.2f}% since added.")
        elif net_change >= 10:
            risk_alerts.append(f"📈 {symbol} has surged {net_change:.2f}% — consider securing gains.")

        flat = all(abs(u["delta"]) < 0.2 for u in data["updates"][-3:])
        if flat:
            risk_alerts.append(f"😐 {symbol} has shown minimal change in recent updates — might be stagnating.")

    high_cap = [s for s in tracked.keys() if re.match(r"^[A-Z]{2,4}$", s)]
    if len(high_cap) >= 3:
        suggestions.append(
            f"🤖 You’re tracking mostly large-cap tokens ({', '.join(high_cap)}). "
            "Want to explore low-cap movers like WIF, PEPE, or FIS?"
        )

    output = risk_alerts + suggestions
    return "\n".join(output) if output else "✅ No current alerts or suggestions."
