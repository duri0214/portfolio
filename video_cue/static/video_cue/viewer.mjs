import {timecode, eventAt, adjacentEvent} from './playback.mjs';

const data = JSON.parse(document.getElementById('cue-data').textContent);
const video = document.getElementById('cue-video');
const byId = id => document.getElementById(id);
const buttons = [...document.querySelectorAll('.event-button')];
let pendingSeek = null;
let pendingPlay = false;
let markers = [];

function showError(message) {
    byId('playback-error').textContent = message;
    byId('playback-error').hidden = false;
}

async function play() {
    try { await video.play(); }
    catch { showError('再生を開始できませんでした。再生ボタンを押すか、動画の形式・接続を確認してください。'); }
}

function load(position = 0, resume = false) {
    byId('playback-error').hidden = true;
    byId('mode-label').textContent = 'HIGHLIGHT / ハイライト';
    byId('position-label').textContent = 'ハイライト内の位置';
    if (video.getAttribute('src') !== data.highlight_url) {
        pendingSeek = position;
        pendingPlay = resume;
        video.src = data.highlight_url;
        byId('toggle-play').disabled = true;
        byId('seek').disabled = true;
        video.load();
    } else {
        if (video.readyState >= 1) video.currentTime = position;
        else pendingSeek = position;
        if (resume) play();
    }
    update();
}

function selectEvent(index) {
    const event = data.events[index];
    if (event && data.highlight_url) load(event.highlight_start, !video.paused);
}

function adjacent(direction) {
    const index = adjacentEvent(data.events, video.currentTime, direction);
    return index >= 0 && index < data.events.length ? index : -1;
}

function drawTimeline() {
    const timeline = byId('timeline');
    timeline.replaceChildren();
    markers = [];
    if (!Number.isFinite(video.duration)) return;
    data.events.forEach((event, index) => {
        const marker = document.createElement('button');
        marker.type = 'button';
        marker.className = 'cue-marker';
        marker.textContent = index + 1;
        marker.setAttribute('aria-label', `イベント ${index + 1} へ移動`);
        marker.style.left = `${Math.min(100, Math.max(0, event.highlight_start / video.duration * 100))}%`;
        marker.addEventListener('click', () => selectEvent(index));
        timeline.append(marker);
        markers.push(marker);
    });
}

function update() {
    const active = eventAt(data.events, video.currentTime);
    byId('position').textContent = timecode(video.currentTime);
    byId('seek').value = video.currentTime;
    byId('current-event').textContent = active >= 0 ? `${String(active + 1).padStart(2, '0')} / ${data.events.length}` : '区間外';
    const event = data.events[active];
    byId('source-time').textContent = event
        ? timecode(event.start + video.currentTime - event.highlight_start)
        : '区間外';
    buttons.forEach((button, index) => {
        button.classList.toggle('active', index === active);
        button.setAttribute('aria-current', String(index === active));
    });
    markers.forEach((marker, index) => marker.setAttribute('aria-current', String(index === active)));
    byId('previous-event').disabled = !data.highlight_url || adjacent(-1) < 0;
    byId('next-event').disabled = !data.highlight_url || adjacent(1) < 0;
}

buttons.forEach((button, index) => button.addEventListener('click', () => selectEvent(index)));
document.querySelectorAll('.event-times').forEach(element => {
    element.textContent = `${timecode(Number(element.dataset.start))} → ${timecode(Number(element.dataset.end))}`;
});
byId('toggle-play').addEventListener('click', () => video.paused ? play() : video.pause());
byId('previous-event').addEventListener('click', () => selectEvent(adjacent(-1)));
byId('next-event').addEventListener('click', () => selectEvent(adjacent(1)));
byId('seek').addEventListener('input', event => { video.currentTime = Number(event.target.value); });
byId('playback-rate').addEventListener('change', event => { video.playbackRate = Number(event.target.value); });
video.addEventListener('loadedmetadata', () => {
    if (pendingSeek !== null) { video.currentTime = Math.min(pendingSeek, video.duration); pendingSeek = null; }
    video.playbackRate = Number(byId('playback-rate').value);
    byId('toggle-play').disabled = false;
    byId('playback-rate').disabled = false;
    byId('seek').disabled = !Number.isFinite(video.duration);
    byId('seek').max = video.duration || 1;
    drawTimeline();
    update();
    if (pendingPlay) { pendingPlay = false; play(); }
});
video.addEventListener('timeupdate', update);
video.addEventListener('play', () => { byId('toggle-play').textContent = 'Ⅱ 一時停止'; });
video.addEventListener('pause', () => { byId('toggle-play').textContent = '▶ 再生'; });
video.addEventListener('error', () => {
    byId('toggle-play').disabled = true;
    byId('seek').disabled = true;
    showError('動画を読み込めません。ファイルの存在・アクセス権・再生形式を確認してください。');
});
if (data.highlight_url) load();
else {
    byId('mode-label').textContent = '再生可能なハイライトがありません';
    showError(data.events.length ? 'ハイライト動画が見つかりません。保存済み成果物を確認してください。' : '動き区間がないため、ハイライト動画はありません。');
}
