const fs = require('fs');

async function main() {
  console.log('upload_rooms.js started');

  const manifestPath = '/tmp/mkv_work/manifest.json';
  if (!fs.existsSync(manifestPath)) {
    console.log('No manifest found at ' + manifestPath);
    return;
  }

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const keys = Object.keys(manifest);
  console.log('Manifest entries: ' + keys.length);

  if (keys.length === 0) {
    console.log('Nothing to upload');
    return;
  }

  // Load @actions/artifact - try both export names
  console.log('Loading @actions/artifact...');
  let artifactClient;
  try {
    const mod = await import('@actions/artifact');
    console.log('Module exports: ' + Object.keys(mod).join(', '));
    if (typeof mod.DefaultArtifactClient === 'function') {
      artifactClient = new mod.DefaultArtifactClient();
      console.log('Using DefaultArtifactClient');
    } else if (typeof mod.UploadArtifact === 'function') {
      artifactClient = new mod.UploadArtifact();
      console.log('Using UploadArtifact');
    } else if (typeof mod.ArtifactClient === 'function') {
      artifactClient = new mod.ArtifactClient();
      console.log('Using ArtifactClient');
    } else {
      console.log('No known class found, trying module itself');
      for (var k of Object.keys(mod)) {
        console.log('  ' + k + ': ' + typeof mod[k]);
      }
      process.exit(1);
    }
  } catch (e) {
    console.log('IMPORT ERROR: ' + e.message);
    process.exit(1);
  }

  for (const key of keys) {
    const entry = manifest[key];
    const filePath = '/tmp/mkv_work/' + key + '/' + entry.merged_file;
    const exists = fs.existsSync(filePath);
    console.log('  [' + key + '] exists=' + exists + ' path=' + filePath);

    if (!exists) continue;

    const artName = 'mkv-room-' + key;
    const sizeMB = Math.round(fs.statSync(filePath).size / 1024 / 1024);
    console.log('  Uploading ' + key + ' (' + sizeMB + ' MB) as ' + artName);

    try {
      const result = await artifactClient.uploadArtifact(artName, [filePath], {
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
  console.log('Manifest saved');
}

main().catch(function(e) {
  console.error('FATAL: ' + e.message);
  process.exit(1);
});
