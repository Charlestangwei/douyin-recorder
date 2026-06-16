import os, sys, json, time, urllib.request, base64

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Charlestangwei/douyin-recorder")
API = "https://api.github.com/repos/" + GH_REPO
HEADERS = {"Authorization": "Bearer " + GH_TOKEN, "Content-Type": "application/json"}
LOCAL_MANIFEST = "manifest.json"

def log(m):
    print("[" + time.strftime("%H:%M:%S") + "] " + m, flush=True)

# Step 1: Read local manifest if available
local_entries = {}
if os.path.exists(LOCAL_MANIFEST):
    try:
        with open(LOCAL_MANIFEST) as f:
            local_entries = json.load(f)
        log("Loaded " + str(len(local_entries)) + " local entries")
    except Exception as e:
        log("Local manifest read error: " + str(e))

# Step 2: Fetch existing manifest from GitHub
try:
    req = urllib.request.Request(API + "/contents/docs/manifest.json", headers=HEADERS)
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    existing = json.loads(base64.b64decode(resp["content"]).decode("utf-8"))
    existing_sha = resp["sha"]
    log("Fetched " + str(len(existing)) + " entries from GitHub")
except Exception as e:
    log("Failed to fetch existing manifest: " + str(e))
    existing = {}
    existing_sha = None

# Step 3: Merge local entries into existing
merged_count = 0
for k, v in local_entries.items():
    if k not in existing:
        existing[k] = v
        merged_count += 1
    elif "artifact_id" not in existing[k] and "artifact_id" in v:
        existing[k] = {**existing[k], **v}
if merged_count > 0:
    log("Added " + str(merged_count) + " new entries from local manifest")

# Step 4: Find all mkv-room artifacts and match/create
try:
    url = API + "/actions/artifacts?per_page=100"
    arts = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15).read()).get("artifacts", [])
    log("Found " + str(len(arts)) + " total artifacts")

    matched = 0
    created = 0
    for a in arts:
        if not a["name"].startswith("mkv-room-"):
            continue
        key = a["name"].replace("mkv-room-", "")
        
        if key in existing and existing[key].get("artifact_id") is not None:
            continue  # already has an artifact_id
        
        # Determine session info from key
        parts = key.split("_", 1)
        room = parts[0]
        start_ts = parts[1] if len(parts) > 1 else ""
        date_str = start_ts[:8] if start_ts else ""
        
        entry = {
            "room": room,
            "date": date_str,
            "start_ts": start_ts,
            "merged_file": key + "_merged.mkv",
            "segments": 0,
            "backup_date": time.strftime("%Y-%m-%d"),
            "artifact_id": a["id"],
            "run_id": a["workflow_run"]["id"],
            "expires": a.get("expires_at", "")
        }
        
        if key in existing and existing[key].get("artifact_id") is None:
            # Update existing entry with artifact_id
            existing[key].update(entry)
            matched += 1
        elif key not in existing:
            # Create new entry
            existing[key] = entry
            created += 1
    
    if matched > 0:
        log("Matched " + str(matched) + " artifact IDs")
    if created > 0:
        log("Created " + str(created) + " new manifest entries")

except Exception as e:
    log("Artifact scan error: " + str(e))

# Step 5: Write updated manifest
try:
    merged_json = json.dumps(existing, indent=2, ensure_ascii=False)
    with open(LOCAL_MANIFEST, "w") as f:
        f.write(merged_json)
    log("Written to " + LOCAL_MANIFEST)

    if existing_sha:
        payload = json.dumps({
            "message": "update manifest",
            "content": base64.b64encode(merged_json.encode()).decode(),
            "sha": existing_sha,
            "branch": "main"
        }).encode()
        put_req = urllib.request.Request(API + "/contents/docs/manifest.json", data=payload, headers=HEADERS, method="PUT")
        urllib.request.urlopen(put_req, timeout=15)
        log("Pushed to GitHub")

except Exception as e:
    log("Write error: " + str(e))

log("Done!")
