import { distribution, rankScenarios, slices } from './model.mjs';
import { loadDataset } from './data.mjs';

const $ = id => document.getElementById(id);
const format = value => Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
const sum = (rows, key) => rows.reduce((n, row) => n + row[key], 0);
let rows = [], manifest;

function table(id, values) {
  const body = $(id); body.replaceChildren();
  if (!values.length) values = [['No matching observations.']];
  for (const fields of values) {
    const tr = document.createElement('tr');
    for (const value of fields) { const td = document.createElement('td'); td.textContent = value; tr.append(td); }
    body.append(tr);
  }
}

function render() {
  if (!$('filters').reportValidity()) return;
  const early = Number($('early').value), late = Number($('late').value);
  if (early > late) { $('status').textContent = 'Alternative earliest threshold must be at or below the latest threshold.'; return; }
  const selected = rows.filter(row => ['route', 'direction', 'time_slice', 'period', 'phase', 'movement', 'passenger_presence']
    .every(key => !$(key).value || row[key] === $(key).value) &&
    (!$('date_from').value || row.service_date >= $('date_from').value) &&
    (!$('date_to').value || row.service_date <= $('date_to').value));
  $('status').textContent = 'Approved aggregate dataset loaded. Adjust filters to explore service.';
  const total = sum(selected, 'pairs');
  $('pairs').textContent = format(total);
  $('minutes').textContent = `${format(sum(selected, 'scheduled_seconds') / 60)} / ${format(sum(selected, 'observed_seconds') / 60)}`;
  const mileage = key => sum(selected, `${key}_samples`) ? format(sum(selected, key)) : 'unavailable';
  $('miles').textContent = `${mileage('scheduled_miles')} / ${mileage('observed_miles')}`;
  const nonrevenue = selected.filter(row => row.movement !== 'scheduled_service');
  $('nonrevenue').textContent = `${sum(nonrevenue, 'observed_miles_samples') ? format(sum(nonrevenue, 'observed_miles')) : 'unavailable'} / ${format(sum(nonrevenue, 'observed_seconds') / 60)}`;
  const dates = selected.map(row => row.service_date).sort();
  $('coverage').textContent = `File coverage ${manifest.coverage_start}–${manifest.coverage_end}; selected ${dates[0] ?? '—'}–${dates.at(-1) ?? '—'}. Baseline ${manifest.baseline_status}. ${new Set(selected.flatMap(row => row.source_batch_sha256)).size} contributing batches.`;
  const flags = [...new Set(selected.flatMap(row => row.qa_flags))];
  const unknown = sum(selected.filter(row => row.phase === 'unclassified'), 'pairs');
  $('warnings').textContent = `${format(unknown)} unclassified phase pairs; ${format(sum(selected.filter(row => row.passenger_presence === 'unknown'), 'pairs'))} pairs with unknown passenger presence; ${format(sum(selected.filter(row => row.crosses_cutover === 'true'), 'pairs'))} pairs crossing cutover; ${format(sum(selected.filter(row => row.trip_crosses_cutover === 'true'), 'pairs'))} pairs on crossing trips. Mileage samples: scheduled ${format(sum(selected, 'scheduled_miles_samples'))}/${format(total)}, observed ${format(sum(selected, 'observed_miles_samples'))}/${format(total)}. ${flags.length ? 'QA: ' + flags.join('; ') : 'No row-level QA flags.'}`;
  const eligible = selected.filter(row => row.movement === 'scheduled_service');
  const event = $('event').value;
  $('denominator').textContent = `Denominator: scheduled-service ${event === 'terminal' ? 'verified terminal' : 'stop-pair'} arrival events in the selected rows, including empty/unknown passenger presence. Deadhead and other non-revenue excluded. Event timestamp: actual ${event === 'terminal' ? 'terminal' : 'pair-end'} arrival against its scheduled arrival. ${event !== 'terminal' ? 'Stop-pair results are an alternative measure, not statutory terminal OTP.' : ''}`;
  table('scenarios', rankScenarios(eligible, event, early, late, $('ranking').value).map(s => [s.rank, `${s.name} [${s.earlyLimit}, ${s.lateLimit}]`, format(s.early), format(s.onTime), format(s.late), format(s.total), s.rate === null ? '—' : `${format(s.rate * 100)}%`]));
  table('terminal', [...new Set(eligible.map(row => row.route))].sort().map(route => {
    const d = distribution(eligible.filter(row => row.route === route));
    return [route, format(d.total), d.total ? format(d.signedSeconds / d.total / 60) : '—', d.total ? format(d.positiveSeconds / d.total / 60) : '—', format(d.late)];
  }));
  const phases = ['pr_connection', 'freeway', 'destination_connection', 'unclassified'];
  table('phases', phases.map(phase => {
    const part = selected.filter(row => row.phase === phase);
    return [phase.replaceAll('_', ' '), format(sum(part, 'pairs')), format(sum(part, 'scheduled_seconds') / 60), format(sum(part, 'observed_seconds') / 60), format((sum(part, 'observed_seconds') - sum(part, 'scheduled_seconds')) / 60)];
  }));
}

async function load() {
  const response = await fetch('./manifest.json', { cache: 'no-store' });
  if (!response.ok) throw new Error('Could not load data availability information.');
  manifest = await response.json();
  if (manifest.status !== 'approved' || !manifest.dataset) { $('status').textContent = manifest.message; return; }
  rows = await loadDataset(manifest);
  for (const key of ['route', 'direction', 'time_slice', 'phase']) {
    const options = [...new Set(rows.map(row => row[key]))];
    options.sort((a, b) => key === 'time_slice' ? slices.indexOf(a) - slices.indexOf(b) : a.localeCompare(b));
    for (const value of options) { const option = document.createElement('option'); option.value = value; option.textContent = value.replaceAll('_', ' '); $(key).append(option); }
  }
  $('controls').disabled = false;
  $('filters').addEventListener('submit', e => e.preventDefault());
  $('filters').addEventListener('input', render);
  render();
}
load().catch(error => { $('status').textContent = `Data unavailable: ${error.message}`; $('controls').disabled = true; });
