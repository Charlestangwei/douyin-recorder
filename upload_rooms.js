const { create } = require('@actions/artifact');
const fs = require('fs');

async function main() {
  // Debug: print all runtime env vars
  console.log('GITHUB_RUN_ID=' + (process.env.GITHUB_RUN_ID || 'NOT SET'));
  console.log('ACTIONS_RUNTIME_URL=' + (process.env.ACTIONS_RUNTIME_URL || 'NOT SET'));
  console.log('ACTIONS_RUNTIME_TOKEN=' + (process.env.ACTIONS_RUNTIME_TOKEN ? 'SET(len=' + process.env.ACTIONS_RUNTIME_TOKEN.length + ')' : 'NOT SET'));
  console.log('ACTIONS_RESULTS_URL=' + (process.env.ACTIONS_RESULTS_URL || 'NOT SET'));
  console.log('RUNNER_TEMP=' + (process.env.RUNNER_TEMP || 'NOT SET'));

  const mpath = '/tmp/mkv_work/manifest.json';
  console.log('Manifest exists: ' + fs.existsSync(mpath));
  if (!fs.existsSync(mpath)) {
    console.log('No manifest');
    return;
  }
  const manifest = JSON.parse(fs.readFileSync(mpath, 'utf8'));
  const keys = Object.keys(manifest);
  console.log('Entries: ' + keys.length);
  if (!keys.length) return;

  console.log('Creating artifact client...');
  let client;
  try {
    client = create();
    console.log('Client created OK');
  } catch(e) {
    console.log('Client create FAILED: ' + e.message);
    process.exit(1);
  }

  for (const key of keys) {
    const entry = manifest[key];
    const fp = '/tmp/mkv_work/' + key + '/' + entry.merged_file;
    const exists = fs.existsSync(fp);
    console.log('  [' + key + '] file_exists=' + exists + ' path=' + fp);
    if (!exists) continue;

    const name = 'mkv-room-' + key;
    const mb = Math.round(fs.statSync(fp).size / 1024 / 1024);
    console.log('  Uploading ' + key + ' (' + mb + 'MB) as ' + name);

    try {
      console.log('  Calling uploadArtifact...');
      const r = await client.uploadArtifact(name, [fp], { retentionDays: 90 });
      console.log('  OK id=' + r.id + ' size=' + r.size + ' failedItems=' + JSON.stringify(r.failedItems));
      entry.artifact_id = r.id;
      entry.run_id = process.env.GITHUB_RUN_ID || '';
    } catch(e) {
      console.log('  FAIL: ' + e.message);
      if (e.stack) console.log('  STACK: ' + e.stack.split('\n')[0]);
    }
  }
  fs.writeFileSync(mpath, JSON.stringify(manifest, null, 2));
  console.log('Done');
}

main().catch(function(e) {
  console.error('FATAL: ' + e.message);
  process.exit(1);
});
