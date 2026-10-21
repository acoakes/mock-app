import CytoscapeComponent from 'react-cytoscapejs';
import type { ElementDefinition, NodeSingular, Stylesheet } from 'cytoscape';
import type { GraphResponse, GraphNode, GraphEdge } from '../api/apiSlice';
import { TESTIDS } from '../testids';

export interface RcaGraphProps {
  data?: GraphResponse;
  isLoading?: boolean;
  isError?: boolean;
}

// ntype -> node fill colour. Ported verbatim from static/rca_graph.js.
export const NODE_COLOURS: Record<string, string> = {
  anomaly: '#d9534f',
  root_cause: '#f0ad4e',
  incident: '#5bc0de',
  change: '#5cb85c',
};

export interface CyElement {
  data: Record<string, unknown>;
}

// Pure wire -> Cytoscape elements adapter, ported verbatim from the vanilla
// `toElements` in static/rca_graph.js:
//   node -> { data: { id, ntype: node.type, label: node.label || node.id } }
//   edge -> { data: { id: `${from}->${to}`, source: from, target: to, etype } }
// Colour is applied by the stylesheet (NODE_COLOURS), NOT carried in element
// data, matching the vanilla renderer. Edge direction is read natively from
// from/to and never re-derived.
export function toCyElements(graph: GraphResponse): CyElement[] {
  const nodes: CyElement[] = graph.nodes.map((n: GraphNode) => ({
    data: {
      id: n.id,
      ntype: n.type,
      label: n.label || n.id,
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

// Cytoscape stylesheet, ported verbatim from static/rca_graph.js. node fill is
// resolved from NODE_COLOURS by ntype (fallback #777777); edges are labelled by
// etype with a directed triangle arrow.
const STYLESHEET: Stylesheet[] = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'background-color': (ele: NodeSingular) =>
        NODE_COLOURS[ele.data('ntype') as string] || '#777777',
      color: '#ffffff',
      'text-outline-color': '#333333',
      'text-outline-width': 2,
      'font-size': 11,
      'text-valign': 'center',
      'text-halign': 'center',
    },
  },
  {
    selector: 'edge',
    style: {
      label: 'data(etype)',
      width: 2,
      'line-color': '#999999',
      'target-arrow-color': '#999999',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'font-size': 9,
      color: '#555555',
    },
  },
] as unknown as Stylesheet[];

const LAYOUT = { name: 'breadthfirst', directed: true, padding: 10 };

const CONTAINER_STYLE = { width: '100%', height: '400px' };

// Real react-cytoscapejs render (design §5). Fed by the already-fetched
// useGetRcaGraphQuery(id) result, passed in as props from RcaDetailPage.
//
// Render-state contract (§5/§7), the rca-graph-panel wrapper is present in ALL
// states and the component never throws:
//   - loading / errored / empty graph ({nodes:[]}) -> rca-graph-unavailable
//   - non-empty graph (nodes.length > 0)          -> rca-graph canvas
export function RcaGraph({ data, isLoading, isError }: RcaGraphProps) {
  const hasNodes = !isLoading && !isError && (data?.nodes?.length ?? 0) > 0;

  return (
    <div data-testid={TESTIDS.rcaGraphPanel} className="detail-panel">
      <h3>RCA Subgraph</h3>
      {hasNodes ? (
        <CytoscapeComponent
          data-testid={TESTIDS.rcaGraph}
          id="rca-graph"
          className="rca-graph"
          elements={toCyElements(data!) as unknown as ElementDefinition[]}
          stylesheet={STYLESHEET}
          layout={LAYOUT}
          style={CONTAINER_STYLE}
        />
      ) : (
        <p data-testid={TESTIDS.rcaGraphUnavailable}>Graph unavailable.</p>
      )}
    </div>
  );
}
