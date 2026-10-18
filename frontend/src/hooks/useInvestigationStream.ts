import { useState, useCallback, useRef, useEffect } from 'react';
import {
  InvestigateRequest,
  AgentThoughtPayload,
  ToolCallPayload,
  GraphEvidencePayload,
  ImpactReport,
} from '../types/api';

export interface SSEParsedEvent {
  event: string;
  data: string;
}

export function parseSSEBuffer(buffer: string): { events: SSEParsedEvent[]; remaining: string } {
  const normalized = buffer.replace(/\r\n/g, '\n');
  const rawEvents = normalized.split('\n\n');
  const remaining = rawEvents.pop() ?? '';
  const events: SSEParsedEvent[] = [];

  for (const block of rawEvents) {
    if (!block.trim()) continue;
    let eventName = 'message';
    const dataLines: string[] = [];

    const lines = block.split('\n');
    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim());
      }
    }

    if (dataLines.length > 0) {
      events.push({ event: eventName, data: dataLines.join('\n') });
    }
  }

  return { events, remaining };
}

export type InvestigationStatus = 'idle' | 'streaming' | 'completed' | 'error';

export function useInvestigationStream() {
  const [status, setStatus] = useState<InvestigationStatus>('idle');
  const [thoughts, setThoughts] = useState<AgentThoughtPayload[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCallPayload[]>([]);
  const [graphEvidence, setGraphEvidence] = useState<GraphEvidencePayload | null>(null);
  const [report, setReport] = useState<ImpactReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<string[] | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortControllerRef.current?.abort(), []);

  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStatus('idle');
    setThoughts([]);
    setToolCalls([]);
    setGraphEvidence(null);
    setReport(null);
    setError(null);
    setCandidates(null);
  }, []);

  const startInvestigation = useCallback(async (request: InvestigateRequest) => {
    reset();
    setStatus('streaming');

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch('/api/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (abortControllerRef.current !== controller) return;
      if (!response.ok) {
        const errJson = await response.json().catch(() => ({ detail: response.statusText }));
        setStatus('error');
        setError(errJson.detail || `Server responded with ${response.status}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        setStatus('error');
        setError('Response body is not a readable stream');
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (abortControllerRef.current !== controller) return;
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const { events, remaining } = parseSSEBuffer(buffer);
        buffer = remaining;

        for (const ev of events) {
          try {
            const parsedData = JSON.parse(ev.data);
            switch (ev.event) {
              case 'agent_thought':
                setThoughts((prev) => [...prev, parsedData]);
                break;
              case 'tool_call':
                setToolCalls((prev) => [...prev, parsedData]);
                break;
              case 'graph_evidence':
                setGraphEvidence(parsedData);
                break;
              case 'report_complete':
                setReport(parsedData);
                setStatus('completed');
                break;
              case 'error':
                setStatus('error');
                setError(parsedData.message || 'Investigation error');
                if (parsedData.candidates) {
                  setCandidates(parsedData.candidates);
                }
                break;
            }
          } catch (e) {
            console.error('Error parsing SSE event data:', e, ev.data);
          }
        }
      }

      if (buffer.trim()) {
        const { events } = parseSSEBuffer(buffer + '\n\n');
        for (const ev of events) {
          try {
            const parsedData = JSON.parse(ev.data);
            if (ev.event === 'report_complete') {
              setReport(parsedData);
              setStatus('completed');
            }
          } catch (e) {
            // ignore trailing parse
          }
        }
      }
    } catch (err: unknown) {
      if (abortControllerRef.current !== controller) return;
      if ((err as Error)?.name === 'AbortError') {
        setStatus('idle');
        return;
      }
      setStatus('error');
      setError(err instanceof TypeError ? 'Cannot reach the GraphScope API. Check that the local server is running and reopen its URL (normally http://127.0.0.1:8080).' : (err as Error)?.message || 'An unexpected error occurred during investigation.');
    }
  }, [reset]);

  return {
    status,
    thoughts,
    toolCalls,
    graphEvidence,
    report,
    error,
    candidates,
    startInvestigation,
    reset,
  };
}
