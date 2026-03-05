"""
Download the custom german-emotions model from a GitHub Release asset.
Expects env var: GITHUB_TOKEN (for private repo access)
Output: ./emotion/german-emotions/
"""
import os
import sys
import tarfile
import urllib.request

REPO = os.getenv("GITHUB_REPOSITORY", "aetherintel/aether")
TAG = os.getenv("MODEL_RELEASE_TAG", "models-v1")
ASSET = "german-emotions.tar.gz"
OUTPUT_DIR = "./emotion/german-emotions"

token = os.getenv("GITHUB_TOKEN")
if not token:
    print("ERROR: GITHUB_TOKEN env var is required")
    sys.exit(1)

url = f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}"
req = urllib.request.Request(url, headers={
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json",
})

print(f"Fetching release info from {url} ...")
with urllib.request.urlopen(req) as resp:
    import json
    release = json.loads(resp.read())

asset_url = None
for asset in release.get("assets", []):
    if asset["name"] == ASSET:
        asset_url = asset["url"]
        break

if not asset_url:
    print(f"ERROR: Asset '{ASSET}' not found in release '{TAG}'")
    print(f"Available assets: {[a['name'] for a in release.get('assets', [])]}")
    sys.exit(1)

print(f"Downloading {ASSET} ...")
dl_req = urllib.request.Request(asset_url, headers={
    "Authorization": f"token {token}",
    "Accept": "application/octet-stream",
})

tarball = f"/tmp/{ASSET}"
with urllib.request.urlopen(dl_req) as resp, open(tarball, "wb") as f:
    f.write(resp.read())

print(f"Extracting to {OUTPUT_DIR} ...")
os.makedirs(OUTPUT_DIR, exist_ok=True)
with tarfile.open(tarball, "r:gz") as tar:
    tar.extractall(OUTPUT_DIR)

os.remove(tarball)
print(f"Done. Model saved to {OUTPUT_DIR}")
