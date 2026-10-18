import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { loadDataset, releaseAssetURL } from '../site/data.mjs';

const row = { route: 'R162', pairs: 1, scheduled_seconds: 60, observed_seconds: 70,
  scheduled_miles: 1, observed_miles: 1, scheduled_miles_samples: 1, observed_miles_samples: 1,
  time_slice_order: 0, delay_histogram: '{"10":1}', terminal_delay_histogram: '{"10":1}',
  source_batch_sha256: '["synthetic"]', qa_flags: '[]' };
const quote = value => '"' + String(value).replaceAll('"', '""') + '"';
const bytes = gzipSync(Object.keys(row).join(',') + '\n' + Object.values(row).map(quote).join(',') + '\n');
const hash = createHash('sha256').update(bytes).digest('hex');
const tag = `commuter-2026-10-18-${hash.slice(0, 12)}`;
const manifest = { status: 'approved', sha256: hash, bytes: bytes.byteLength, rows: 1, pairs: 1,
  dataset: 'https://api.github.com/repos/test/ServiceImpactModel/releases/assets/123',
  release: { repository: 'test/ServiceImpactModel', date: '2026-10-18', tag, asset_name: `${tag}.csv.gz`,
    asset_id: 123, download_url: `https://github.com/test/ServiceImpactModel/releases/download/${tag}/${tag}.csv.gz` } };
const binaryResponse = () => new Response(bytes, { headers: { 'Content-Type': 'application/octet-stream' } });

test('remote release fetch validates bytes, decompresses and parses without credentials', async () => {
  let calls = 0;
  const rows = await loadDataset(manifest, async (url, options) => {
    calls++;
    assert.equal(url, manifest.dataset);
    assert.equal(options.headers.Accept, 'application/octet-stream');
    assert.equal(options.mode, 'cors');
    assert.equal(options.credentials, 'omit');
    return binaryResponse();
  });
  assert.equal(calls, 1); assert.equal(rows.length, 1); assert.equal(rows[0].pairs, 1);
});

test('remote checksum, size and aggregate mismatches are refused', async () => {
  await assert.rejects(loadDataset(manifest, async () => new Response('wrong bytes')), /checksum/);
  await assert.rejects(loadDataset({ ...manifest, bytes: 1 }, binaryResponse), /checksum\/size/);
  await assert.rejects(loadDataset({ ...manifest, pairs: 2 }, binaryResponse), /totals/);
});

test('API metadata, HTTP errors and cross-origin failures remain visible', async () => {
  await assert.rejects(loadDataset(manifest, async () => new Response('{}', { headers: { 'Content-Type': 'application/json' } })), /metadata instead/);
  await assert.rejects(loadDataset(manifest, async () => new Response('', { status: 403 })), /HTTP 403/);
  await assert.rejects(loadDataset(manifest, async () => { throw new TypeError('CORS'); }), /cross-origin/);
});

test('only exact versioned GitHub asset references are accepted', () => {
  assert.equal(releaseAssetURL(manifest), manifest.dataset);
  assert.throws(() => releaseAssetURL({ ...manifest, dataset: 'data/commuter.csv.gz' }), /exact dated/);
  assert.throws(() => releaseAssetURL({ ...manifest, release: { ...manifest.release, tag: 'latest' } }), /exact dated/);
  assert.throws(() => releaseAssetURL({ ...manifest, release: { ...manifest.release, repository: 'https://example.com' } }), /Invalid/);
});
