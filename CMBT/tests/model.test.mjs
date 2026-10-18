import test from 'node:test';
import assert from 'node:assert/strict';
import { distribution, rankScenarios, parseCSV } from '../site/model.mjs';

const rows = [{ delay_histogram: { '-60': 1, '-59': 1, '359': 1, '360': 1 },
  terminal_delay_histogram: { '-60': 1, '-59': 1, '359': 1, '360': 1 } }];

test('statutory boundaries and denominator', () => {
  const result = distribution(rows);
  assert.equal(result.early, 1); assert.equal(result.onTime, 2); assert.equal(result.late, 1);
  assert.equal(result.total, 4); assert.equal(result.rate, .5);
  assert.equal(distribution([]).rate, null);
});

test('alternative ranking retains thresholds and exposes ties', () => {
  const same = rankScenarios(rows, 'terminal', -59, 359);
  assert.deepEqual(same.map(s => s.rank), [1, 1]);
  assert.equal(same[0].earlyLimit, -59); assert.equal(same[0].lateLimit, 359);
  assert.equal(rankScenarios(rows, 'terminal', -60, 360)[0].name, 'Exploratory alternative');
  assert.equal(rankScenarios(rows, 'terminal', -60, 360, 'lower')[0].name, 'Statutory OTP');
  assert.throws(() => distribution(rows, 'terminal', 1, -1), /ordered/);
});

test('terminal and pair denominators remain distinct', () => {
  const pairOnly = [{ delay_histogram: { '0': 12 }, terminal_delay_histogram: {} }];
  assert.equal(distribution(pairOnly).total, 0);
  assert.equal(distribution(pairOnly, 'pair').total, 12);
  assert.match(rankScenarios(pairOnly, 'pair', -59, 359)[0].name, /alternative/);
});

test('CSV quoting, embedded newlines, malformed field count', () => {
  const fields = ['route', 'pairs', 'scheduled_seconds', 'observed_seconds', 'scheduled_miles', 'observed_miles',
    'scheduled_miles_samples', 'observed_miles_samples', 'time_slice_order', 'delay_histogram',
    'terminal_delay_histogram', 'source_batch_sha256', 'qa_flags'];
  const values = ['R162,\n"test"', 4, 60, 120, 1, 2, 1, 1, 8, '{"-60":1,"-59":1,"359":1,"360":1}', '{}', '["test-hash"]', '[]'];
  const encode = value => '"' + String(value).replaceAll('"', '""') + '"';
  const parsed = parseCSV(fields.join(',') + '\r\n' + values.map(encode).join(',') + '\r\n');
  assert.equal(parsed[0].route, 'R162,\n"test"');
  assert.equal(distribution(parsed, 'pair').total, 4);
  assert.throws(() => parseCSV('a,b\n1,2,3\n'), /field count/);
  assert.throws(() => parseCSV('a\n"unfinished'), /Unclosed/);
});
