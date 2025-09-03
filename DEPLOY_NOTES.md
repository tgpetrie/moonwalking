Deployment notes
================

This project can be deployed to Vercel (frontend static) and Render (backend). A few tips to avoid failed uploads or unexpected behavior:

- Use the repo manifests (package.json, package-lock.json, requirements.txt). Do not rely on local node_modules.
- Add a `.vercelignore` and `.renderignore` to exclude local build artifacts, logs, editor configs and other large files from uploads (added in this branch).
- Keep `frontend/dist/` out of the repository; Vercel will build the frontend from `frontend/package.json` using `@vercel/static-build` and the configured `distDir`.
- If you need environment variables for Vercel, set them in the Vercel project settings (avoid committing `.env` files with secrets).
- For Render, `render.yaml` contains service definitions. Double-check `buildCommand` and `startCommand` to ensure they reference the correct paths (they do here: `backend/requirements.txt`, `cd backend && gunicorn ...`).

Common failure modes
-------------------
- Accidentally uploading `node_modules/` or large `dist/` directories — use the ignore files included in this branch.
- Missing or mismatched build tooling versions in the manifest — pin devDependencies in `frontend/package.json` and commit them so CI and deployers install the correct versions.
- Large log files in the repo — add them to `.gitignore` and `.vercelignore`/`.renderignore`.

If you want, I can also:
- Remove large files from the repo history (git-filter-repo) if you have accidentally committed them.
- Add a simple GitHub Action that validates `dist/` is ignored before merging.
