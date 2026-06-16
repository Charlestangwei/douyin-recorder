import os, json, sys
manifest_path = '/tmp/mkv_work/manifest.json'
if not os.path.exists(manifest_path):
    sys.exit(0)
with open(manifest_path) as f:
    m = json.load(f)
uploaded = 0
for key, info in m.items():
    mfile = info.get('merged_file', key + '_merged.mkv')
    fpath = os.path.join('/tmp/mkv_work', key, mfile)
    if not os.path.exists(fpath):
        fpath = os.path.join('/tmp/mkv_work', mfile)
    if not os.path.exists(fpath):
        print('SKIP ' + key + ': file not found')
        continue
    print('Uploading ' + key + '...')
    ret = os.system('python3 upload_artifact.py mkv-room-' + key + ' "' + fpath + '"')
    if ret == 0:
        uploaded += 1
        print('  OK: ' + key)
    else:
        print('  FAIL: ' + key)
print('Uploaded ' + str(uploaded) + '/' + str(len(m)) + ' rooms')
