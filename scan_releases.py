import os, sys, json, time, urllib.request, re
GH_TOKEN = os.environ.get("GH_TOKEN", "")
API = "https://api.github.com/repos/" + os.environ.get("GH_REPO", "Charlestangwei/douyin-recorder")
HEADERS = {"Authorization": "Bearer " + GH_TOKEN} if GH_TOKEN else {}
DATE = sys.argv[1]

manifest = {}
page = 1
while True:
    url = API + "/releases?per_page=100&page=" + str(page)
    try:
        data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30).read())
        if not data: break
    except: break
    for r in data:
        tag = r["tag_name"]
        if DATE not in tag or not tag.endswith(".mkv"):
            continue
        for a in r.get("assets", []):
            n = a["name"]
            m = re.match(r"(.+)_(\d{8}_\d{6})_\d+\.mkv", n)
            if not m: continue
            room = m.group(1)
            st = m.group(2)
            key = room + "_" + st
            if key not in manifest:
                manifest[key] = {
                    "room": room, "date": DATE, "start_ts": st,
                    "merged_file": key + "_merged.mkv",
                    "segments": 0, "backup_date": time.strftime("%Y-%m-%d")
                }
            manifest[key]["segments"] += 1
    page += 1
    if page > 15: break

os.makedirs("/tmp/mkv_work", exist_ok=True)
with open("/tmp/mkv_work/manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print("Scanned " + str(len(manifest)) + " sessions for " + DATE)
