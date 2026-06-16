import os, json, base64, urllib.request

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "")
API = "https://api.github.com/repos/" + GH_REPO
HEADERS = {"Authorization": "Bearer " + GH_TOKEN, "Accept": "application/vnd.github+json"}

with open("/tmp/mkv_work/manifest.json") as f:
    backup_manifest = json.load(f)

# Match artifacts by name pattern
try:
    req = urllib.request.Request(API + "/actions/artifacts?per_page=20", headers=HEADERS)
    arts = json.loads(urllib.request.urlopen(req, timeout=15).read())["artifacts"]
    DATE = list(backup_manifest.values())[0]["date"] if backup_manifest else ""
    for a in arts:
        aname = a["name"]
        if a["name"].startswith("mkv-room-") and a["name"] != "mkv-backup-" + DATE:
            room = a["name"].replace("mkv-room-", "")
            # Try to match by room prefix
            for room_id in backup_manifest:
                if room_id.startswith(room.split("-")[0]):
                    backup_manifest[room_id]["artifact_id"] = a["id"]
                    backup_manifest[room_id]["expires"] = a["expires_at"][:10]
except Exception as e:
    print("Artifact lookup: " + str(e))

existing = {}
existing_sha = None
try:
    req = urllib.request.Request(API + "/contents/docs/manifest.json", headers=HEADERS)
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    existing = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    existing_sha = data["sha"]
except:
    pass

existing.update(backup_manifest)
merged = json.dumps(existing, indent=2, ensure_ascii=False)

body = json.dumps({
    "message": "backup manifest: " + str(list(backup_manifest.keys())),
    "content": base64.b64encode(merged.encode()).decode(),
    "sha": existing_sha,
    "branch": "main"
} if existing_sha else {
    "message": "init manifest.json",
    "content": base64.b64encode(merged.encode()).decode(),
    "branch": "main"
}).encode()

req = urllib.request.Request(API + "/contents/docs/manifest.json", data=body, headers={**HEADERS, "Content-Type": "application/json"}, method="PUT")
urllib.request.urlopen(req, timeout=15)
print("manifest.json updated!")
print("Rooms: " + str(list(backup_manifest.keys())))
if backup_manifest:
    print("Artifact ID: ok")
