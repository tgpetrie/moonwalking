from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from watchlist_insights import Memory, smart_watchlist_insights
except ImportError:  # graceful fallback if module not present
    Memory = None
    smart_watchlist_insights = None

# Legacy process-local set still used by existing dashboard insights logic.
watchlist_db = set()

watchlist_bp = Blueprint("watchlist_bp", __name__)

INSIGHTS_UNAVAILABLE = "Insights memory unavailable"
_insights_memory = (
    Memory(
        persist_path=os.path.join(os.path.dirname(__file__), "watchlist_insights.log")
    )
    if Memory
    else None
)

_SESSION_USER_KEY = "mw_user_id"
# On hosts with ephemeral filesystems (e.g. Render without a disk), the
# default path is wiped on every deploy — point WATCHLIST_DB_PATH at a
# persistent mount in production.
_WATCHLIST_DB_PATH = Path(
    os.environ.get("WATCHLIST_DB_PATH")
    or Path(__file__).resolve().parent / "data" / "watchlists.sqlite"
)
_DB_LOCK = threading.Lock()


def _utc_now_iso():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalize_email(value):
    return str(value or "").strip().lower()


def _normalize_symbol(value):
    return re.sub(r"[^A-Z0-9.]", "", str(value or "").upper().strip())


def _parse_optional_price(value):
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _slugify_username(value):
    base = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower().strip())
    base = re.sub(r"(^-+|-+$)", "", base)
    return base or "watcher"


def _db_connect():
    _WATCHLIST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_WATCHLIST_DB_PATH, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_watchlist_schema():
    with _DB_LOCK:
        conn = _db_connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    username TEXT NOT NULL UNIQUE,
                    plan TEXT NOT NULL DEFAULT 'Free Account',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS watchlists (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    position INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS watchlist_items (
                    id TEXT PRIMARY KEY,
                    watchlist_id TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    item_type TEXT NOT NULL DEFAULT 'Asset',
                    title TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    added_price REAL,
                    position INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(watchlist_id) REFERENCES watchlists(id) ON DELETE CASCADE,
                    UNIQUE(watchlist_id, item_key)
                );

                CREATE INDEX IF NOT EXISTS idx_watchlists_user_id ON watchlists(user_id);
                CREATE INDEX IF NOT EXISTS idx_watchlist_items_watchlist_id ON watchlist_items(watchlist_id);
                CREATE INDEX IF NOT EXISTS idx_watchlist_items_item_key ON watchlist_items(item_key);
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(watchlist_items)").fetchall()
            }
            if "added_price" not in columns:
                conn.execute("ALTER TABLE watchlist_items ADD COLUMN added_price REAL")
            conn.commit()
        finally:
            conn.close()


def _user_by_id(conn, user_id):
    return conn.execute(
        """
        SELECT id, email, display_name, username, plan, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()


def _user_by_email(conn, email):
    return conn.execute(
        """
        SELECT id, email, password_hash, display_name, username, plan
        FROM users
        WHERE email = ?
        """,
        (email,),
    ).fetchone()


def _serialize_user(row):
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["display_name"],
        "username": row["username"],
        "plan": row["plan"],
    }


def _claim_username(conn, raw_username):
    base = _slugify_username(raw_username)
    candidate = base
    suffix = 2
    while conn.execute(
        "SELECT 1 FROM users WHERE username = ? LIMIT 1", (candidate,)
    ).fetchone():
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def _seed_default_watchlist(conn, user_id):
    existing = conn.execute(
        "SELECT 1 FROM watchlists WHERE user_id = ? LIMIT 1", (user_id,)
    ).fetchone()
    if existing:
        return

    now = _utc_now_iso()
    watchlist_id = f"watchlist-{uuid.uuid4().hex[:10]}"
    conn.execute(
        """
        INSERT INTO watchlists (id, user_id, name, description, notes, position, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            watchlist_id,
            user_id,
            "My Watchlist",
            "Your persistent watchlist synced across devices.",
            "Add symbols, notes, and context here.",
            1,
            now,
            now,
        ),
    )


