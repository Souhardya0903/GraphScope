import { describe, it, expect } from 'vitest';
import { parseSSEBuffer } from '../hooks/useInvestigationStream';

describe('parseSSEBuffer', () => {
  it('parses multiple SSE events across buffer chunks', () => {
    const raw = 'event: agent_thought\ndata: {"step":"resolve_symbol","detail":"Resolving target"}\n\n';
    const { events, remaining } = parseSSEBuffer(raw);
    expect(events.length).toBe(1);
    expect(events[0].event).toBe('agent_thought');
    expect(JSON.parse(events[0].data).step).toBe('resolve_symbol');
    expect(remaining).toBe('');
  });

  it('preserves incomplete trailing chunks in remaining buffer', () => {
    const incomplete = 'event: agent_thought\ndata: {"step":"resolve_sym';
    const { events, remaining } = parseSSEBuffer(incomplete);
    expect(events.length).toBe(0);
    expect(remaining).toBe(incomplete);
  });

  it('handles multiple events in single buffer and CRLF line endings', () => {
    const multi = 'event: agent_thought\r\ndata: {"step":"step1"}\r\n\r\nevent: tool_call\r\ndata: {"tool":"trace_callers"}\r\n\r\n';
    const { events, remaining } = parseSSEBuffer(multi);
    expect(events.length).toBe(2);
    expect(events[0].event).toBe('agent_thought');
    expect(events[1].event).toBe('tool_call');
    expect(remaining).toBe('');
  });
});
