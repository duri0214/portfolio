import test from 'node:test';
import assert from 'node:assert/strict';
import {timecode, eventAt, adjacentEvent} from '../static/video_cue/playback.mjs';

const events = [
    {start: 1.8, end: 4, duration: 2.2, highlight_start: 1},
    {start: 6, end: 7.6, duration: 1.6, highlight_start: 5.2},
    {start: 10, end: 11.6, duration: 1.6, highlight_start: 8.8},
];
test('ハイライトの余白をイベントと誤認しない', () => {
    assert.equal(eventAt(events, 0.9), -1);
    assert.equal(eventAt(events, 1), 0);
    assert.equal(eventAt(events, 3.3), -1);
    assert.equal(eventAt(events, 5.2), 1);
});
test('前後イベントへの移動は余白や末尾、空結果でも境界を守る', () => {
    assert.equal(adjacentEvent(events, 1, 1), 1);
    assert.equal(adjacentEvent(events, 5.2, -1), 0);
    assert.equal(adjacentEvent(events, 4.5, 1), 1);
    assert.equal(adjacentEvent(events, 10.5, 1), -1);
    assert.equal(adjacentEvent(events, 0, -1), -1);
    assert.equal(adjacentEvent([], 0, 1), -1);
});
test('時間・分の繰り上がりと未確定時刻を表示する', () => {
    assert.equal(timecode(6.2), '00:06.2');
    assert.equal(timecode(60), '01:00.0');
    assert.equal(timecode(3601.1), '01:00:01.1');
    assert.equal(timecode(NaN), '—');
});
