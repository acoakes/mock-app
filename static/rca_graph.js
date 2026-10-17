// Live-mode-only RCA subgraph renderer.
//
// Reads the {nodes, edges} payload inlined by the Flask route in a
// <script type="application/json" id="rca-graph-data"> tag (NO HTTP endpoint)
// and builds a Cytoscape node-link diagram in #rca-graph using the vendored
// cytoscape.min.js (no CDN). The adapter (design §7.3) maps the wire shape to
// Cytoscape elements:
//   node -> { data: { id, ntype, label } }, coloured by ntype
//   edge -> { data: { id: from+'->'+to, source: from, target: to, etype } },
//           labelled by etype
(function () {
  'use strict';

  function parsePayload() {
    var tag = document.getElementById('rca-graph-data');
    if (!tag) {
      return null;
    }
    try {
      return JSON.parse(tag.textContent || tag.innerText || '{}');
    } catch (err) {
      return null;
    }
  }

  // ntype -> node fill colour.
  var NODE_COLOURS = {
    anomaly: '#d9534f',
    root_cause: '#f0ad4e',
    incident: '#5bc0de',
    change: '#5cb85c'
  };

  function toElements(graph) {
    var elements = [];
    (graph.nodes || []).forEach(function (node) {
      elements.push({
        data: {
          id: node.id,
          ntype: node.type,
          label: node.label || node.id
        }
      });
    });
    (graph.edges || []).forEach(function (edge) {
      elements.push({
        data: {
          id: edge.from + '->' + edge.to,
          source: edge.from,
          target: edge.to,
          etype: edge.type
        }
      });
    });
    return elements;
  }

  function render() {
    var container = document.getElementById('rca-graph');
    if (!container || typeof cytoscape === 'undefined') {
      return;
    }
    var graph = parsePayload();
    if (!graph || !(graph.nodes && graph.nodes.length)) {
      return;
    }

    cytoscape({
      container: container,
      elements: toElements(graph),
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'background-color': function (ele) {
              return NODE_COLOURS[ele.data('ntype')] || '#777777';
            },
            'color': '#ffffff',
            'text-outline-color': '#333333',
            'text-outline-width': 2,
            'font-size': 11,
            'text-valign': 'center',
            'text-halign': 'center'
          }
        },
        {
          selector: 'edge',
          style: {
            'label': 'data(etype)',
            'width': 2,
            'line-color': '#999999',
            'target-arrow-color': '#999999',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'font-size': 9,
            'color': '#555555'
          }
        }
      ],
      layout: { name: 'breadthfirst', directed: true, padding: 10 }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
