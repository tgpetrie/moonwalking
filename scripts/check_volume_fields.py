#!/usr/bin/env python3
"""
Check volume banner data structure from backend /data endpoint.
Verifies that volume_1h_now, volume_1h_prev, and volume_change_1h_pct are present.
"""
import requests
import json
import sys

API_URL = "http://127.0.0.1:5003/data"

def check_volume_fields():
    try:
        response = requests.get(API_URL, timeout=5)
        response.raise_for_status()
        data = response.json()

        print("=== Backend /data Response Analysis ===\n")

        # Check for volume banner field
        if "banner_1h_volume" not in data:
            print("❌ MISSING: banner_1h_volume field not found in response")
            print(f"Available top-level keys: {list(data.keys())}")
            return False

        banner = data["banner_1h_volume"]

        if not isinstance(banner, list):
            print(f"❌ INVALID: banner_1h_volume is {type(banner).__name__}, expected list")
            return False

        if len(banner) == 0:
            print("⚠️  WARNING: banner_1h_volume is empty (backend may be warming up)")
            return True

        print(f"✅ Found banner_1h_volume with {len(banner)} items\n")

        # Check first item for required fields
        item = banner[0]
        print("First item sample:")
        print(json.dumps(item, indent=2))
        print()

        # Check required fields
        required_fields = {
            "symbol": "Token identifier",
            "volume_1h_now": "Current 1h volume",
            "volume_1h_prev": "Previous 1h volume (baseline)",
            "volume_change_1h_pct": "Percentage change",
        }

        missing = []
        present = []

        for field, desc in required_fields.items():
            if field in item:
                value = item[field]
                status = "✅" if value is not None else "⚠️ "
                present.append(f"{status} {field}: {value} ({desc})")
            else:
                missing.append(f"❌ {field}: {desc}")

        print("Field verification:")
        for line in present + missing:
            print(f"  {line}")

        if missing:
            print(f"\n❌ FAIL: {len(missing)} required fields missing")
            return False

        print("\n✅ PASS: All required volume fields present")

        # Check if pct is computable when not provided
        can_compute = all(
            item.get(f) is not None
            for f in ["volume_1h_now", "volume_1h_prev"]
        )

        if item.get("volume_change_1h_pct") is None and can_compute:
            print("ℹ️  Note: pct is None but can be computed client-side from now/prev")

        return True

    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Backend not running at {API_URL}")
        print("Start the backend with: cd backend && python app.py")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ ERROR: Request timed out to {API_URL}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success = check_volume_fields()
    sys.exit(0 if success else 1)
