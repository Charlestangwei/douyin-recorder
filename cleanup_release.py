import os, sys, json, time, urllib.request

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Charlestangwei/douyin-recorder")
API = "https://api.github.com/repos/" + GH_REPO
HEADERS = {"Authorization": "Bearer " + GH_TOKEN, "Accept": "application/vnd.github+json"}
DATE = sys.argv[1]

def log(m):
    print("[" + time.strftime("%H:%M:%S") + "] " + m, flush=True)

def get_mkv_assets(date_str):
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
                        items.append({"asset_id": a["id"], "name": a["name"]})
            page += 1
        except:
            break
    return items

log("Scanning " + DATE + " Release assets to delete...")
assets = get_mkv_assets(DATE)
log("Found " + str(len(assets)) + " MKV assets to delete")

ok = 0
for a in assets:
    try:
        dreq = urllib.request.Request(API + "/releases/assets/" + str(a["asset_id"]), headers=HEADERS, method="DELETE")
        urllib.request.urlopen(dreq, timeout=30)
        log("  Deleted " + a["name"])
        ok += 1
    except Exception as e:
        log("  FAILED " + a["name"])

log("Deleted " + str(ok) + "/" + str(len(assets)) + " assets. Done!")
