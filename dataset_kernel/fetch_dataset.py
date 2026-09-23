"""
fetch_dataset.py  --  runs ON KAGGLE (not on Render).

Downloads a repo from Hugging Face and publishes it as a Kaggle dataset.
dataset_manager.py fills in CONFIG below before pushing this script to Kaggle.

Credentials: dataset_manager.py writes the Kaggle key/token (and optional
HF token) into a small private Kaggle dataset and attaches it to this kernel
via dataset_sources -- that happens automatically on every push, so there is
no manual setup step here. `get_secret` also checks Kaggle's UI-managed
"Secrets" (Add-ons -> Secrets) first, in case you've attached one by hand;
those just don't survive an automated CLI push the way the attached dataset
does.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

CONFIG = __CONFIG__  # injected by dataset_manager.py


def _dataset_secret(name):
    """Read a credential from the private secrets dataset attached to this kernel."""
    slug = CONFIG.get("secrets_dataset", "").split("/")[-1]
    if not slug:
        return None
    path = os.path.join("/kaggle/input", slug, "secrets.json")
    try:
        with open(path) as f:
            return json.load(f).get(name)
    except Exception:
        return None


def get_secret(name):
    try:
        from kaggle_secrets import UserSecretsClient
        val = UserSecretsClient().get_secret(name)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(name) or _dataset_secret(name)


def run(cmd, env=None):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def failed(res):
    """The kaggle CLI sometimes prints an error but still exits 0."""
    if res.returncode != 0:
        return True
    lines = (res.stdout + "\n" + res.stderr).splitlines()
    return any(l.strip().lower().startswith(("error", "dataset creation error", "invalid")) for l in lines)


def main():
    owner, slug = CONFIG["dataset"].split("/", 1)

    token = get_secret("KAGGLE_API_TOKEN")
    key = get_secret("KAGGLE_KEY")
    if not (token or key):
        sys.exit("Attach a KAGGLE_API_TOKEN (or KAGGLE_KEY) secret to this notebook (Add-ons -> Secrets).")
    env = {**os.environ, "KAGGLE_USERNAME": owner}
    if token:
        env["KAGGLE_API_TOKEN"] = token
    if key:
        env["KAGGLE_KEY"] = key
    hf_token = get_secret("HF_TOKEN") or None

    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub"], check=True)
    from huggingface_hub import snapshot_download

    # Download outside /kaggle/working so it isn't also saved as notebook output.
    base = "/kaggle/temp" if os.path.isdir("/kaggle/temp") else None
    workdir = tempfile.mkdtemp(dir=base)
    data_dir = os.path.join(workdir, "data")

    print(f"Downloading {CONFIG['hf_repo']} from Hugging Face ...", flush=True)
    snapshot_download(
        repo_id=CONFIG["hf_repo"],
        revision=CONFIG.get("hf_revision") or None,
        local_dir=data_dir,
        token=hf_token,
    )
    shutil.rmtree(os.path.join(data_dir, ".cache"), ignore_errors=True)  # HF bookkeeping, not data

    files = [os.path.join(r, f) for r, _, fs in os.walk(data_dir) for f in fs]
    if not files:
        sys.exit("Hugging Face download produced no files.")
    print(f"Downloaded {len(files)} files.", flush=True)

    with open(os.path.join(data_dir, "dataset-metadata.json"), "w") as fh:
        json.dump(
            {"title": CONFIG["title"], "id": CONFIG["dataset"], "licenses": [{"name": "other"}]},
            fh,
        )

    print("Creating Kaggle dataset ...", flush=True)
    res = run(["kaggle", "datasets", "create", "-p", data_dir, "--dir-mode", "zip"], env=env)
    print(res.stdout, res.stderr, flush=True)
    if failed(res):
        print("Create failed (dataset may already exist); trying a new version ...", flush=True)
        res = run(
            ["kaggle", "datasets", "version", "-p", data_dir, "-m", "refresh from Hugging Face",
             "--dir-mode", "zip"],
            env=env,
        )
        print(res.stdout, res.stderr, flush=True)
        if failed(res):
            sys.exit("Could not create or version the Kaggle dataset.")

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
