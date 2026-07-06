# Single-Box Deploy (mini PC, VPS, or Oracle Free VM + Tailscale)

Single-box deployment: the Flask backend serves both the API and the built
frontend on one origin, SQLite lives on the local disk, and Tailscale makes
it reachable from your phone/laptop only — nothing is exposed to the public
internet. Works on any Debian/Ubuntu box with systemd: an Intel N100 mini
PC, a cheap VPS (Hetzner etc.), or an Oracle Cloud Always Free VM. Moving
between boxes later = run this kit on the new box and copy one SQLite file.

```
phone / laptop (Tailscale)
        │ https://<minipc>.<tailnet>.ts.net
        ▼
Tailscale Serve (TLS)  ──►  gunicorn app:app :5003
                              ├─ serves frontend/dist (SERVE_FRONTEND_DIST=1)
                              ├─ /api/* + /data board API
                              ├─ SQLite: WATCHLIST_DB_PATH
                              └─ proxies sentiment :8003 (uvicorn)
```

## Oracle Cloud Always Free quickstart

The free tier includes an ARM VM big enough for this app many times over.
Create the account and VM in the Oracle Cloud console (only you can do
this part), then the generic setup below applies unchanged.

1. Sign up at oracle.com/cloud/free (card required for identity; you stay
   on free resources). Pick a home region with Ampere A1 capacity — if VM
   creation fails with "out of capacity", retry later or script retries;
   it's the tier's best-known annoyance.
2. Create instance: **VM.Standard.A1.Flex** (Ampere ARM), e.g. 2 OCPU /
   12 GB (up to 4 OCPU / 24 GB total is free), image **Ubuntu 24.04
   (aarch64)**, add your SSH key. Boot volume default (up to 200 GB free).
3. Recommended: upgrade the account to **Pay As You Go** after signup.
   Always-free resources still cost $0, but PAYG accounts are exempt from
   Oracle's idle-instance reclamation policy (pure free-tier accounts can
   have quiet VMs stopped after ~7 idle days).
4. Networking: with Tailscale you need **no inbound ports** besides SSH
   (22, already open in the default security list). Tailscale connects
   outbound. Skip Oracle's security-list/NSG dance entirely.
5. Oracle Ubuntu images ship restrictive host-level iptables rules
   (`/etc/iptables/rules.v4`). They block *inbound* extras, which is fine
   here — everything rides Tailscale. If something inbound ever seems
   mysteriously blocked, check iptables before blaming Oracle's cloud
   firewall.
6. ARM note: all Python deps used here (flask, gunicorn, pandas, torch CPU
   wheels, websocket-client) publish aarch64 Linux wheels; `setup.sh`
   works unmodified.

Then continue with the generic steps below (SSH in as the `ubuntu` user).

## One-time setup

### 1. Prerequisites on the box

```bash
sudo apt update && sudo apt install -y python3-venv git nodejs npm curl
# Tailscale: https://tailscale.com/download/linux
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up   # log in with your tailnet account
```

### 2. Get the code and build

```bash
sudo mkdir -p /opt/moonwalking && sudo chown "$USER" /opt/moonwalking
git clone https://github.com/tgpetrie/moonwalking.git /opt/moonwalking
cd /opt/moonwalking
./deploy/homeserver/setup.sh
```

`setup.sh` creates the venv, installs backend requirements, builds the
frontend with a same-origin API base, and writes
`deploy/homeserver/.env` with a generated `SECRET_KEY`.

### 3. Database location + service user

```bash
sudo useradd --system --home /opt/moonwalking --shell /usr/sbin/nologin moonwalking || true
sudo mkdir -p /var/lib/moonwalking
sudo chown moonwalking:moonwalking /var/lib/moonwalking
sudo chown -R moonwalking:moonwalking /opt/moonwalking
```

`WATCHLIST_DB_PATH` in `.env` defaults to
`/var/lib/moonwalking/watchlists.sqlite` — deliberately outside the repo so
updates/re-clones can never delete your accounts.

### 4. Install and start the services

```bash
sudo cp deploy/homeserver/moonwalking-*.service /etc/systemd/system/
# If your paths/user differ from /opt/moonwalking + `moonwalking`, edit them.
sudo systemctl daemon-reload
sudo systemctl enable --now moonwalking-backend moonwalking-sentiment
systemctl status moonwalking-backend --no-pager
```

### 5. Expose over the tailnet (HTTPS)

```bash
sudo tailscale serve --bg http://127.0.0.1:5003
tailscale serve status
```

This gives you `https://<minipc>.<your-tailnet>.ts.net` with a real TLS
certificate, on every device where Tailscale is installed and logged in.
Secure session cookies work because the browser sees HTTPS.

### 6. Verify

- Open the tailnet URL on the mini PC's browser or your laptop: board loads.
- Sign up, add a coin to the watchlist.
- Open the same URL on your phone (Tailscale installed): log in — the same
  watchlist appears. That's cross-device done.

## Routine operations

### Update to latest code

```bash
cd /opt/moonwalking
sudo -u moonwalking git pull
./deploy/homeserver/setup.sh          # reinstall deps + rebuild frontend
sudo systemctl restart moonwalking-backend moonwalking-sentiment
```

### Back up accounts/watchlists

The whole database is one file:

```bash
sqlite3 /var/lib/moonwalking/watchlists.sqlite ".backup /var/lib/moonwalking/backup-$(date +%F).sqlite"
```

Put that line in a weekly cron/systemd timer and copy the backups somewhere
that isn't the mini PC.

### Logs

```bash
journalctl -u moonwalking-backend -f
journalctl -u moonwalking-sentiment -f
```

## Design decisions (why it's set up this way)

- **One gunicorn worker** — the app holds market caches, Coinbase pollers,
  and snapshot writers in process memory. A second worker would double-poll
  Coinbase and serve a different board per request. `--threads 8` provides
  request concurrency instead.
- **SQLite over Postgres** — single user-ish workload, writes serialized in
  `backend/watchlist.py`; one file to back up; zero services to maintain.
- **Tailscale over public exposure** — this app will eventually hold a
  (read-only) Coinbase API connection; a service that is unreachable from
  the public internet is a categorically smaller attack surface than any
  login page. If you later want a public read-only board, add a Cloudflare
  Tunnel that only routes `/data` and `/api/data`.
- **`SERVE_FRONTEND_DIST=1`** — frontend and API on one origin removes CORS
  and cross-site cookie concerns entirely; `SameSite=Lax` just works.
- **`DISABLE_TALISMAN=1`** — Talisman's HTTPS redirect misfires behind a
  TLS-terminating proxy (Tailscale Serve); transport security is provided by
  the tailnet.
