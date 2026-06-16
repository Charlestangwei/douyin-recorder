import os, sys, json, re, time, subprocess, urllib.request

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
        try:
            data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30).read())
            if not data:
                break
            for r in data:
                tag = r["tag_name"]
                if date_str in tag and tag.endswith(".mkv"):
                    for a in r.get("assets", []):
                        parts = a["name"].split("_")
                        room = parts[0]
                        start_ts = parts[1] + "_" + parts[2] if len(parts) > 2 else parts[1]
                        items.append({"tag": tag, "asset_id": a["id"], "name": a["name"], "dl_url": a["browser_download_url"], "room": room, "start_ts": start_ts})
            page += 1
        except:
            break
    return items

def group_by_session(items):
    sessions = {}
    for item in items:
        key = item["room"] + "_" + item["start_ts"]
        if key not in sessions:
            sessions[key] = {"room": item["room"], "start_ts": item["start_ts"], "segs": []}
        sessions[key]["segs"].append(item)
    for key in sessions:
        sessions[key]["segs"].sort(key=lambda x: x["name"])
    return sessions

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
sessions = group_by_session(items)
log("Grouped into " + str(len(sessions)) + " sessions")

manifest = {}
for key, session in sessions.items():
    room, start_ts = session["room"], session["start_ts"]
    segs = session["segs"]
    log("Processing " + key + ": " + str(len(segs)) + " segments")

    rd = os.path.join(WORK_DIR, room + "_" + start_ts)
    os.makedirs(rd, exist_ok=True)
    dl_files = []
    for s in segs:
        fp = os.path.join(rd, s["name"])
        log("  DL " + s["name"])
        dl(s["dl_url"], fp)
        dl_files.append(fp)

    merged_name = room + "_" + start_ts + "_merged.mkv"
    merged_path = os.path.join(rd, merged_name)

    if len(dl_files) > 1:
        cl = os.path.join(WORK_DIR, "concat_" + room + "_" + start_ts + ".txt")
        with open(cl, "w") as cf:
            for fp in dl_files:
                cf.write("file '" + fp + "'\n")
        log("  Merging " + str(len(dl_files)) + " segments...")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl, "-c", "copy", "-movflags", "+faststart", merged_path], capture_output=True, timeout=3600)
        if os.path.exists(merged_path):
            log("  Merged OK (" + str(round(os.path.getsize(merged_path)/1024/1024)) + " MB)")
        else:
            log("  Merge FAILED, using first segment")
            merged_path = dl_files[0]
    else:
        merged_path = dl_files[0]
        log("  Single segment, no merge")

    manifest[key] = {"room": room, "date": DATE, "start_ts": start_ts,
                     "merged_file": merged_name if len(dl_files) > 1 else segs[0]["name"],
                     "segments": len(segs), "backup_date": time.strftime("%Y-%m-%d")}

    # Delete Release assets AFTER merge
    for s in segs:
        try:
            dreq = urllib.request.Request(API + "/releases/assets/" + str(s["asset_id"]), headers=HEADERS, method="DELETE")
            urllib.request.urlopen(dreq, timeout=30)
            log("  Deleted " + s["name"])
        except Exception as e:
            log("  DEL FAIL " + s["name"])

with open(os.path.join(WORK_DIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

log("Manifest saved. Done!")
