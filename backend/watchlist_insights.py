import os
import json
import threading
from datetime import datetime


class Memory:
    """Simple log storage with optional file persistence (append-only)."""
    def __init__(self, logs=None, persist_path=None, max_entries=500):
        self.logs = logs or []
        self.persist_path = persist_path
        self.max_entries = max_entries
        self._lock = threading.Lock()
        if self.persist_path:
            self._load()

    def _load(self):
        try:
            if os.path.exists(self.persist_path):
                with open(self.persist_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.logs.append(line)
                self.logs = self.logs[-self.max_entries:]
        except Exception:
            pass

    def _flush(self):
        if not self.persist_path:
            return
        try:
            with open(self.persist_path, 'a') as f:
                f.write(self.logs[-1] + '\n')
        except Exception:
            pass

    def add(self, entry: str) -> None:
        # Use timezone-aware UTC timestamp
        timestamp = datetime.now().astimezone().isoformat()
        record = f"{timestamp} | {entry}"
        with self._lock:
            self.logs.append(record)
            if len(self.logs) > self.max_entries:
                self.logs = self.logs[-self.max_entries:]
            self._flush()

    def search(self, term: str):
        return [log for log in self.logs if term in log]

    def last_for_symbol(self, symbol: str):
        symbol_upper = symbol.upper()
        for line in reversed(self.logs):
            if f" {symbol_upper} " in line or line.endswith(symbol_upper):
                return line
        return None


def _parse_added_entries(added_entries):
    import re
    tracked = {}
    pattern = re.compile(r"User added (\w+) to their watchlist at \$([\d.]+)")
    for entry in added_entries:
        match = pattern.search(entry)
        if match:
            symbol, price = match.group(1), float(match.group(2))
            tracked[symbol] = {"addedAtPrice": price, "updates": []}
    return tracked


def _apply_updates(tracked, update_entries):
    import re
    pattern = re.compile(r"(\w+) is now at \$([\d.]+) \(([+-]?\d+\.\d+)%\)")
    for entry in update_entries:
        match = pattern.search(entry)
        if not match:
            continue
        symbol, price, delta = match.group(1), float(match.group(2)), float(match.group(3))
        if symbol in tracked:
            tracked[symbol]["updates"].append({"price": price, "delta": delta})


def _build_risk_alerts(tracked):
    alerts = []
    for symbol, data in tracked.items():
        updates = data.get("updates")
        if not updates:
            continue
        recent = updates[-1]
        net_change = ((recent["price"] - data["addedAtPrice"]) / data["addedAtPrice"]) * 100
        if net_change <= -5:
            alerts.append(f"⚠️ {symbol} has dropped {net_change:.2f}% since added.")
        elif net_change >= 10:
            alerts.append(f"📈 {symbol} has surged {net_change:.2f}% — consider securing gains.")
        # Flat / stagnation detection
        tail = updates[-3:]
        if tail and all(abs(u["delta"]) < 0.2 for u in tail):
            alerts.append(f"😐 {symbol} has shown minimal change in recent updates — might be stagnating.")
    return alerts


def _build_suggestions(tracked):
    import re
    suggestions = []
    high_cap = [s for s in tracked.keys() if re.match(r"^[A-Z]{2,4}$", s)]
    if len(high_cap) >= 3:
        suggestions.append(
            f"🤖 You’re tracking mostly large-cap tokens ({', '.join(high_cap)}). "
            "Want to explore low-cap movers like WIF, PEPE, or FIS?"
        )
    return suggestions


def smart_watchlist_insights(memory: Memory) -> str:
    added = memory.search("User added")
    updates = memory.search("is now at")
    tracked = _parse_added_entries(added)
    _apply_updates(tracked, updates)
    risk_alerts = _build_risk_alerts(tracked)
    suggestions = _build_suggestions(tracked)
    output = risk_alerts + suggestions
    return "\n".join(output) if output else "✅ No current alerts or suggestions."
