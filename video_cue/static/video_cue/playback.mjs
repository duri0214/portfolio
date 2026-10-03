export function timecode(seconds) {
    if (!Number.isFinite(seconds)) return '—';
    const tenths = Math.floor(Math.max(0, seconds) * 10 + 1e-6);
    const hours = Math.floor(tenths / 36000);
    const minutes = Math.floor(tenths / 600) % 60;
    const rest = Math.floor(tenths / 10) % 60;
    return `${hours ? `${String(hours).padStart(2, '0')}:` : ''}${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}.${tenths % 10}`;
}

export function eventAt(events, seconds) {
    return events.findIndex(event => {
        const start = event.highlight_start;
        return start !== null && seconds >= start && seconds < start + event.duration;
    });
}

export function adjacentEvent(events, seconds, direction) {
    if (direction > 0) {
        return events.findIndex(event => event.highlight_start > seconds + 0.05);
    }
    for (let i = events.length - 1; i >= 0; i--) {
        const start = events[i].highlight_start;
        if (start !== null && start < seconds - 0.05) return i;
    }
    return -1;
}