def _serialize_watchlist(conn, user_id, watchlist_id):
    watchlist = conn.execute(
        """
        SELECT id, user_id, name, description, notes, position, created_at, updated_at
        FROM watchlists
        WHERE id = ? AND user_id = ?
        """,
        (watchlist_id, user_id),
    ).fetchone()
    if not watchlist:
        return None

    items = conn.execute(
        """
        SELECT id, item_key, item_type, title, notes, position, created_at, updated_at
             , added_price
        FROM watchlist_items
        WHERE watchlist_id = ?
        ORDER BY position ASC, created_at ASC
        """,
        (watchlist_id,),
    ).fetchall()

    return {
        "id": watchlist["id"],
        "name": watchlist["name"],
        "description": watchlist["description"],
        "notes": watchlist["notes"],
        "updatedAt": watchlist["updated_at"],
        "items": [
            {
                "id": item["id"],
                "itemKey": item["item_key"],
                "itemType": item["item_type"],
                "title": item["title"],
                "notes": item["notes"],
                "addedPrice": item["added_price"],
                "addedAt": item["created_at"],
                "position": item["position"],
            }
            for item in items
        ],
    }


def _serialize_watchlists(conn, user_id):
    rows = conn.execute(
        """
        SELECT id
        FROM watchlists
        WHERE user_id = ?
        ORDER BY position ASC, created_at ASC
        """,
        (user_id,),
    ).fetchall()
    return [
        _serialize_watchlist(conn, user_id, row["id"])
        for row in rows
        if row and row["id"]
    ]


def _touch_watchlist(conn, watchlist_id):
    conn.execute(
        "UPDATE watchlists SET updated_at = ? WHERE id = ?",
        (_utc_now_iso(), watchlist_id),
    )


def _reindex_watchlist_items(conn, watchlist_id):
    rows = conn.execute(
        """
        SELECT id
        FROM watchlist_items
        WHERE watchlist_id = ?
        ORDER BY position ASC, created_at ASC
        """,
        (watchlist_id,),
    ).fetchall()
    for idx, row in enumerate(rows, start=1):
        conn.execute(
            "UPDATE watchlist_items SET position = ? WHERE id = ?",
            (idx, row["id"]),
        )


def _sync_legacy_symbol_set(conn, symbol):
    exists = conn.execute(
        "SELECT 1 FROM watchlist_items WHERE item_key = ? LIMIT 1", (symbol,)
    ).fetchone()
    if exists:
        watchlist_db.add(symbol)
    else:
        watchlist_db.discard(symbol)


def _session_user_id():
    raw = session.get(_SESSION_USER_KEY)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _auth_payload(conn, user_id):
    user = _user_by_id(conn, user_id)
    if not user:
        return None
    return {
        "authenticated": True,
        "user": _serialize_user(user),
        "watchlists": _serialize_watchlists(conn, user_id),
    }


def _require_auth_user():
    user_id = _session_user_id()
    if not user_id:
        return None, (jsonify({"error": "Authentication required"}), 401)
    return user_id, None


def get_authenticated_user():
    """Return safe metadata for the signed-in user, or None.

    Private member blueprints use this instead of reaching into the watchlist
    database or trusting a user id supplied by the browser.
    """
    user_id = _session_user_id()
    if not user_id:
        return None
    with _DB_LOCK:
        conn = _db_connect()
        try:
            row = _user_by_id(conn, user_id)
            return _serialize_user(row) if row else None
        finally:
            conn.close()


@watchlist_bp.route("/api/auth/session", methods=["GET"])
def auth_session():
    user_id = _session_user_id()
    if not user_id:
        return jsonify({"authenticated": False, "user": None, "watchlists": []})

    with _DB_LOCK:
        conn = _db_connect()
        try:
            if not _user_by_id(conn, user_id):
                session.pop(_SESSION_USER_KEY, None)
                return jsonify({"authenticated": False, "user": None, "watchlists": []})
            _seed_default_watchlist(conn, user_id)
            payload = _auth_payload(conn, user_id)
            if not payload:
                session.pop(_SESSION_USER_KEY, None)
                return jsonify({"authenticated": False, "user": None, "watchlists": []})
            conn.commit()
            return jsonify(payload)
        finally:
            conn.close()


