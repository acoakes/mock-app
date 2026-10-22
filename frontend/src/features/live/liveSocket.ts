// WebSocket live-push client (design §3 / §9 step 5, the [LATER] slice).
//
// This is the socket side of the live-refresh seam. It opens a connection to
// the Flask `/ws` endpoint, parses each pushed envelope, and dispatches
// `api.util.invalidateTags([...])` so RTK Query refetches exactly the queries
// whose data went stale. Redux is the push sink (per the design's fixed
// decision), so components/endpoints never change — only `useLivePolling`
// decides whether freshness comes from this socket or from polling.
//
// Envelope shape (emitted by ws.py): { type, event, id? }. The frontend keys
// off `type` to pick tags; `event`/`id` are advisory.

import { api } from '../../api/apiSlice';
import type { AppDispatch } from '../../store';

// The tag types RTK Query knows about (mirrors apiSlice `tagTypes`). We only
// ever invalidate a subset from pushed events.
export type ApiTag =
  | 'Dashboard'
  | 'Charts'
  | 'Anomalies'
  | 'RcaList'
  | 'Ingestion';

/** Event `type` -> RTK Query tags to invalidate (design §3 cache-tag map).
 *
 * - anomaly  -> Anomalies + Charts + Dashboard (mirrors `acknowledgeAnomaly`)
 * - rca      -> RcaList
 * - ingestion-> Ingestion
 * An unknown type maps to [] (no-op), so a future/garbled event is harmless.
 */
export function tagsForEvent(type: string): ApiTag[] {
  switch (type) {
    case 'anomaly':
      return ['Anomalies', 'Charts', 'Dashboard'];
    case 'rca':
      return ['RcaList'];
    case 'ingestion':
      return ['Ingestion'];
    default:
      return [];
  }
}

/** The minimal push envelope the backend emits. */
export interface LiveEvent {
  type: string;
  event?: string;
  id?: number;
}

function isLiveEvent(value: unknown): value is LiveEvent {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as { type?: unknown }).type === 'string'
  );
}

/** Build the single-origin `/ws` URL (ws/wss) from the current location so the
 * Vite dev proxy (and the Flask-served build) both resolve it. */
export function liveSocketUrl(loc: Pick<Location, 'protocol' | 'host'> = window.location): string {
  const scheme = loc.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${loc.host}/ws`;
}

export interface LiveSocketOptions {
  /** Override the URL (tests). Defaults to `liveSocketUrl()`. */
  url?: string;
  /** Injectable WebSocket ctor (tests / SSR). Defaults to global WebSocket. */
  socketFactory?: (url: string) => WebSocket;
  /** Fired on open/close so the seam can track connected-state. */
  onOpen?: () => void;
  onClose?: () => void;
  /** Base/max reconnect backoff in ms (capped exponential). */
  baseBackoffMs?: number;
  maxBackoffMs?: number;
}

/** Owns one WebSocket to `/ws` with reconnect/backoff, dispatching
 * `invalidateTags` on each valid pushed event. */
export class LiveSocket {
  private readonly dispatch: AppDispatch;
  private readonly url: string;
  private readonly socketFactory: (url: string) => WebSocket;
  private readonly onOpen?: () => void;
  private readonly onClose?: () => void;
  private readonly baseBackoffMs: number;
  private readonly maxBackoffMs: number;

  private ws: WebSocket | null = null;
  private closedByUser = false;
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(dispatch: AppDispatch, options: LiveSocketOptions = {}) {
    this.dispatch = dispatch;
    this.url = options.url ?? liveSocketUrl();
    this.socketFactory = options.socketFactory ?? ((u) => new WebSocket(u));
    this.onOpen = options.onOpen;
    this.onClose = options.onClose;
    this.baseBackoffMs = options.baseBackoffMs ?? 1000;
    this.maxBackoffMs = options.maxBackoffMs ?? 15000;
  }

  /** Open the connection (idempotent while already open/connecting). */
  connect(): void {
    this.closedByUser = false;
    if (this.ws) {
      return;
    }
    const ws = this.socketFactory(this.url);
    this.ws = ws;

    ws.onopen = () => {
      this.attempt = 0;
      this.onOpen?.();
    };
    ws.onmessage = (ev: MessageEvent) => {
      this.handleMessage(ev.data);
    };
    ws.onclose = () => {
      this.ws = null;
      this.onClose?.();
      if (!this.closedByUser) {
        this.scheduleReconnect();
      }
    };
    // On error, let the subsequent close event drive reconnect.
    ws.onerror = () => {
      /* no-op: close handler owns reconnect */
    };
  }

  /** Close for good; no reconnect. */
  close(): void {
    this.closedByUser = true;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
  }

  private handleMessage(data: unknown): void {
    if (typeof data !== 'string') {
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(data);
    } catch {
      return;
    }
    if (!isLiveEvent(parsed)) {
      return;
    }
    const tags = tagsForEvent(parsed.type);
    if (tags.length > 0) {
      this.dispatch(api.util.invalidateTags(tags));
    }
  }

  private scheduleReconnect(): void {
    const delay = Math.min(this.baseBackoffMs * 2 ** this.attempt, this.maxBackoffMs);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.closedByUser) {
        this.connect();
      }
    }, delay);
  }
}

/** Convenience factory used by the seam. */
export function createLiveSocket(dispatch: AppDispatch, options: LiveSocketOptions = {}): LiveSocket {
  return new LiveSocket(dispatch, options);
}
