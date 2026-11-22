import {bindSheet} from './cells.js';
bindSheet(document.querySelector('#frames'), document.querySelector('#focused-cell'));
const notice = document.querySelector('#notice');
const reel = document.querySelector('#reel');
reel.addEventListener('change', () => location.assign(`/sheet/${document.body.dataset.sheet}?sample=${reel.value}`));
async function send(button, payload, id) {
  button.disabled = true;
  notice.textContent = '正在校对…';
  try {
    const response = await fetch(id ? `/api/runs/${id}/repeat` : '/api/runs', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.message);
    notice.textContent = result.reused ? '复算一致' : '交付已归档';
    if (!id) location.assign(`/sheet/runs?${new URLSearchParams({run:result.id,sample:reel.value})}`);
  } catch (error) {
    notice.textContent = error.message || '提交失败，请重试';
  } finally { button.disabled = false; }
}
document.querySelector('#sample-form').addEventListener('submit', event => {
  event.preventDefault();
  send(event.submitter, {sample:reel.value});
});
document.querySelector('#originals')?.addEventListener('submit', event => {
  event.preventDefault();
  send(event.submitter, Object.fromEntries(new FormData(event.currentTarget)));
});
document.querySelector('#repeat')?.addEventListener('click', event => send(event.currentTarget, null, event.currentTarget.dataset.id));

const finalizeForm = document.querySelector('#finalize-form');
finalizeForm?.addEventListener('submit', async event => {
  event.preventDefault();
  const run = finalizeForm.dataset.run;
  const decisions = [...finalizeForm.querySelectorAll('fieldset')].map(fieldset => {
    const picked = fieldset.querySelector('input:checked');
    return picked ? {track: fieldset.dataset.track, cue_id: fieldset.dataset.cue, line: Number(picked.value)} : null;
  }).filter(Boolean);
  if (!decisions.length) { notice.textContent = '先为每个待选组选定原行'; return; }
  const button = finalizeForm.querySelector('button');
  button.disabled = true;
  notice.textContent = '正在复算定稿…';
  try {
    const response = await fetch(`/api/delivery/${run}/finalize`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({decisions})
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.message);
    notice.textContent = result.reused ? '定稿未变化，沿用既有档' : '定稿已复算并签发新档';
    location.assign(`/sheet/delivery?run=${result.id}`);
  } catch (error) {
    notice.textContent = error.message || '定稿提交失败';
  } finally { button.disabled = false; }
});
