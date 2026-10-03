export function timecode(seconds) {
    if (!Number.isFinite(seconds)) return '—';
    const tenths = Math.floor(Math.max(0, seconds) * 10 + 1e-6);
    const hours = Math.floor(tenths / 36000);
    const minutes = Math.floor(tenths / 600) % 60;
    const rest = Math.floor(tenths / 10) % 60;
    return `${hours ? `${String(hours).padStart(2, '0')}:` : ''}${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}.${tenths % 10}`;
}

export function eventAt(events, mode, seconds) {
    if (mode === 'clip') return -1;
    return events.findIndex(event => {
        const start = mode === 'highlight' ? event.highlight_start : event.start;
        return start !== null && seconds >= start && seconds < start + event.duration;
    });
}

export function adjacentEvent(events, mode, seconds, direction, selected = -1) {
    if (mode === 'clip') return selected + direction;
    if (direction > 0) {
        return events.findIndex(event => (mode === 'highlight' ? event.highlight_start : event.start) > seconds + 0.05);
    }
    for (let i = events.length - 1; i >= 0; i--) {
        const start = mode === 'highlight' ? events[i].highlight_start : events[i].start;
        if (start !== null && start < seconds - 0.05) return i;
    }
    return -1;
}
