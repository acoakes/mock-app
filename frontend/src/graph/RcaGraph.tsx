import type { GraphResponse, GraphNode, GraphEdge } from '../api/apiSlice';
import { TESTIDS } from '../testids';

export interface RcaGraphProps {
  data?: GraphResponse;
  isLoading?: boolean;
  isError?: boolean;
}

// Pure wire -> Cytoscape elements adapter (ported shape from rca_graph.js). It
// is typed and exported now for the STEP 3 port, but is NOT invoked for
// rendering this step — the placeholder below only renders the panel + the
// unavailable state. Keeping the adapter here makes step 3 a component-only
// change.
export interface CyElement {
  data: Record<string, unknown>;
}

const NODE_COLOURS: Record<string, string> = {
  anomaly: '#d9534f',
  root_cause: '#f0ad4e',
  incident: '#5bc0de',
  change: '#5cb85c',
};

export function toCyElements(graph: GraphResponse): CyElement[] {
  const nodes: CyElement[] = graph.nodes.map((n: GraphNode) => ({
    data: {
      id: n.id,
      ntype: n.type,
      label: n.label || n.id,
      colour: NODE_COLOURS[n.type],
    },
  }));
  const edges: CyElement[] = graph.edges.map((e: GraphEdge) => ({
    data: {
      id: `${e.from}->${e.to}`,
      source: e.from,
      target: e.to,
      etype: e.type,
    },
  }));
  return [...nodes, ...edges];
}

// DEFERRED PLACEHOLDER (design §9 step 3). Renders the rca-graph-panel and, for
// now, always the rca-graph-unavailable state. The real react-cytoscapejs
// rendering + useGetRcaGraphQuery wiring is STEP 3. cytoscape deps are already
// installed so step 3 only writes this component's body.
export function RcaGraph({ data }: RcaGraphProps) {
  const hasNodes = (data?.nodes?.length ?? 0) > 0;

  return (
    <div data-testid={TESTIDS.rcaGraphPanel} className="detail-panel">
      <h3>RCA Subgraph</h3>
      {hasNodes ? (
        // Placeholder container for the future Cytoscape canvas (not wired yet).
        <div data-testid={TESTIDS.rcaGraph} id="rca-graph" className="rca-graph" />
      ) : (
        <p data-testid={TESTIDS.rcaGraphUnavailable}>Graph unavailable.</p>
      )}
    </div>
  );
}
