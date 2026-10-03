import {timecode, eventAt, adjacentEvent} from './playback.mjs';

const data = JSON.parse(document.getElementById('cue-data').textContent);
const video = document.getElementById('cue-video');
const byId = id => document.getElementById(id);
const buttons = [...document.querySelectorAll('.event-button')];
let mode = data.highlight_url ? 'highlight' : data.source_url ? 'source' : 'clip';
let selected = -1;
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

function load(url, nextMode, position = 0, resume = false) {
    mode = nextMode;
    byId('playback-error').hidden = true;
    byId('mode-label').textContent = {highlight: 'HIGHLIGHT / ハイライト', source: 'ORIGINAL / 元動画', clip: 'CLIP / 個別クリップ'}[mode];
    byId('position-label').textContent = {highlight: 'ハイライト内の位置', source: '元動画の再生位置', clip: 'クリップ内の位置'}[mode];
    if (video.getAttribute('src') !== url) {
        pendingSeek = position;
        pendingPlay = resume;
        video.src = url;
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

function selectEvent(index, requestedMode = mode) {
    const event = data.events[index];
    if (!event) return;
    const resume = !video.paused;
    selected = index;
    if (requestedMode === 'highlight' && data.highlight_url) load(data.highlight_url, 'highlight', event.highlight_start, resume);
    else if (requestedMode === 'source' && data.source_url) load(data.source_url, 'source', event.start, resume);
    else if (event.clip_url) load(event.clip_url, 'clip', 0, resume);
    else showError('このイベントの動画が見つかりません。動画の配置を確認してください。');
}

function adjacent(direction) {
    let index = adjacentEvent(data.events, mode, video.currentTime, direction, selected);
    if (mode === 'clip') {
        while (index >= 0 && index < data.events.length && !data.events[index].clip_url) index += direction;
    }
    return index >= 0 && index < data.events.length ? index : -1;
}

function drawTimeline() {
    const timeline = byId('timeline');
    timeline.replaceChildren();
    markers = [];
    if (mode !== 'clip' && !Number.isFinite(video.duration)) return;
    data.events.forEach((event, index) => {
        const marker = document.createElement('button');
        marker.type = 'button';
        marker.className = 'cue-marker';
        marker.textContent = index + 1;
        marker.setAttribute('aria-label', `イベント ${index + 1} へ移動`);
        const start = mode === 'highlight' ? event.highlight_start : event.start;
        const percent = mode === 'clip' ? (index + .5) / data.events.length * 100 : start / video.duration * 100;
        marker.style.left = `${Math.min(100, Math.max(0, percent))}%`;
        marker.disabled = mode === 'clip' && !event.clip_url;
        marker.addEventListener('click', () => selectEvent(index));
        timeline.append(marker);
        markers.push(marker);
    });
    byId('timeline-note').textContent = mode === 'clip' ? '個別クリップの順番です。番号を選ぶと切り替わります。' : '番号はイベントの開始位置です。選択すると頭出しします。';
}

function update() {
    const active = mode === 'clip' ? selected : eventAt(data.events, mode, video.currentTime);
    if (active >= 0) selected = active;
    byId('position').textContent = timecode(video.currentTime);
    byId('seek').value = video.currentTime;
    byId('current-event').textContent = active >= 0 ? `${String(active + 1).padStart(2, '0')} / ${data.events.length}` : '区間外';
    let original = mode === 'source' ? timecode(video.currentTime) : '区間外';
    if (mode === 'highlight' && active >= 0) {
        const event = data.events[active];
        original = timecode(event.start + video.currentTime - event.highlight_start);
    } else if (mode === 'clip' && selected >= 0) original = '対応時刻なし';
    byId('source-time').textContent = original;
    buttons.forEach((button, index) => {
        button.classList.toggle('active', index === active);
        button.setAttribute('aria-current', String(index === active));
    });
    markers.forEach((marker, index) => marker.setAttribute('aria-current', String(index === active)));
    byId('previous-event').disabled = adjacent(-1) < 0;
    byId('next-event').disabled = adjacent(1) < 0;
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
byId('show-highlight').addEventListener('click', () => selected >= 0 ? selectEvent(selected, 'highlight') : load(data.highlight_url, 'highlight'));
byId('show-source').addEventListener('click', () => selected >= 0 ? selectEvent(selected, 'source') : load(data.source_url, 'source'));
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
if (data.highlight_url) load(data.highlight_url, 'highlight');
else if (data.source_url) load(data.source_url, 'source');
else {
    const first = data.events.findIndex(event => event.clip_url);
    if (first >= 0) selectEvent(first);
    else {
        byId('mode-label').textContent = '再生可能な動画がありません';
        showError(data.events.length ? '動画が見つかりません。出力ファイルの配置を確認してください。' : '動き区間がないため、ハイライト動画はありません。');
    }
}
