import os, sys, json, re, urllib.request, base64, subprocess, time

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Charlestangwei/douyin-recorder")
API = f"https://api.github.com/repos/{GH_REPO}"
HEADERS = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}

def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def get_releases_by_date(date_str):
    """Find all releases containing date_str in tag name that are MKV with assets."""
    items = []
    page = 1
    while True:
        url = f"{API}/releases?per_page=100&page={page}"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.loads(resp.read())
            if not data:
                break
            for r in data:
                tag = r["tag_name"]
                if date_str in tag and tag.endswith(".mkv"):
                    for a in r.get("assets", []):
                        items.append({
                            "tag": tag, "asset_id": a["id"],
                            "name": a["name"], "size": a["size"],
                            "dl_url": a["browser_download_url"],
                            "asset_url": a["url"]
                        })
            page += 1
        except:
            break
    return items

def delete_asset(asset_id):
    url = f"{API}/releases/assets/{asset_id}"
    req = urllib.request.Request(url, headers=HEADERS, method="DELETE")
    resp = urllib.request.urlopen(req, timeout=30)
    return resp.status == 204

log(f"Scanning releases for date: {sys.argv[1]}")
items = get_releases_by_date(sys.argv[1])
log(f"Found {len(items)} MKV files")

if not items:
    log("Nothing to do.")
    sys.exit(0)

# Download MKVs to /tmp/mkv_input/
os.makedirs("/tmp/mkv_input", exist_ok=True)
downloaded = []
for item in items:
    fpath = f"/tmp/mkv_input/{item['name']}"
    log(f"Downloading {item['name']}...")
    req = urllib.request.Request(item["dl_url"])
    resp = urllib.request.urlopen(req, timeout=300)
    with open(fpath, "wb") as f:
        while True:
            chunk = resp.read(8192*1024)
            if not chunk:
                break
            f.write(chunk)
    downloaded.append({"path": fpath, "name": item["name"]})
    log(f"  Done ({os.path.getsize(fpath)/1024/1024:.0f} MB)")

log(f"Downloaded {len(downloaded)} files to /tmp/mkv_input/")

# Generate manifest entry
manifest_entry = {}
for d in downloaded:
    # Extract base key: A8888288889_20260529_120045
    m = re.match(r"(.+?)_(\d{3})\.mkv", d["name"])
    if m:
        base_key = m.group(1)
        if base_key not in manifest_entry:
            manifest_entry[base_key] = {"files": [], "backup_date": time.strftime("%Y-%m-%d")}
        manifest_entry[base_key]["files"].append(d["name"])

# Save manifest to /tmp/mkv_input/manifest.json
with open("/tmp/mkv_input/manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest_entry, f, indent=2, ensure_ascii=False)
log(f"Manifest saved: {len(manifest_entry)} entries")

# Delete MKV assets from releases
log("Deleting MKV assets from releases...")
ok = 0
for item in items:
    try:
        delete_asset(item["asset_id"])
        ok += 1
        log(f"  Deleted {item['name']}")
    except Exception as e:
        log(f"  FAILED {item['name']}: {e}")
log(f"Deleted {ok}/{len(items)} assets")

log("Done! MKV files are in /tmp/mkv_input/ - upload-artifact will handle the rest.")
