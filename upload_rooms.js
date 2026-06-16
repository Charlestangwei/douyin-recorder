const fs = require('fs');

async function main() {
  const { UploadArtifact } = await import('@actions/artifact');
  const manifestPath = '/tmp/mkv_work/manifest.json';
  if (!fs.existsSync(manifestPath)) {
    console.log('No manifest found, nothing to upload');
    return;
  }

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const keys = Object.keys(manifest);
  console.log('Uploading ' + keys.length + ' room artifacts...');

  for (const key of keys) {
    const entry = manifest[key];
    const filePath = '/tmp/mkv_work/' + key + '/' + entry.merged_file;

    if (!fs.existsSync(filePath)) {
      console.log('  SKIP ' + key + ': file not found');
      continue;
    }

    const artName = 'mkv-room-' + key;
    const sizeMB = Math.round(fs.statSync(filePath).size / 1024 / 1024);
    console.log('  Uploading ' + key + ' (' + sizeMB + ' MB) as ' + artName + '...');

    try {
      const uploader = new UploadArtifact();
      const result = await uploader.uploadArtifact(artName, [filePath], {
        retentionDays: 90
      });
      console.log('  OK ' + key + ': artifact_id=' + result.id);
      entry.artifact_id = result.id;
      entry.run_id = process.env.GITHUB_RUN_ID || '';
    } catch (e) {
      console.log('  FAIL ' + key + ': ' + e.message);
    }
  }

  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log('Manifest updated with artifact IDs');
}

main().catch(function(e) {
  console.error('FATAL:', e.message);
  process.exit(1);
});
