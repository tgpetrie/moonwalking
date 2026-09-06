# Railway + Cloudflare production deployment

This is the lowest-complexity production layout for the current Moonwalkings architecture:

```text
Visitor -> Cloudflare DNS/TLS/cache -> Railway always-on container
                                      |- Flask API + built React app
                                      |- sentiment service on localhost
                                      `- persistent SQLite volume
```

Why one public service:

- Login cookies and APIs stay same-origin at `https://bhabit.net`.
- The Coinbase WebSocket, scanners, alerts, and outcome grader remain continuously running.
- There is no browser CORS dependency or Pages-to-backend proxy to fail.
- Cloudflare still owns the domain, public TLS, DDoS protection, and edge caching.

Railway Hobby currently has a $5/month minimum that includes $5 of usage. A small persistent volume is billed by actual storage. Review the live price before enabling billing: <https://docs.railway.com/pricing/plans>.

## Files

- `backend/Dockerfile`: builds the React frontend and compact Python runtime.
- `backend/production_entrypoint.sh`: starts sentiment and Flask in one container.
- `railway.json`: Dockerfile, healthcheck, and always-restart policy.
- `deploy/railway/env.example`: production variables without secrets.

## Railway setup

From the repository root:

```bash
railway login
railway init --name bhabit
railway add --service bhabit
railway volume add --mount-path /var/lib/moonwalking
```

Generate a secret locally and set the production variables in Railway. Do not commit the generated value:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
railway variable set SECRET_KEY=<generated-value> --service bhabit --skip-deploys
railway variable set FLASK_ENV=production SERVE_FRONTEND_DIST=1 SESSION_COOKIE_SECURE=1 DISABLE_TALISMAN=1 CORS_ALLOWED_ORIGINS=https://bhabit.net,https://www.bhabit.net --service bhabit --skip-deploys
railway up --service bhabit
```

After the healthcheck passes:

```bash
railway domain bhabit.net --service bhabit --port 5003
railway domain www.bhabit.net --service bhabit --port 5003
```

Railway returns the required DNS targets. Add those records in Cloudflare or allow Railway's domain flow to add them. The domain must also be attached inside Railway; manually creating only a DNS record is insufficient.

## Cloudflare settings

1. Remove the old Tunnel records for `@` and `www` after Railway is healthy.
2. Add Railway's required CNAME records with Proxy status enabled.
3. Under **SSL/TLS -> Edge Certificates**, confirm Universal SSL is `Active`.
4. Use **Full** encryption mode for the Railway origin.
5. Redirect `www.bhabit.net` to `https://bhabit.net` after both certificates are active.

Do not leave the old local tunnel and Railway DNS records active for the same hostname.

## Persistence

Attach exactly one Railway volume at `/var/lib/moonwalking`. The entrypoint automatically stores these files there:

- `watchlists.sqlite`
- `price_snapshots.sqlite`
- `volume_1h.sqlite`
- `signal_outcomes.sqlite`
- `control_dry_run.sqlite`

`backend/production_entrypoint.sh` derives each database path from
`RAILWAY_VOLUME_MOUNT_PATH` (falling back to `MW_DATA_DIR`). In particular,
`MW_CONTROL_DRY_RUN_DB` defaults to
`$RAILWAY_VOLUME_MOUNT_PATH/control_dry_run.sqlite`. An explicitly configured
database path takes precedence, so any override must remain inside the mounted
volume to survive a deploy or restart.

One replica is intentional because SQLite and the in-memory detector state are single-writer resources.
