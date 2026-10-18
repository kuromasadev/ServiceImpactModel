export const slices = ['Early AM', 'AM Peak', 'Morning', 'Mid-Day', 'Afternoon', 'PM Peak', 'After PM', 'Evening', 'Late'];

export function parseCSV(text) {
  const records = [];
  let record = [], value = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') { value += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && (c === ',' || c === '\n')) {
      record.push(value.replace(/\r$/, '')); value = '';
      if (c === '\n') { records.push(record); record = []; }
    } else value += c;
  }
  if (quoted) throw new Error('Unclosed CSV quote');
  if (value || record.length) { record.push(value.replace(/\r$/, '')); records.push(record); }
  const headers = records.shift();
  if (!headers || new Set(headers).size !== headers.length) throw new Error('Invalid CSV header');
  return records.map(fields => {
    if (fields.length !== headers.length) throw new Error('CSV field count mismatch');
    const row = Object.fromEntries(headers.map((key, i) => [key, fields[i]]));
    for (const key of ['pairs', 'scheduled_seconds', 'observed_seconds', 'scheduled_miles', 'observed_miles',
      'scheduled_miles_samples', 'observed_miles_samples', 'time_slice_order']) {
      row[key] = Number(row[key]);
      if (!Number.isFinite(row[key]) || row[key] < 0) throw new Error('Invalid aggregate number');
    }
    for (const key of ['delay_histogram', 'terminal_delay_histogram', 'source_batch_sha256', 'qa_flags']) row[key] = JSON.parse(row[key]);
    return row;
  });
}

export function distribution(rows, event = 'terminal', early = -59, late = 359) {
  if (!Number.isFinite(early) || !Number.isFinite(late) || early > late) throw new Error('Thresholds must be finite and ordered.');
  const result = { early: 0, onTime: 0, late: 0, total: 0, signedSeconds: 0, positiveSeconds: 0 };
  for (const row of rows) {
    for (const [delay, count] of Object.entries(row[event === 'terminal' ? 'terminal_delay_histogram' : 'delay_histogram'])) {
      const seconds = Number(delay);
      if (!Number.isFinite(seconds) || !Number.isInteger(count) || count < 0) throw new Error('Invalid delay histogram');
      result.total += count;
      result.signedSeconds += seconds * count;
      result.positiveSeconds += Math.max(0, seconds) * count;
      result[seconds < early ? 'early' : seconds > late ? 'late' : 'onTime'] += count;
    }
  }
  result.rate = result.total ? result.onTime / result.total : null;
  return result;
}

export function rankScenarios(rows, event, early, late, direction = 'higher') {
  const scenarios = [
    { name: event === 'terminal' ? 'Statutory OTP' : 'Statutory thresholds · stop-pair alternative', earlyLimit: -59, lateLimit: 359 },
    { name: 'Exploratory alternative', earlyLimit: early, lateLimit: late }
  ].map(s => ({ ...s, ...distribution(rows, event, s.earlyLimit, s.lateLimit) }));
  scenarios.sort((a, b) => direction === 'higher' ? (b.rate ?? -1) - (a.rate ?? -1) : (a.rate ?? 2) - (b.rate ?? 2));
  scenarios.forEach((s, i) => { s.rank = s.rate === null ? '—' : i && s.rate === scenarios[i - 1].rate ? scenarios[i - 1].rank : i + 1; });
  return scenarios;
}
