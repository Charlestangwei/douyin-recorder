import os, sys, json, re, time, subprocess, urllib.request, base64

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Charlestangwei/douyin-recorder")
API = "https://api.github.com/repos/" + GH_REPO
HEADERS = {"Authorization": "Bearer " + GH_TOKEN, "Accept": "application/vnd.github+json"}
DATE = sys.argv[1]
WORK_DIR = "/tmp/mkv_work"
os.makedirs(WORK_DIR, exist_ok=True)

def log(m):
    print("[" + time.strftime("%H:%M:%S") + "] " + m, flush=True)

def get_mkv_by_date(date_str):
    items = []
    page = 1
    while True:
        url = API + "/releases?per_page=100&page=" + str(page)
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
            if not data:
                break
            for r in data:
                tag = r["tag_name"]
                if date_str in tag and tag.endswith(".mkv"):
                    for a in r.get("assets", []):
                        items.append({"tag": tag, "asset_id": a["id"], "name": a["name"], "dl_url": a["browser_download_url"], "room": tag.split("_")[0]})
            page += 1
        except:
            break
    return items

def dl(url, dest):
    resp = urllib.request.urlopen(urllib.request.Request(url), timeout=600)
    with open(dest, "wb") as f:
        while True:
            chunk = resp.read(8*1024*1024)
            if not chunk:
                break
            f.write(chunk)

log("Scanning " + DATE + "...")
items = get_mkv_by_date(DATE)
log("Found " + str(len(items)) + " MKV files")

rooms = {}
for item in items:
    rooms.setdefault(item["room"], []).append(item)
for rid in rooms:
    rooms[rid].sort(key=lambda x: x["name"])

log("Rooms: " + str(list(rooms.keys())))

manifest = {}
for room_id, segs in rooms.items():
    log("Processing " + room_id + ": " + str(len(segs)) + " segments")
    rd = os.path.join(WORK_DIR, room_id)
    os.makedirs(rd, exist_ok=True)
    dl_files = []
    for s in segs:
        fp = os.path.join(rd, s["name"])
        log("  DL " + s["name"] + "...")
        dl(s["dl_url"], fp)
        dl_files.append(fp)
    
    merged_name = room_id + "_" + DATE + "_merged.mkv"
    merged_path = os.path.join(rd, merged_name)
    
    # Concat
    cl = os.path.join(WORK_DIR, "concat_" + room_id + ".txt")
    with open(cl, "w") as f:
        for fp in dl_files:
            f.write("file '" + fp + "'\n")
    
    log("  Merging -> " + merged_name)
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl, "-c", "copy", "-movflags", "+faststart", merged_path],
                       capture_output=True, timeout=3600)
    ok = os.path.exists(merged_path)
    log("  Merge " + ("OK" if ok else "FAILED") + " (" + str(os.path.getsize(merged_path)/1024/1024) + " MB)" if ok else "")
    
    manifest[room_id] = {
        "date": DATE,
        "merged_file": merged_name,
        "segments": len(segs),
        "backup_date": time.strftime("%Y-%m-%d"),
        "artifact_id": None
    }
    
    for s in segs:
        try:
            dreq = urllib.request.Request(API + "/releases/assets/" + str(s["asset_id"]), headers=HEADERS, method="DELETE")
            urllib.request.urlopen(dreq, timeout=30)
            log("  Deleted " + s["name"])
        except Exception as e:
            log("  DEL FAIL " + s["name"] + ": " + str(e))

with open(os.path.join(WORK_DIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
log("Manifest saved. Done!")
