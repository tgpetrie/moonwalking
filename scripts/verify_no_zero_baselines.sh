#!/usr/bin/env bash
set -euo pipefail

is_probably_json() {
  # Read only the first non-whitespace byte and check for JSON starters.
  # Returns 0 if likely JSON, 1 otherwise.
  local url="$1"
  local first
  first="$(
    curl -fsS "$url" \
      | LC_ALL=C tr -d ' \n\r\t' \
      | head -c 1 \
      || true
  )"
  [[ "$first" == "{" || "$first" == "[" ]]
}

try_urls=()
if [[ $# -ge 1 ]]; then
  # If the provided URL isn't JSON, fall back to common endpoints on the same host.
  provided="$1"
  base="$(printf '%s' "$provided" | sed -E 's#(https?://[^/]+).*#\1#')"

  try_urls+=("$provided")
  try_urls+=("$base/api/data" "$base/data" "$base/")
else
  try_urls+=(
    "http://127.0.0.1:5002/api/data"
    "http://127.0.0.1:5002/data"
    "http://127.0.0.1:5002/"
  )
fi

URL=""
for u in "${try_urls[@]}"; do
  if is_probably_json "$u"; then
    URL="$u"
    break
  fi
done

if [[ -z "$URL" ]]; then
  echo "FAIL: none of the candidate URLs returned JSON: ${try_urls[*]}" >&2
  exit 1
fi

echo "Checking baselines from: $URL"

payload="$(curl -fsS "$URL")"

if command -v jq >/dev/null 2>&1; then
  hit="$(
    printf '%s' "$payload" | jq -r '
      def bad(x): (x != null) and (x <= 0);
      .. | objects
      | select(
          bad(.previous_price?) or
          bad(.initial_price_1min?) or
          bad(.initial_price_3min?) or
          bad(.price_1m_ago?) or
          bad(.price_3m_ago?)
        )
      | @json
    ' | head -n 1
  )"
else
  hit="$(python3 - <<'PY'
import json,sys
keys = {"previous_price","initial_price_1min","initial_price_3min","price_1m_ago","price_3m_ago"}

payload = sys.stdin.read()
data = json.loads(payload)

bad_found = None
def walk(x):
    global bad_found
    if bad_found is not None:
        return
    if isinstance(x, dict):
        for k,v in x.items():
            if k in keys and v is not None and isinstance(v,(int,float)) and v <= 0:
                bad_found = x
                return
            walk(v)
    elif isinstance(x, list):
        for it in x:
            walk(it)

walk(data)
if bad_found is not None:
    print(json.dumps(bad_found))
else:
    print("")
PY
<<<"$payload")"
fi

if [[ -n "$hit" ]]; then
  echo "FAIL: Found non-positive baseline payload:" >&2
  echo "$hit" >&2
  exit 1
fi

echo "OK: No non-positive baselines found."
#!/usr/bin/env bash
