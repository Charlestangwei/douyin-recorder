import os, json, base64, urllib.request

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "")
API = "https://api.github.com/repos/" + GH_REPO
HEADERS = {"Authorization": "Bearer " + GH_TOKEN, "Accept": "application/vnd.github+json"}

# Fetch manifest.json from GitHub
existing = {}
existing_sha = None
try:
    req = urllib.request.Request(API + "/contents/docs/manifest.json", headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15).read()
    data = json.loads(resp)
    existing = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    existing_sha = data["sha"]
except Exception as e:
    print("Could not load existing manifest: " + str(e))

# List artifacts and match mkv-room-* names
try:
    req = urllib.request.Request(API + "/actions/artifacts?per_page=50", headers=HEADERS)
    arts = json.loads(urllib.request.urlopen(req, timeout=15).read())["artifacts"]
    for a in arts:
        aname = a["name"]
        if aname.startswith("mkv-room-"):
            room_key = aname[9:]
            if room_key in existing:
                existing[room_key]["artifact_id"] = a["id"]
                existing[room_key]["expires"] = a["expires_at"][:10]
                print("Matched " + room_key[:30] + " -> id=" + str(a["id"]))
except Exception as e:
    print("Artifact matching error: " + str(e))
    pass

if existing_sha:
    merged = json.dumps(existing, indent=2, ensure_ascii=False)
    body = json.dumps({
        "message": "update manifest with artifact IDs",
        "content": base64.b64encode(merged.encode()).decode(),
        "sha": existing_sha,
        "branch": "main"
    }).encode()
    req = urllib.request.Request(API + "/contents/docs/manifest.json", data=body,
        headers={**HEADERS, "Content-Type": "application/json"}, method="PUT")
    urllib.request.urlopen(req, timeout=15)
    print("Manifest pushed!")
else:
    print("No existing manifest to update")
