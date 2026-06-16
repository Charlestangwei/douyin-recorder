#!/bin/bash
set -e

python3 -c "
import os, json, subprocess, sys

RT_URL = os.environ.get('ACTIONS_RUNTIME_URL', '')
RT_TOKEN = os.environ.get('ACTIONS_RUNTIME_TOKEN', '')
RUN_ID = os.environ.get('GITHUB_RUN_ID', '')
MPATH = '/tmp/mkv_work/manifest.json'

if not os.path.exists(MPATH):
    print('No manifest found')
    sys.exit(0)

manifest = json.load(open(MPATH))
keys = list(manifest.keys())
print(f'Uploading {len(keys)} room artifacts...')

for key in keys:
    entry = manifest[key]
    fpath = f'/tmp/mkv_work/{key}/{entry[\"merged_file\"]}'
    if not os.path.exists(fpath):
        print(f'  SKIP {key}: file not found')
        continue
    
    size_mb = round(os.path.getsize(fpath) / 1024 / 1024)
    art_name = f'mkv-room-{key}'
    print(f'  Uploading {key} ({size_mb}MB) as {art_name}...')
    
    upload_url = f'{RT_URL}_apis/pipelines/workflows/{RUN_ID}/artifacts?api-version=6.0-preview'
    cmd = [
        'curl', '-s', '-L', '-X', 'POST', '--fail',
        '-H', f'Authorization: Bearer {RT_TOKEN}',
        '-F', f'name={art_name}',
        '-F', f'file=@{fpath}',
        upload_url
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=600)
    
    if result.returncode == 0:
        try:
            resp = json.loads(result.stdout)
            art_id = resp.get('id')
            print(f'  OK id={art_id}')
            manifest[key]['artifact_id'] = art_id
            manifest[key]['run_id'] = RUN_ID
        except:
            print(f'  OK (no id): {result.stdout.decode()[:100]}')
    else:
        err = result.stderr.decode()[:200] if result.stderr else result.stdout.decode()[:200]
        print(f'  FAILED: {err}')

json.dump(manifest, open(MPATH, 'w'), indent=2)
print('Done!')
"
