import { parseCSV } from './model.mjs';

export function releaseAssetURL(manifest) {
  const release = manifest.release;
  if (!release || !/^[A-Za-z0-9_-][A-Za-z0-9_.-]*\/[A-Za-z0-9_-][A-Za-z0-9_.-]*$/.test(release.repository)
      || !/^\d{4}-\d{2}-\d{2}$/.test(release.date) || !/^[0-9a-f]{64}$/.test(manifest.sha256)
      || !Number.isSafeInteger(release.asset_id) || release.asset_id <= 0) {
    throw new Error('Invalid dated GitHub Release reference.');
  }
  const tag = `commuter-${release.date}-${manifest.sha256.slice(0, 12)}`;
  const name = `${tag}.csv.gz`;
  const url = `https://api.github.com/repos/${release.repository}/releases/assets/${release.asset_id}`;
  if (release.tag !== tag || release.asset_name !== name || manifest.dataset !== url
      || release.download_url !== `https://github.com/${release.repository}/releases/download/${tag}/${name}`) {
    throw new Error('Dataset must point to the exact dated Release asset.');
  }
  return url;
}

export async function loadDataset(manifest, fetcher = globalThis.fetch) {
  const url = releaseAssetURL(manifest);
  if (!globalThis.DecompressionStream || !globalThis.crypto?.subtle) {
    throw new Error('This browser needs gzip and secure SHA-256 support. Use a current browser over HTTPS or localhost.');
  }
  let response;
  try {
    response = await fetcher(url, {
      headers: { Accept: 'application/octet-stream' }, mode: 'cors', credentials: 'omit',
      referrerPolicy: 'no-referrer'
    });
  } catch {
    throw new Error('GitHub Release download failed. Check network access and cross-origin download support.');
  }
  if (!response.ok) throw new Error(`GitHub Release download failed (HTTP ${response.status}); check public access and API rate limits.`);
  if ((response.headers.get('content-type') || '').includes('json')) {
    throw new Error('GitHub returned asset metadata instead of gzip bytes; the Release download path needs verification.');
  }
  const bytes = await response.arrayBuffer();
  const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(b => b.toString(16).padStart(2, '0')).join('');
  if (digest !== manifest.sha256 || bytes.byteLength !== manifest.bytes) {
    throw new Error('Release dataset checksum/size does not match the approved manifest.');
  }
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  const rows = parseCSV(await new Response(stream).text());
  if (rows.length !== manifest.rows || rows.reduce((n, row) => n + row.pairs, 0) !== manifest.pairs) {
    throw new Error('Dataset totals do not match the release manifest.');
  }
  return rows;
}
