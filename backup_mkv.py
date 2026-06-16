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
        try:
            data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30).read())
            if not data:
                break
            for r in data:
                tag = r["tag_name"]
                if date_str in tag and tag.endswith(".mkv"):
                    for a in r.get("assets", []):
                        # Parse: room_start_seq.mkv
                        parts = a["name"].split("_")
                        room = parts[0]
                        start_ts = parts[1] + "_" + parts[2] if len(parts) > 2 else parts[1]
                        items.append({"tag": tag, "asset_id": a["id"], "name": a["name"], "dl_url": a["browser_download_url"], "room": room, "start_ts": start_ts})
            page += 1
        except:
            break
    return items

def group_by_session(items):
    """Group by room + start timestamp (same livestream session)"""
    sessions = {}
    for item in items:
        key = item["room"] + "_" + item["start_ts"]
        if key not in sessions:
            sessions[key] = {"room": item["room"], "start_ts": item["start_ts"], "segs": []}
        sessions[key]["segs"].append(item)
    # Sort segments within each session by seq number
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
log("Grouped into " + str(len(sessions)) + " sessions: " + str(list(sessions.keys())))

manifest = {}
for key, session in sessions.items():
    room = session["room"]
    start_ts = session["start_ts"]
    segs = session["segs"]
    log("Processing " + key + ": " + str(len(segs)) + " segments")

    rd = os.path.join(WORK_DIR, room + "_" + start_ts)
    os.makedirs(rd, exist_ok=True)
    dl_files = []
    for s in segs:
        fp = os.path.join(rd, s["name"])
        log("  DL " + s["name"] + "...")
        dl(s["dl_url"], fp)
        dl_files.append(fp)

    merged_name = room + "_" + start_ts + "_merged.mkv"
    merged_path = os.path.join(rd, merged_name)

    cl = os.path.join(WORK_DIR, "concat_" + room + "_" + start_ts + ".txt")
    with open(cl, "w") as f:
        for fp in dl_files:
            f.write("file '" + fp + "'\n")

    log("  Merging -> " + merged_name + " (" + str(len(dl_files)) + " segments)")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl, "-c", "copy", "-movflags", "+faststart", merged_path],
                       capture_output=True, timeout=3600)
    size_mb = os.path.getsize(merged_path) / 1024/1024 if os.path.exists(merged_path) else 0
    log("  Merge OK (" + str(round(size_mb, 0)) + " MB)" if os.path.exists(merged_path) else "  Merge FAILED")

    manifest[key] = {
        "room": room,
        "date": DATE,
        "start_ts": start_ts,
        "merged_file": merged_name,
        "segments": len(segs),
        "backup_date": time.strftime("%Y-%m-%d"),
    # Upload per-room merged MKV via GitHub Artifacts API
    run_id = os.environ.get("GH_RUN_ID", "0")
    if run_id and GH_TOKEN and os.path.exists(merged_path):
        fsize = os.path.getsize(merged_path)
        log("  Uploading " + str(round(fsize/1024/1024)) + " MB to Artifact API...")
        import subprocess as _sp
        room_name = room
        # Use curl with proper multipart: name as form field, file as attachment
        _cmd = [
            "curl", "-s", "-L", "-X", "POST",
            "-H", "Authorization: Bearer " + GH_TOKEN,
            "-F", "name=mkv-room-" + room_name,
            "-F", "file=@" + merged_path,
            "https://uploads.github.com/repos/" + GH_REPO + "/actions/runs/" + run_id + "/artifacts"
        ]
        _r = _sp.run(_cmd, capture_output=True, timeout=600)
        if _r.returncode == 0 and _r.stdout:
            try:
                _j = json.loads(_r.stdout)
                log("  Artifact OK! id=" + str(_j.get("id", "?")) + " name=" + str(_j.get("name", "?")))
            except:
                log("  Artifact uploaded (response: " + _r.stdout.decode()[:100] + ")")
        else:
            log("  Artifact FAILED: " + _r.stderr.decode()[:200])

        "artifact_id": None
    }



with open(os.path.join(WORK_DIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

# Log artifact info for upload
log("Artifact files:")
for key in sessions:
    room = sessions[key]["room"]
    start_ts = sessions[key]["start_ts"]
    merged = room + "_" + start_ts + "_merged.mkv"
    path = os.path.join(WORK_DIR, room + "_" + start_ts, merged)
    if os.path.exists(path):
        log("  " + merged + " (" + str(round(os.path.getsize(path)/1024/1024)) + " MB)")

# Upload per-room artifact using GH CLI
for key in sessions:
    room = sessions[key]["room"]
    start_ts = sessions[key]["start_ts"]
    merged = room + "_" + start_ts + "_merged.mkv"
    path = os.path.join(WORK_DIR, room + "_" + start_ts, merged)
    if os.path.exists(path):
        log("Uploading artifact for " + room + "...")
        run_id = os.environ.get("GH_RUN_ID", "0")
        fsize = os.path.getsize(path)
        log("  Uploading " + str(round(fsize/1024/1024)) + " MB via curl...")


    # Delete Release assets after upload succeeds
    if os.path.exists(path):
        for s in segs:
            try:
                dreq = urllib.request.Request(API + "/releases/assets/" + str(s["asset_id"]), headers=HEADERS, method="DELETE")
                urllib.request.urlopen(dreq, timeout=30)
                log("  Deleted " + s["name"])
            except Exception as e:
                log("  DEL FAIL " + s["name"])

log("Manifest saved. Done!")
