import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { NODE_COLOURS, RcaGraph, toCyElements, type CyElement } from '../RcaGraph';
import type { GraphResponse } from '../../api/apiSlice';

// Stub react-cytoscapejs so the populated-render branch can be asserted without
// mounting a real (canvas-heavy) Cytoscape instance in jsdom. The stub forwards
// the data-testid passthrough prop so `rca-graph` is reachable.
vi.mock('react-cytoscapejs', () => ({
  default: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid']}>cytoscape</div>
  ),
}));

describe('toCyElements (pure adapter)', () => {
  it('maps a populated payload to node-then-edge elements with the exact shapes', () => {
    const graph: GraphResponse = {
      nodes: [
        { id: 'a1', type: 'anomaly', label: 'Anomaly 1' },
        // label falls back to id when empty
        { id: 'rc1', type: 'root_cause', label: '' },
      ],
      edges: [{ from: 'a1', to: 'rc1', type: 'caused_by' }],
    };

    const elements = toCyElements(graph);

    expect(elements).toEqual<CyElement[]>([
      { data: { id: 'a1', ntype: 'anomaly', label: 'Anomaly 1' } },
      { data: { id: 'rc1', ntype: 'root_cause', label: 'rc1' } },
      { data: { id: 'a1->rc1', source: 'a1', target: 'rc1', etype: 'caused_by' } },
    ]);

    // colour is applied by the stylesheet, NOT carried in element data
    expect(elements[0].data).not.toHaveProperty('colour');
  });

  it('returns an empty array for an empty payload', () => {
    expect(toCyElements({ nodes: [], edges: [] })).toEqual([]);
  });
});

describe('NODE_COLOURS (ported colour map)', () => {
  it('resolves each ntype to its verbatim hex', () => {
    expect(NODE_COLOURS).toEqual({
      anomaly: '#d9534f',
      root_cause: '#f0ad4e',
      incident: '#5bc0de',
      change: '#5cb85c',
    });
  });
});

const renderGraph = (ui: ReactNode) => render(ui);

describe('RcaGraph render states', () => {
  it('renders rca-graph inside the panel for a non-empty graph', () => {
    renderGraph(
      <RcaGraph
        data={{ nodes: [{ id: 'a1', type: 'anomaly', label: 'Anomaly 1' }], edges: [] }}
      />,
    );
    expect(screen.getByTestId('rca-graph-panel')).toBeInTheDocument();
    expect(screen.getByTestId('rca-graph')).toBeInTheDocument();
    expect(screen.queryByTestId('rca-graph-unavailable')).not.toBeInTheDocument();
  });

  it('renders rca-graph-unavailable inside the panel for an empty graph', () => {
    renderGraph(<RcaGraph data={{ nodes: [], edges: [] }} />);
    expect(screen.getByTestId('rca-graph-panel')).toBeInTheDocument();
    expect(screen.getByTestId('rca-graph-unavailable')).toBeInTheDocument();
    expect(screen.queryByTestId('rca-graph')).not.toBeInTheDocument();
  });

  it('renders rca-graph-unavailable while loading', () => {
    renderGraph(<RcaGraph isLoading />);
    expect(screen.getByTestId('rca-graph-panel')).toBeInTheDocument();
    expect(screen.getByTestId('rca-graph-unavailable')).toBeInTheDocument();
  });

  it('renders rca-graph-unavailable on error', () => {
    renderGraph(<RcaGraph isError />);
    expect(screen.getByTestId('rca-graph-panel')).toBeInTheDocument();
    expect(screen.getByTestId('rca-graph-unavailable')).toBeInTheDocument();
  });
});
