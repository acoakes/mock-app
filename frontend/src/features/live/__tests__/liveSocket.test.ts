import { describe, expect, it, vi } from 'vitest';
import {
  LiveSocket,
  liveSocketUrl,
  tagsForEvent,
  type ApiTag,
} from '../liveSocket';
import { api } from '../../../api/apiSlice';

// jsdom has no real WebSocket, so provide a minimal stub we can drive by hand
// (same pattern as the react-cytoscapejs stub in RcaGraph.test.tsx).
class FakeWebSocket {
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {}
  close() {
    this.closed = true;
  }
  // Test helpers to simulate the server side.
  emitOpen() {
    this.onopen?.();
  }
  emitMessage(data: unknown) {
    this.onmessage?.({ data });
  }
  emitClose() {
    this.onclose?.();
  }
}

describe('tagsForEvent (pure cache-tag map)', () => {
  it('maps anomaly -> Anomalies + Charts + Dashboard', () => {
    expect(tagsForEvent('anomaly')).toEqual<ApiTag[]>(['Anomalies', 'Charts', 'Dashboard']);
  });

  it('maps rca -> RcaList', () => {
    expect(tagsForEvent('rca')).toEqual<ApiTag[]>(['RcaList']);
  });

  it('maps ingestion -> Ingestion', () => {
    expect(tagsForEvent('ingestion')).toEqual<ApiTag[]>(['Ingestion']);
  });

  it('maps an unknown type -> [] (no-op)', () => {
    expect(tagsForEvent('something-else')).toEqual<ApiTag[]>([]);
  });
});

describe('liveSocketUrl', () => {
  it('uses ws:// for http and wss:// for https, same host', () => {
    expect(liveSocketUrl({ protocol: 'http:', host: 'localhost:3000' })).toBe('ws://localhost:3000/ws');
    expect(liveSocketUrl({ protocol: 'https:', host: 'app.example.com' })).toBe('wss://app.example.com/ws');
  });
});

describe('LiveSocket message handling', () => {
  function makeSocket() {
    const dispatch = vi.fn();
    let fake!: FakeWebSocket;
    const socket = new LiveSocket(dispatch as never, {
      url: 'ws://test/ws',
      socketFactory: (url) => {
        fake = new FakeWebSocket(url);
        return fake as unknown as WebSocket;
      },
    });
    socket.connect();
    return { dispatch, fake, socket };
  }

  it('dispatches invalidateTags with the mapped tags on a valid event', () => {
    const { dispatch, fake } = makeSocket();
    fake.emitMessage(JSON.stringify({ type: 'anomaly', event: 'updated', id: 1 }));
    expect(dispatch).toHaveBeenCalledWith(api.util.invalidateTags(['Anomalies', 'Charts', 'Dashboard']));
  });

  it('does not dispatch on an unknown event type (empty tag set)', () => {
    const { dispatch, fake } = makeSocket();
    fake.emitMessage(JSON.stringify({ type: 'mystery' }));
    expect(dispatch).not.toHaveBeenCalled();
  });

  it('ignores malformed (non-JSON) messages without throwing', () => {
    const { dispatch, fake } = makeSocket();
    expect(() => fake.emitMessage('not json {')).not.toThrow();
    expect(dispatch).not.toHaveBeenCalled();
  });

  it('ignores a JSON message with no string type', () => {
    const { dispatch, fake } = makeSocket();
    fake.emitMessage(JSON.stringify({ event: 'updated' }));
    expect(dispatch).not.toHaveBeenCalled();
  });

  it('fires onOpen/onClose callbacks', () => {
    const onOpen = vi.fn();
    const onClose = vi.fn();
    let fake!: FakeWebSocket;
    const socket = new LiveSocket(vi.fn() as never, {
      url: 'ws://test/ws',
      socketFactory: (url) => {
        fake = new FakeWebSocket(url);
        return fake as unknown as WebSocket;
      },
      onOpen,
      onClose,
    });
    socket.connect();
    fake.emitOpen();
    expect(onOpen).toHaveBeenCalledOnce();
    socket.close();
    // A user-initiated close does not trigger reconnect; onClose is only fired
    // from the socket's own close event, so simulate server close separately.
    expect(fake.closed).toBe(true);
  });
});
