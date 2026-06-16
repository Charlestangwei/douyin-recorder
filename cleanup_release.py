import os, sys, json, time, urllib.request

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Charlestangwei/douyin-recorder")
API = "https://api.github.com/repos/" + GH_REPO
HEADERS = {"Authorization": "Bearer " + GH_TOKEN}
DATE = sys.argv[1]

def log(m):
    print("[" + time.strftime("%H:%M:%S") + "] " + m, flush=True)

# Check if THIS run created artifacts (look for new mkv-room artifacts for this date)
saw_new = False
try:
    url = API + "/actions/artifacts?per_page=50"
    arts = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15).read()).get("artifacts", [])
    for a in arts:
        if a["name"].startswith("mkv-room-") and DATE in a["name"]:
            run_id = a.get("workflow_run", {}).get("id", 0)
            # Only trust artifacts from recent runs (within 3h)
            now = time.time()
            created = a.get("created_at", "")
            if created:
                from datetime import datetime
                ctime = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
                if now - ctime < 10800:  # 3 hours
                    saw_new = True
                    log("Recent artifact verified: " + a["name"])
                    break
    if not saw_new:
        log("No recent mkv-room artifacts found for " + DATE + " - skipping delete")
        log("Done!")
        exit(0)
except Exception as e:
    log("Artifact check error: " + str(e))
    exit(1)

# Find and delete MKV Release assets
log("Scanning " + DATE + " Release assets to delete...")
assets = []
page = 1
while True:
    url = API + "/releases?per_page=100&page=" + str(page)
    try:
        data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30).read())
        if not data: break
        for r in data:
            tag = r["tag_name"]
            if DATE in tag and tag.endswith(".mkv"):
                for a in r.get("assets", []):
                    assets.append({"asset_id": a["id"], "name": a["name"]})
        page += 1
    except:
        break

log("Found " + str(len(assets)) + " MKV assets to delete")
ok = 0
for a in assets:
    try:
        dreq = urllib.request.Request(API + "/releases/assets/" + str(a["asset_id"]), headers=HEADERS, method="DELETE")
        urllib.request.urlopen(dreq, timeout=30)
        ok += 1
        log("  Deleted " + a["name"])
    except Exception as e:
        log("  FAILED " + a["name"])
log("Deleted " + str(ok) + "/" + str(len(assets)) + " assets")
log("Done!")
