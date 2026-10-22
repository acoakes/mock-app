import { describe, expect, it } from 'vitest';
import { decidePollingInterval } from '../useLiveQuery';

// The seam's socket-vs-poll decision (design §3). Socket up -> no polling;
// socket down -> fall back to the original demo(no-poll)/live(poll) behaviour.
describe('decidePollingInterval', () => {
  it('returns 0 when the socket is connected (socket drives freshness)', () => {
    expect(decidePollingInterval({ connected: true, mode: 'live', refreshSeconds: 5 })).toBe(0);
    expect(decidePollingInterval({ connected: true, mode: 'demo', refreshSeconds: 5 })).toBe(0);
  });

  it('falls back to polling in live mode when the socket is down', () => {
    expect(decidePollingInterval({ connected: false, mode: 'live', refreshSeconds: 5 })).toBe(5000);
  });

  it('does not poll in demo mode when the socket is down', () => {
    expect(decidePollingInterval({ connected: false, mode: 'demo', refreshSeconds: 5 })).toBe(0);
  });

  it('does not poll in live mode when refresh_seconds is 0', () => {
    expect(decidePollingInterval({ connected: false, mode: 'live', refreshSeconds: 0 })).toBe(0);
  });

  it('does not poll when the mode is unknown (unauthenticated / pre-session)', () => {
    expect(decidePollingInterval({ connected: false, mode: undefined, refreshSeconds: 5 })).toBe(0);
  });
});
