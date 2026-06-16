#!/usr/bin/env python3
"""Upload a file to GitHub Actions Artifacts via internal API.
Must be run inside a GitHub Actions runner context (ACTIONS_RUNTIME_TOKEN + ACTIONS_RESULTS_URL)."""
import os, sys, json, subprocess, urllib.request, urllib.parse

def upload_artifact(name, filepath, retention_days=90):
    token = os.environ.get("ACTIONS_RUNTIME_TOKEN")
    results_url = os.environ.get("ACTIONS_RESULTS_URL")
    if not token or not results_url:
        print(f"SKIP {name}: not in Actions runner context")
        return False

    filesize = os.path.getsize(filepath)
    filename = os.path.basename(filepath)

    # Step 1: Create artifact container
    create_url = results_url.rstrip("/") + "/artifact"
    create_body = json.dumps({"name": name, "retentionDays": retention_days}).encode()

    req = urllib.request.Request(create_url, data=create_body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
        method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        upload_url = data.get("fileContainerResourceUrl", "")
        if not upload_url:
            print(f"FAIL {name}: no upload URL in response: {data}")
            return False
    except Exception as e:
        print(f"FAIL {name}: create container error: {e}")
        return False

    # Step 2: Upload file content via curl (more reliable than urllib for binary)
    put_url = upload_url.rstrip("/") + "?" + urllib.parse.urlencode({
        "itemName": filename, "itemType": "file"
    })

    result = subprocess.run([
        "curl", "-s", "-X", "PUT",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/octet-stream",
        "-H", f"Content-Range: bytes 0-{filesize-1}/{filesize}",
        "--data-binary", f"@{filepath}",
        put_url
    ], capture_output=True, text=True, timeout=300)
    
    if result.returncode == 0:
        print(f"OK {name} ({filename}, {filesize/1024/1024:.0f}MB)")
        return True
    else:
        print(f"FAIL {name}: curl error: {result.stderr[:200]}")
        return False

if __name__ == "__main__":
    upload_name = sys.argv[1]
    upload_path = sys.argv[2]
    upload_artifact(upload_name, upload_path)