@watchlist_bp.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    data = request.get_json() or {}
    name = str(data.get("name") or "").strip()
    email = _normalize_email(data.get("email"))
    password = str(data.get("password") or "")

    if not name:
        return jsonify({"error": "Name is required"}), 400
    if "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    with _DB_LOCK:
        conn = _db_connect()
        try:
            existing = _user_by_email(conn, email)
            if existing:
                return jsonify({"error": "Email is already registered"}), 409

            now = _utc_now_iso()
            username_seed = name or email.split("@", 1)[0]
            username = _claim_username(conn, username_seed)
            conn.execute(
                """
                INSERT INTO users (email, password_hash, display_name, username, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (email, generate_password_hash(password), name, username, now, now),
            )
            user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            _seed_default_watchlist(conn, user_id)
            conn.commit()
            payload = _auth_payload(conn, user_id)
        finally:
            conn.close()

    session.permanent = True
    session[_SESSION_USER_KEY] = user_id
    return jsonify(payload), 201


@watchlist_bp.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json() or {}
    email = _normalize_email(data.get("email"))
    password = str(data.get("password") or "")

    if "@" not in email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    with _DB_LOCK:
        conn = _db_connect()
        try:
            user = _user_by_email(conn, email)
            if not user or not check_password_hash(user["password_hash"], password):
                return jsonify({"error": "Invalid email or password"}), 401

            user_id = user["id"]
            _seed_default_watchlist(conn, user_id)
            conn.commit()
            payload = _auth_payload(conn, user_id)
        finally:
            conn.close()

    session.permanent = True
    session[_SESSION_USER_KEY] = user_id
    return jsonify(payload), 200


@watchlist_bp.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.pop(_SESSION_USER_KEY, None)
    return jsonify({"ok": True})


@watchlist_bp.route("/api/watchlists", methods=["GET"])
def list_watchlists():
    user_id, error = _require_auth_user()
    if error:
        return error

    with _DB_LOCK:
        conn = _db_connect()
        try:
            if not _user_by_id(conn, user_id):
                session.pop(_SESSION_USER_KEY, None)
                return jsonify({"error": "Session invalid"}), 401
            _seed_default_watchlist(conn, user_id)
            payload = _auth_payload(conn, user_id)
            if not payload:
                session.pop(_SESSION_USER_KEY, None)
                return jsonify({"error": "Session invalid"}), 401
            return jsonify({"watchlists": payload["watchlists"]})
        finally:
            conn.close()


@watchlist_bp.route("/api/watchlists", methods=["POST"])
def create_watchlist():
    user_id, error = _require_auth_user()
    if error:
        return error

    data = request.get_json() or {}
    name = str(data.get("name") or "").strip() or "Untitled Watchlist"
    description = str(data.get("description") or "").strip()
    notes = str(data.get("notes") or "").strip()

    with _DB_LOCK:
        conn = _db_connect()
        try:
            position = (
                conn.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 FROM watchlists WHERE user_id = ?",
                    (user_id,),
                ).fetchone()[0]
                or 1
            )
            now = _utc_now_iso()
            watchlist_id = f"watchlist-{uuid.uuid4().hex[:10]}"
            conn.execute(
                """
                INSERT INTO watchlists (id, user_id, name, description, notes, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    watchlist_id,
                    user_id,
                    name,
                    description,
                    notes,
                    position,
                    now,
                    now,
                ),
            )
            conn.commit()
            watchlist = _serialize_watchlist(conn, user_id, watchlist_id)
            return jsonify({"watchlist": watchlist}), 201
        finally:
            conn.close()


