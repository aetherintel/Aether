# ============================================================================
# workers/emotion_worker/Dockerfile
# Self-contained emotion analysis worker — model weights are baked in.
# Build arg GITHUB_TOKEN is required to download the custom german-emotions
# model from the GitHub Release (models-v1 tag).
# ============================================================================

FROM python:3.11-slim

ARG GITHUB_TOKEN
ARG GITHUB_REPOSITORY=aetherintel/aether
ARG MODEL_RELEASE_TAG=models-v1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY workers/emotion_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aether_lib /app/aether_lib
COPY workers/emotion_worker/*.py ./workers/emotion_worker/

RUN touch /app/workers/__init__.py && \
    touch /app/workers/emotion_worker/__init__.py

# Download custom german-emotions model weights from GitHub Release
RUN --mount=type=secret,id=github_token \
    GITHUB_TOKEN=${GITHUB_TOKEN} \
    GITHUB_REPOSITORY=${GITHUB_REPOSITORY} \
    MODEL_RELEASE_TAG=${MODEL_RELEASE_TAG} \
    python - <<'EOF'
import os, sys, tarfile, urllib.request, json

repo = os.environ["GITHUB_REPOSITORY"]
tag = os.environ["MODEL_RELEASE_TAG"]
token = os.environ.get("GITHUB_TOKEN", "")
asset_name = "german-emotions.tar.gz"
output_dir = "/app/models/emotion/german-emotions"

if not token:
    print("ERROR: GITHUB_TOKEN is required to download model weights")
    sys.exit(1)

url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
req = urllib.request.Request(url, headers={
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json",
})
with urllib.request.urlopen(req) as resp:
    release = json.loads(resp.read())

asset_url = next(
    (a["url"] for a in release.get("assets", []) if a["name"] == asset_name),
    None
)
if not asset_url:
    print(f"ERROR: Asset '{asset_name}' not found in release '{tag}'")
    sys.exit(1)

print(f"Downloading {asset_name} ...")
dl_req = urllib.request.Request(asset_url, headers={
    "Authorization": f"token {token}",
    "Accept": "application/octet-stream",
})
tarball = f"/tmp/{asset_name}"
with urllib.request.urlopen(dl_req) as resp, open(tarball, "wb") as f:
    f.write(resp.read())

os.makedirs(output_dir, exist_ok=True)
with tarfile.open(tarball, "r:gz") as tar:
    tar.extractall(output_dir)
os.remove(tarball)
print(f"Model saved to {output_dir}")
EOF

ENV PYTHONUNBUFFERED=1 \
    MODELS_PATH=/app/models/emotion \
    PYTHONPATH=/app:/app/workers:/app/aether_lib:/app/shared_libs
