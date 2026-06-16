import os, json, base64, urllib.request

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "")
API = f"https://api.github.com/repos/{GH_REPO}"
HEADERS = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}

with open("/tmp/mkv_input/manifest.json") as f:
    backup_manifest = json.load(f)

existing = {}
existing_sha = None
try:
    req = urllib.request.Request(API + "/contents/docs/manifest.json", headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    existing = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    existing_sha = data["sha"]
except:
    pass

existing.update(backup_manifest)
merged = json.dumps(existing, indent=2, ensure_ascii=False)
url = API + "/contents/docs/manifest.json"
body = json.dumps({
    "message": f"backup mkv: {list(backup_manifest.keys())}",
    "content": base64.b64encode(merged.encode()).decode(),
    "sha": existing_sha,
    "branch": "main"
} if existing_sha else {
    "message": "init manifest.json",
    "content": base64.b64encode(merged.encode()).decode(),
    "branch": "main"
}).encode()
req = urllib.request.Request(url, data=body, headers={**HEADERS, "Content-Type": "application/json"}, method="PUT")
urllib.request.urlopen(req, timeout=15)
print("manifest.json updated!")