@watchlist_bp.route("/api/watchlists/<string:watchlist_id>", methods=["PATCH"])
def update_watchlist(watchlist_id):
    user_id, error = _require_auth_user()
    if error:
        return error

    data = request.get_json() or {}
    fields = {}
    if "name" in data:
        name = str(data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Watchlist name cannot be empty"}), 400
        fields["name"] = name
    if "description" in data:
        fields["description"] = str(data.get("description") or "").strip()
    if "notes" in data:
        fields["notes"] = str(data.get("notes") or "")

    if not fields:
        return jsonify({"error": "No valid fields to update"}), 400

    with _DB_LOCK:
        conn = _db_connect()
        try:
            exists = conn.execute(
                "SELECT id FROM watchlists WHERE id = ? AND user_id = ?",
                (watchlist_id, user_id),
            ).fetchone()
            if not exists:
                return jsonify({"error": "Watchlist not found"}), 404

            fields["updated_at"] = _utc_now_iso()
            set_clause = ", ".join([f"{key} = ?" for key in fields.keys()])
            values = list(fields.values()) + [watchlist_id]
            conn.execute(
                f"UPDATE watchlists SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            watchlist = _serialize_watchlist(conn, user_id, watchlist_id)
            return jsonify({"watchlist": watchlist})
        finally:
            conn.close()


@watchlist_bp.route("/api/watchlists/<string:watchlist_id>", methods=["DELETE"])
def delete_watchlist(watchlist_id):
    user_id, error = _require_auth_user()
    if error:
        return error

    with _DB_LOCK:
        conn = _db_connect()
        try:
            exists = conn.execute(
                "SELECT id FROM watchlists WHERE id = ? AND user_id = ?",
                (watchlist_id, user_id),
            ).fetchone()
            if not exists:
                return jsonify({"error": "Watchlist not found"}), 404

            symbols = conn.execute(
                "SELECT item_key FROM watchlist_items WHERE watchlist_id = ?",
                (watchlist_id,),
            ).fetchall()
            conn.execute("DELETE FROM watchlists WHERE id = ?", (watchlist_id,))
            remaining = conn.execute(
                "SELECT COUNT(*) FROM watchlists WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            if remaining == 0:
                _seed_default_watchlist(conn, user_id)
            for symbol_row in symbols:
                _sync_legacy_symbol_set(conn, symbol_row["item_key"])
            conn.commit()
            return jsonify(
                {
                    "deletedId": watchlist_id,
                    "watchlists": _serialize_watchlists(conn, user_id),
                }
            )
        finally:
            conn.close()


@watchlist_bp.route("/api/watchlists/<string:watchlist_id>/items", methods=["POST"])
def create_watchlist_item(watchlist_id):
    user_id, error = _require_auth_user()
    if error:
        return error

    data = request.get_json() or {}
    symbol = _normalize_symbol(data.get("itemKey") or data.get("symbol"))
    if not symbol:
        return jsonify({"error": "itemKey (symbol) is required"}), 400

    item_type = str(data.get("itemType") or "Asset").strip() or "Asset"
    title = str(data.get("title") or symbol).strip() or symbol
    notes = str(data.get("notes") or "").strip()
    added_price = _parse_optional_price(data.get("addedPrice") or data.get("price"))

    with _DB_LOCK:
        conn = _db_connect()
        try:
            watchlist = conn.execute(
                "SELECT id FROM watchlists WHERE id = ? AND user_id = ?",
                (watchlist_id, user_id),
            ).fetchone()
            if not watchlist:
                return jsonify({"error": "Watchlist not found"}), 404

            existing = conn.execute(
                """
                SELECT id
                FROM watchlist_items
                WHERE watchlist_id = ? AND item_key = ?
                """,
                (watchlist_id, symbol),
            ).fetchone()
            if existing:
                return jsonify({"error": f"{symbol} already exists in watchlist"}), 409

            position = (
                conn.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 FROM watchlist_items WHERE watchlist_id = ?",
                    (watchlist_id,),
                ).fetchone()[0]
                or 1
            )
            now = _utc_now_iso()
            item_id = f"item-{uuid.uuid4().hex[:10]}"
            conn.execute(
                """
                INSERT INTO watchlist_items (
                    id,
                    watchlist_id,
                    item_key,
                    item_type,
                    title,
                    notes,
                    added_price,
                    position,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    watchlist_id,
                    symbol,
                    item_type,
                    title,
                    notes,
                    added_price,
                    position,
                    now,
                    now,
                ),
            )
            _touch_watchlist(conn, watchlist_id)
            _sync_legacy_symbol_set(conn, symbol)
            conn.commit()
            return (
                jsonify(
                    {"watchlist": _serialize_watchlist(conn, user_id, watchlist_id)}
                ),
                201,
            )
        finally:
            conn.close()


@watchlist_bp.route(
    "/api/watchlists/<string:watchlist_id>/items/<string:item_id>", methods=["PATCH"]
)
def update_watchlist_item(watchlist_id, item_id):
    user_id, error = _require_auth_user()
    if error:
        return error

    data = request.get_json() or {}
    with _DB_LOCK:
        conn = _db_connect()
        try:
            watchlist = conn.execute(
                "SELECT id FROM watchlists WHERE id = ? AND user_id = ?",
                (watchlist_id, user_id),
            ).fetchone()
            if not watchlist:
                return jsonify({"error": "Watchlist not found"}), 404

            item = conn.execute(
                """
                SELECT id, item_key
                FROM watchlist_items
                WHERE id = ? AND watchlist_id = ?
                """,
                (item_id, watchlist_id),
            ).fetchone()
            if not item:
                return jsonify({"error": "Watchlist item not found"}), 404

            updates = {}
            if "notes" in data:
                updates["notes"] = str(data.get("notes") or "")
            if "title" in data:
                updates["title"] = (
                    str(data.get("title") or "").strip() or item["item_key"]
                )
            if "itemType" in data:
                updates["item_type"] = (
                    str(data.get("itemType") or "").strip() or "Asset"
                )
            if "itemKey" in data:
                next_symbol = _normalize_symbol(data.get("itemKey"))
                if not next_symbol:
                    return jsonify({"error": "itemKey cannot be empty"}), 400
                existing = conn.execute(
                    """
                    SELECT id
                    FROM watchlist_items
                    WHERE watchlist_id = ? AND item_key = ? AND id <> ?
                    """,
                    (watchlist_id, next_symbol, item_id),
                ).fetchone()
                if existing:
                    return (
                        jsonify(
                            {"error": f"{next_symbol} already exists in watchlist"}
                        ),
                        409,
                    )
                updates["item_key"] = next_symbol

            if not updates:
                return jsonify({"error": "No valid fields to update"}), 400

            updates["updated_at"] = _utc_now_iso()
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values()) + [item_id, watchlist_id]
            conn.execute(
                f"UPDATE watchlist_items SET {set_clause} WHERE id = ? AND watchlist_id = ?",
                values,
            )
            _touch_watchlist(conn, watchlist_id)
            _sync_legacy_symbol_set(conn, item["item_key"])
            if "item_key" in updates:
                _sync_legacy_symbol_set(conn, updates["item_key"])
            conn.commit()
            return jsonify(
                {"watchlist": _serialize_watchlist(conn, user_id, watchlist_id)}
            )
        finally:
            conn.close()


@watchlist_bp.route(
    "/api/watchlists/<string:watchlist_id>/items/<string:item_id>", methods=["DELETE"]
)
def delete_watchlist_item(watchlist_id, item_id):
    user_id, error = _require_auth_user()
    if error:
        return error

    with _DB_LOCK:
        conn = _db_connect()
        try:
            watchlist = conn.execute(
                "SELECT id FROM watchlists WHERE id = ? AND user_id = ?",
                (watchlist_id, user_id),
            ).fetchone()
            if not watchlist:
                return jsonify({"error": "Watchlist not found"}), 404

            item = conn.execute(
                """
                SELECT id, item_key
                FROM watchlist_items
                WHERE id = ? AND watchlist_id = ?
                """,
                (item_id, watchlist_id),
            ).fetchone()
            if not item:
                return jsonify({"error": "Watchlist item not found"}), 404

            conn.execute(
                "DELETE FROM watchlist_items WHERE id = ? AND watchlist_id = ?",
                (item_id, watchlist_id),
            )
            _reindex_watchlist_items(conn, watchlist_id)
            _touch_watchlist(conn, watchlist_id)
            _sync_legacy_symbol_set(conn, item["item_key"])
            conn.commit()
            return jsonify(
                {"watchlist": _serialize_watchlist(conn, user_id, watchlist_id)}
            )
        finally:
            conn.close()


# Legacy endpoints for existing dashboard/watchlist flows.
@watchlist_bp.route("/api/watchlist", methods=["GET"])
def get_watchlist():
    return jsonify(list(watchlist_db))


@watchlist_bp.route("/api/watchlist", methods=["POST"])
def add_to_watchlist():
    data = request.get_json() or {}
    symbol = _normalize_symbol(data.get("symbol"))
    if not symbol:
        return jsonify({"error": "Symbol is required"}), 400

    watchlist_db.add(symbol)
    if _insights_memory and "price" in data:
        try:
            price_val = float(data["price"])
            _insights_memory.add(
                f"User added {symbol} to their watchlist at ${price_val:.2f}"
            )
        except (ValueError, TypeError):
            pass
    return (
        jsonify(
            {
                "message": f"{symbol} added to watchlist",
                "watchlist": list(watchlist_db),
            }
        ),
        201,
    )


@watchlist_bp.route("/api/watchlist/<string:symbol>", methods=["DELETE"])
def remove_from_watchlist(symbol):
    symbol = _normalize_symbol(symbol)
    if symbol in watchlist_db:
        watchlist_db.remove(symbol)
        return (
            jsonify(
                {
                    "message": f"{symbol} removed from watchlist",
                    "watchlist": list(watchlist_db),
                }
            ),
            200,
        )
    return jsonify({"error": f"{symbol} not in watchlist"}), 404


@watchlist_bp.route("/api/watchlist/insights", methods=["GET"])
def get_watchlist_insights():
    if not smart_watchlist_insights or not _insights_memory:
        return jsonify({"error": INSIGHTS_UNAVAILABLE}), 503
    result = smart_watchlist_insights(_insights_memory)
    return jsonify({"insights": result.split("\n") if result else [], "raw": result})


@watchlist_bp.route("/api/watchlist/insights/log", methods=["POST"])
def add_watchlist_log():
    if not _insights_memory:
        return jsonify({"error": INSIGHTS_UNAVAILABLE}), 503
    data = request.get_json() or {}
    entry = data.get("entry")
    if not entry or not isinstance(entry, str):
        return jsonify({"error": "entry (string) required"}), 400
    entry = entry.strip()[:500]
    _insights_memory.add(entry)
    return jsonify({"message": "log added"}), 201


@watchlist_bp.route("/api/watchlist/insights/price", methods=["POST"])
def add_price_update():
    if not _insights_memory:
        return jsonify({"error": INSIGHTS_UNAVAILABLE}), 503
    data = request.get_json() or {}
    symbol = _normalize_symbol(data.get("symbol"))
    price = data.get("price")
    previous = data.get("previous")
    if not symbol or price is None or previous is None:
        return jsonify({"error": "symbol, price, previous required"}), 400
    try:
        p = float(price)
        prev = float(previous)
        if prev == 0:
            return jsonify({"error": "previous cannot be zero"}), 400
        delta_pct = ((p - prev) / prev) * 100
        _insights_memory.add(f"{symbol} is now at ${p:.2f} ({delta_pct:+.2f}%)")
        return jsonify(
            {"message": "price update logged", "delta_pct": round(delta_pct, 2)}
        )
    except (ValueError, TypeError):
        return jsonify({"error": "invalid numeric values"}), 400


@watchlist_bp.route("/api/watchlist/insights/latest", methods=["POST"])
def latest_alerts_for_symbols():
    if not _insights_memory:
        return jsonify({"error": INSIGHTS_UNAVAILABLE}), 503
    data = request.get_json() or {}
    symbols = data.get("symbols")
    if not symbols or not isinstance(symbols, list):
        return jsonify({"error": "symbols (list) required"}), 400
    result = {}
    for sym in symbols:
        last = _insights_memory.last_for_symbol(str(sym))
        if last:
            result[sym] = last
    return jsonify({"latest": result})


try:
    _ensure_watchlist_schema()
except Exception:
    # Keep app startup resilient even if local filesystem is read-only in a test harness.
    pass
