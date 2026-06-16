const { create } = require('@actions/artifact');
const fs = require('fs');

async function main() {
  const mpath = '/tmp/mkv_work/manifest.json';
  if (!fs.existsSync(mpath)) {
    console.log('No manifest');
    return;
  }
  const manifest = JSON.parse(fs.readFileSync(mpath, 'utf8'));
  const keys = Object.keys(manifest);
  console.log('Entries: ' + keys.length);
  if (!keys.length) return;

  const client = create();
  console.log('Client created');

  for (const key of keys) {
    const entry = manifest[key];
    const fp = '/tmp/mkv_work/' + key + '/' + entry.merged_file;
    if (!fs.existsSync(fp)) {
      console.log('  SKIP ' + key);
      continue;
    }
    const name = 'mkv-room-' + key;
    const mb = Math.round(fs.statSync(fp).size / 1024 / 1024);
    console.log('  Upload ' + key + ' (' + mb + 'MB)');

    try {
      const r = await client.uploadArtifact(name, [fp], { retentionDays: 90 });
      console.log('  OK id=' + r.id);
      entry.artifact_id = r.id;
      entry.run_id = process.env.GITHUB_RUN_ID || '';
    } catch(e) {
      console.log('  FAIL: ' + e.message);
    }
  }
  fs.writeFileSync(mpath, JSON.stringify(manifest, null, 2));
  console.log('Done');
}

main().catch(function(e) {
  console.error('FATAL: ' + e.message);
  process.exit(1);
});
