const $ = id => document.getElementById(id);
const pct = n => (n * 100).toFixed(1) + '%';
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let metrics, snapshot, mode = 'at_default';
function renderTitles() {
  const q = $('search').value.trim().toLowerCase();
  const rows = snapshot.anime.filter(a => a.title.toLowerCase().includes(q) && (!$('minimum').checked || a.reviews >= 20));
  $('rowCount').textContent = `${rows.length} titles shown`;
  $('titles').innerHTML = rows.map(a => `<tr><td><button class="title-button" data-id="${a.anime_id}">${escape(a.title)}</button></td><td>${a.score ?? '—'}</td><td>${a.reviews}</td><td><span class="arrow" aria-hidden="true">↗</span></td></tr>`).join('') || '<tr><td colspan="4">No matching titles. Try a different search or turn off the review filter.</td></tr>';
}
function renderModels() {
  const measure = $('measure').value;
  $('modelBars').innerHTML = Object.entries(metrics.methods).map(([name,m]) => {
    const value = measure === 'auc' ? m.auc : m[mode][measure];
    return `<div class="model-row"><h3>${escape(name)}</h3><div class="track"><span style="width:${value*100}%"></span></div><strong>${pct(value)}</strong></div>`;
  }).join('');
  $('metricNote').textContent = measure === 'auc' ? 'ROC AUC measures separation across all thresholds. 50% is chance-level ranking; changing the threshold does not change AUC.' : measure === 'caught_negative' ? 'Recall: the share of Not Recommended reviews correctly identified. Higher values mean fewer negative verdicts are missed.' : 'Balanced accuracy averages the hit rate on both verdicts. Calling every review positive scores 50%.';
}
function showTitle(id) {
  const a = snapshot.anime.find(a => a.anime_id === Number(id));
  if (!a) return;
  $('detailTitle').textContent = a.title;
  $('detailBody').innerHTML = `<dl><div><dt>MyAnimeList score</dt><dd>${a.score ?? '—'} / 10</dd></div><div><dt>Collected reviews</dt><dd>${a.reviews}</dd></div><div><dt>Chart rank</dt><dd>${a.top_rank}</dd></div></dl><p>${a.reviews < 20 ? 'Small sample: this title has fewer than 20 collected reviews. Interpret its results cautiously.' : 'Collected reviews are a recent sample and may include preliminary verdicts.'}</p>`;
  $('malLink').href = `https://myanimelist.net/anime/${a.anime_id}`;
  $('details').showModal();
}
async function load() {
  try {
    const responses = await Promise.all(['results/metrics.json','results/anime.json'].map(url => fetch(url)));
    if (responses.some(r => !r.ok)) throw Error('Saved results could not be loaded.');
    [metrics,snapshot] = await Promise.all(responses.map(r => r.json()));
    const date = new Date(snapshot.scraped).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric',timeZone:'UTC'});
    $('snapshot').textContent = `SAVED SNAPSHOT · ${date} · ${snapshot.source}. Updated by the monthly analysis pipeline.`;
    $('footerDate').textContent = `Snapshot: ${date}`;
    const counts = Object.entries(metrics.counts);
    $('heroStats').innerHTML = `<div><span>Reviews analysed</span><b>${metrics.reviews.toLocaleString()}</b></div><div><span>Titles reviewed</span><b>${metrics.titles}</b></div>` + counts.map(([name,n]) => `<div><span>${escape(name)}</span><b>${pct(n/metrics.reviews)}</b></div>`).join('');
    $('distribution').innerHTML = counts.map(([name,n],i) => `<span class="verdict v${i}" style="width:${n/metrics.reviews*100}%" title="${escape(name)}: ${n} reviews"></span>`).join('');
    $('verdictLegend').innerHTML = counts.map(([name,n],i) => `<div><i class="v${i}"></i><span>${escape(name)}</span><strong>${n} <small>(${pct(n/metrics.reviews)})</small></strong></div>`).join('');
    $('gap').textContent = `TextBlob labels ${pct(metrics.original.textblob_positive_share)} of all reviews positive, while ${pct(metrics.original.actual_recommended_share)} actually recommend the show. It calls ${pct(metrics.original.not_recommended_called_positive)} of Not Recommended reviews positive at its default threshold.`;
    renderTitles(); renderModels();
  } catch(e) { $('error').hidden = false; $('error').textContent = `${e.message} Serve the repository through a local web server, then reload.`; $('snapshot').textContent = 'Results unavailable'; $('heroStats').textContent = 'Saved results unavailable'; }
}
$('search').addEventListener('input',()=>snapshot && renderTitles());
$('minimum').addEventListener('change',()=>snapshot && renderTitles());
$('titles').addEventListener('click',e=>{const button=e.target.closest('[data-id]');if(button)showTitle(button.dataset.id);});
$('measure').addEventListener('change',()=>metrics && renderModels());
document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.mode;document.querySelectorAll('[data-mode]').forEach(x=>x.setAttribute('aria-pressed',x===b));if(metrics)renderModels();}));
$('close').addEventListener('click',()=>$('details').close());
$('details').addEventListener('click',e=>{if(e.target===$('details'))$('details').close();});
load();

async function loadForum() {
  try {
    const response = await fetch('results/forum.json');
    if (!response.ok) throw Error('No discussion snapshot yet.');
    const data = await response.json();
    $('forumStatus').textContent = `${data.source} · ${data.anime.reduce((n,a)=>n+a.comments,0).toLocaleString()} comments collected · cap ${data.limit_per_anime.toLocaleString()} per anime · VADER predictions`;
    $('forumTitles').innerHTML = data.anime.map(a=>`<tr><td>${escape(a.title)}${a.comments === 0 ? ' · No discussions found in collected sources' : a.comments < 100 ? ' · Small sample' : ''}<br><small>${escape(a.source_status ? Object.entries(a.source_status).map(([k,v])=>`${k}: ${v}`).join(' · ') : 'AniList only')}</small></td><td>${a.comments.toLocaleString()}</td>${['Positive','Neutral','Negative'].map(label=>`<td>${a.comments ? pct(a.counts[label]/a.comments) : '—'}</td>`).join('')}</tr>`).join('');
  } catch(e) { $('forumStatus').textContent = 'Discussion collection is ready to run. No forum results have been published yet.'; }
}
loadForum();
