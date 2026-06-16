import os, sys, json, time, urllib.request, subprocess
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Charlestangwei/douyin-recorder")
API = "https://api.github.com/repos/" + GH_REPO
HDR = {"Authorization": "Bearer " + GH_TOKEN} if GH_TOKEN else {}
DATE = sys.argv[1]
ROOM_KEY = sys.argv[2]
START_TS = sys.argv[3]
OUT_DIR = "/tmp/mkv_work/" + ROOM_KEY
os.makedirs(OUT_DIR, exist_ok=True)

segs = []
page = 1
while True:
    try:
        rq = urllib.request.Request(API + "/releases?per_page=100&page=" + str(page), headers=HDR)
        rs = json.loads(urllib.request.urlopen(rq, timeout=30).read())
        if not rs: break
    except: break
    for r in rs:
        if ROOM_KEY in r["tag_name"] and r["tag_name"].endswith(".mkv"):
            for a in r.get("assets", []):
                n = a["name"]
                if START_TS in n and n.endswith(".mkv"):
                    segs.append((a["browser_download_url"], n, a["size"]))
    page += 1
    if page > 15: break

if not segs:
    print("No segments for " + ROOM_KEY + "/" + START_TS)
    sys.exit(1)
segs.sort()
total_mb = sum(s[2] for s in segs) / 1024 / 1024
print("Found " + str(len(segs)) + " segments (" + "{:.0f}".format(total_mb) + "MB)")

files = []
for url, name, _ in segs:
    out = os.path.join(OUT_DIR, name)
    if not os.path.exists(out):
        print("  DL " + name + "...")
        with open(out, "wb") as f:
            f.write(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=300).read())
    files.append(out)

outfile = os.path.join(OUT_DIR, ROOM_KEY + "_merged.mkv")
if len(segs) == 1:
    os.rename(files[0], outfile)
else:
    lst = os.path.join(OUT_DIR, "list.txt")
    with open(lst, "w") as f:
        for fp in files:
            f.write("file '" + fp.replace("'", "'\\''") + "'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", outfile], check=True, capture_output=True)
    os.remove(lst)

print("Merged: " + outfile)
sz = os.path.getsize(outfile)
print("Size: " + "{:.0f}".format(sz / 1024 / 1024) + "MB")

# Append to shared manifest
mp = "/tmp/mkv_work/manifest.json"
man = {}
if os.path.exists(mp):
    with open(mp) as f: man = json.load(f)
man[ROOM_KEY + "_" + START_TS] = {
    "room": ROOM_KEY, "date": DATE, "start_ts": START_TS,
    "merged_file": ROOM_KEY + "_merged.mkv", "segments": len(segs),
    "backup_date": time.strftime("%Y-%m-%d")
}
with open(mp, "w") as f: json.dump(man, f, indent=2)
print("Manifest: " + ROOM_KEY + "_" + START_TS)
