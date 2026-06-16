import json, os
keys = [{"key": k, "file": v["merged_file"]} for k, v in json.load(open("/tmp/mkv_work/manifest.json")).items()]
with open(os.environ["GITHUB_OUTPUT"], "a") as f:
    f.write("rooms=" + json.dumps(keys) + "\n")
