"""Thin gremlinpython read client for the live-mode RCA subgraph visual.

This is a self-contained reader that mirrors FEAT-001's documented ``{nodes, edges}``
wire contract (aws-lab ``rca.graph_queries.get_rca_chain`` / ``rca.write_neptune_stub``).
It deliberately re-implements the ~15 lines of traversal here rather than importing lab
Python: mock-app and aws-lab are separate repos that share only the wire contract and the
``gid``/``GREMLIN_URL`` scheme, not code.

Read contract (single source = aws-lab write_neptune_stub.build_graph):
    node:  gid -> id, ntype -> type, label -> label, remaining scalar props -> props.*
    edge:  label(=etype) -> type, out-vertex gid -> from, in-vertex gid -> to, props -> {}

Edge direction is read NATIVELY and never re-derived: ``caused_by`` is reached from the
anomaly via ``.out('caused_by')`` (anomaly -> root_cause); ``correlates_with`` is reached
via ``.in_('correlates_with')`` (incident/change -> anomaly).

``gremlin_python`` is imported inside the connect path so a module-level ``import
rca_graph_client`` stays dependency-light. If Gremlin is unreachable the functions raise a
ConnectionError; the data_source caller catches it and fails safe to the placeholder.
"""

import os

GREMLIN_URL = os.environ.get("GREMLIN_URL", "ws://localhost:8182/gremlin")

# Scalar vertex properties that are structural, not part of the {props} bag.
_RESERVED_VPROPS = {"gid", "ntype", "label"}


def _connect():
    """Open a Gremlin remote connection. Raises ConnectionError if unreachable."""
    try:
        from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
    except ImportError as exc:
        raise ConnectionError("gremlin_python not importable: %s" % exc)
    try:
        return DriverRemoteConnection(GREMLIN_URL, "g")
    except Exception as exc:
        raise ConnectionError("cannot reach Gremlin at %s: %s" % (GREMLIN_URL, exc))


def _traversal(connection):
    from gremlin_python.process.anonymous_traversal import traversal

    return traversal().with_remote(connection)


def _close(connection):
    try:
        connection.close()
    except Exception:  # pragma: no cover - best-effort close
        pass


def _vertex_to_node(vmap):
    """Map a Gremlin elementMap (vertex) to a build_graph-shaped node dict."""
    props = {}
    for key, value in vmap.items():
        # elementMap keys include T.id / T.label (non-str) and property names (str).
        if not isinstance(key, str):
            continue
        if key in _RESERVED_VPROPS:
            continue
        props[key] = value
    return {
        "id": vmap.get("gid"),
        "type": vmap.get("ntype"),
        "label": vmap.get("label"),
        "props": props,
    }


def _edge_triple(from_gid, to_gid, etype):
    return {"from": from_gid, "to": to_gid, "type": etype, "props": {}}


def get_rca_chain(rca_id):
    """Return the {nodes, edges} subgraph anchored on anomaly:<rca_id>.

    Collects the anomaly vertex, its root_cause via .out('caused_by') (+ the caused_by
    edge), and any correlated incident/change via .in_('correlates_with') (+ those edges).
    Returns {'nodes': [], 'edges': []} for an unknown/absent anomaly. Raises ConnectionError
    if the Gremlin server is unreachable.
    """
    connection = _connect()
    try:
        g = _traversal(connection)
        anomaly_gid = "anomaly:%s" % rca_id
        anchor = g.V().has("ntype", "anomaly").has("gid", anomaly_gid)
        anomaly_maps = anchor.clone().element_map().to_list()
        if not anomaly_maps:
            return {"nodes": [], "edges": []}

        nodes = {}
        edges = []

        for vmap in anomaly_maps:
            node = _vertex_to_node(vmap)
            nodes[node["id"]] = node

        # root_cause via .out('caused_by') (anomaly -> root_cause), native direction.
        for vmap in anchor.clone().out("caused_by").element_map().to_list():
            node = _vertex_to_node(vmap)
            nodes[node["id"]] = node
            edges.append(_edge_triple(anomaly_gid, node["id"], "caused_by"))

        # incident/change via .in_('correlates_with') (incident/change -> anomaly).
        for vmap in anchor.clone().in_("correlates_with").element_map().to_list():
            node = _vertex_to_node(vmap)
            nodes[node["id"]] = node
            edges.append(_edge_triple(node["id"], anomaly_gid, "correlates_with"))

        return {"nodes": list(nodes.values()), "edges": edges}
    finally:
        _close(connection)
