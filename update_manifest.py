import os, sys, json, time, urllib.request, base64

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Charlestangwei/douyin-recorder")
API = "https://api.github.com/repos/" + GH_REPO
HEADERS = {"Authorization": "Bearer " + GH_TOKEN, "Content-Type": "application/json"}
LOCAL_MANIFEST = "manifest.json"

def log(m):
    print("[" + time.strftime("%H:%M:%S") + "] " + m, flush=True)

# Step 1: Read local manifest if available (new entries from backup_mkv.py)
local_entries = {}
if os.path.exists(LOCAL_MANIFEST):
    try:
        with open(LOCAL_MANIFEST) as f:
            local_entries = json.load(f)
        log("Loaded " + str(len(local_entries)) + " local entries from " + LOCAL_MANIFEST)
    except Exception as e:
        log("Local manifest read error: " + str(e))
else:
    log("No local manifest.json found (first run or no new entries)")

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

# Step 3: Merge local entries into existing (but don't overwrite artifact_id)
merged_count = 0
for k, v in local_entries.items():
    if k not in existing:
        existing[k] = v
        merged_count += 1
    elif "artifact_id" not in existing[k] and "artifact_id" in v:
        # Only add artifact_id if missing
        existing[k] = {**existing[k], **v}

if merged_count > 0:
    log("Added " + str(merged_count) + " new entries from local manifest")
else:
    log("No new entries to merge")

# Step 4: Find all mkv-room artifacts and match IDs
try:
    url = API + "/actions/artifacts?per_page=100"
    arts = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15).read()).get("artifacts", [])
    log("Found " + str(len(arts)) + " total artifacts")

    matched = 0
    for a in arts:
        if a["name"].startswith("mkv-room-"):
            key = a["name"].replace("mkv-room-", "")
            if key in existing and existing[key].get("artifact_id") is None:
                existing[key]["artifact_id"] = a["id"]
                existing[key]["run_id"] = a["workflow_run"]["id"]
                existing[key]["expires"] = a.get("expires_at", "")
                matched += 1
    if matched > 0:
        log("Matched " + str(matched) + " artifact IDs to manifest entries")
    else:
        log("No new artifact IDs to match")

except Exception as e:
    log("Artifact scan error: " + str(e))

# Step 5: Write updated manifest (local and to GitHub API)
try:
    merged_json = json.dumps(existing, indent=2, ensure_ascii=False)

    # Write local
    with open(LOCAL_MANIFEST, "w") as f:
        f.write(merged_json)
    log("Written to " + LOCAL_MANIFEST)

    # Push to GitHub
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
