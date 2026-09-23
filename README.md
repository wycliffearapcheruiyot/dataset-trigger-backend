# Dataset Trigger Backend

Standalone FastAPI service. Another service asks it "is the dataset on Kaggle?".
- On Kaggle already -> answers `ready`.
- Missing -> pushes `dataset_kernel/fetch_dataset.py` to Kaggle, which downloads
  the repo from Hugging Face and publishes it as the Kaggle dataset. The service
  answers `preparing` until Kaggle reports the dataset ready.

State (preparing / ready / failed) is kept in MongoDB, collection `dataset_state`,
so concurrent triggers start only one Kaggle run and state survives restarts.

## Endpoints (both need header `X-Webhook-Secret: <DATASET_TRIGGER_SECRET>`)
| Call | Result |
|---|---|
| `POST /dataset/ensure[?wait=SECONDS]` | 200 ready / 202 preparing / 502 failed. `wait` max 120. |
| `GET /dataset/status` | Same answers, never starts a run. Poll after a 202. |
| `GET /health` | `{"ok": true}` (no auth) |

## Setup
1. **MongoDB Atlas**: create a database user; under Network Access allow Render
   (0.0.0.0/0 is the simple option). Put the connection string in `MONGODB_URI`.
2. **Render**: push this folder to GitHub, create a Web Service from it (or use
   `render.yaml` as a Blueprint), and fill in the env vars from `.env.example`.
   That's it -- no manual Kaggle UI step is needed. Before every push, the
   service writes your Kaggle key (and `HF_TOKEN`, if set) into a small
   private Kaggle dataset (`DATASET_SECRETS_SLUG`, default
   `dataset-trigger-secrets`) and attaches it to the pushed kernel via
   `dataset_sources`. That survives automated CLI pushes, unlike Kaggle's
   UI-managed "Secrets," which are stripped on every push -- so the kernel
   always has fresh credentials without you touching the Kaggle dashboard.

## Test
    curl -X POST "https://YOUR-SERVICE.onrender.com/dataset/ensure?wait=60" \
         -H "X-Webhook-Secret: $DATASET_TRIGGER_SECRET"
