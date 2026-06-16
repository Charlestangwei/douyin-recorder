const fs = require('fs');

async function main() {
  console.log('upload_rooms.js started');
  console.log('CWD: ' + process.cwd());
  console.log('Manifest exists: ' + fs.existsSync('/tmp/mkv_work/manifest.json'));

  const manifestPath = '/tmp/mkv_work/manifest.json';
  if (!fs.existsSync(manifestPath)) {
    console.log('No manifest found');
    return;
  }

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const keys = Object.keys(manifest);
  console.log('Manifest entries: ' + keys.length);

  if (keys.length === 0) {
    console.log('Nothing to upload');
    return;
  }

  console.log('Loading @actions/artifact...');
  let UploadArtifact;
  try {
    const mod = await import('@actions/artifact');
    UploadArtifact = mod.UploadArtifact;
    console.log('Loaded UploadArtifact: ' + (typeof UploadArtifact));
  } catch (e) {
    console.log('IMPORT ERROR: ' + e.message);
    console.log('Stack: ' + e.stack);
    process.exit(1);
  }

  for (const key of keys) {
    const entry = manifest[key];
    const filePath = '/tmp/mkv_work/' + key + '/' + entry.merged_file;
    console.log('  File exists: ' + key + ' -> ' + fs.existsSync(filePath) + ' (' + filePath + ')');

    if (!fs.existsSync(filePath)) {
      console.log('  SKIP ' + key + ': file not found');
      continue;
    }

    const artName = 'mkv-room-' + key;
    const sizeMB = Math.round(fs.statSync(filePath).size / 1024 / 1024);
    console.log('  Uploading ' + key + ' (' + sizeMB + ' MB)');

    try {
      const uploader = new UploadArtifact();
      console.log('  Uploader created, calling uploadArtifact...');
      const result = await uploader.uploadArtifact(artName, [filePath], {
        retentionDays: 90
      });
      console.log('  OK id=' + result.id + ' size=' + result.size);
      entry.artifact_id = result.id;
      entry.run_id = process.env.GITHUB_RUN_ID || '';
    } catch (e) {
      console.log('  FAIL: ' + e.message);
    }
  }

  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log('Manifest saved with artifact IDs');
}

main().catch(function(e) {
  console.error('FATAL: ' + e.message);
  console.error(e.stack);
  process.exit(1);
});
