import json, os
data = []
for k, v in json.load(open("/tmp/mkv_work/manifest.json")).items():
    room = v.get("room", k.split("_")[0] if "_" in k else k)
    st = v.get("start_ts", "")
    if not st and "_" in k:
        parts = k.split("_", 1)
        if len(parts) > 1 and parts[1].isdigit():
            st = parts[1]
    data.append({"key": k, "file": v.get("merged_file", k + "_merged.mkv"), "start_ts": st})
with open(os.environ["GITHUB_OUTPUT"], "a") as f:
    f.write("rooms=" + json.dumps(data) + "\n")
