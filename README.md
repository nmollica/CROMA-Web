# CROMA-Web

Web port of the MATLAB CoralPictureAnalyzer for Steve Palumbi's group.

## Status
Skeleton with per-session multi-user state and a stubbed pipeline
(upload → correct → segment → analyze → export). Export works end-to-end
(produces a placeholder results file) so the full chain is testable now.

## Architecture
- **Dash + dash-extensions**: per-session state via `Serverside` objects held
  in a server-side FileSystem cache, keyed per browser session. No cross-user
  globals — safe for ~10 concurrent users.
- **Trial scope**: nothing persisted server-side; results are downloaded as
  Excel/CSV. Google-account login + Drive saving planned for a later version.
- **Deploy**: Docker + Caddy (auto-HTTPS) on a single GCP VM (e2-standard-2),
  start/stop for cost control.

## Run locally
```bash
pip install -r requirements.txt
python app.py            # http://localhost:8050
# or containerized:
docker compose up --build