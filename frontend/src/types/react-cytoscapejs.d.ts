// Local module-declaration shims for `react-cytoscapejs@2.0.0` and `cytoscape`,
// neither of which ships TypeScript types here (the real types live in the
// separate `@types/react-cytoscapejs` / `@types/cytoscape`, deliberately NOT
// installed to avoid the corporate-proxy TLS wall — see design §3 toolchain
// note + plan item 1).
//
// These declare only the surface the RcaGraph component actually uses:
// element/stylesheet/layout shapes passed to the component, plus a minimal
// node accessor for the background-colour callback. `skipLibCheck:true` keeps
// this cheap.
declare module 'cytoscape' {
  // A single graph element (node or edge). Nodes carry { id, ntype, label };
  // edges carry { id, source, target, etype }.
  export interface ElementDefinition {
    data: Record<string, unknown>;
  }

  // Minimal node handle exposed to style callbacks — just the `data(key)`
  // accessor the colour map uses.
  export interface NodeSingular {
    data(key: string): unknown;
  }

  // A cytoscape stylesheet entry: a selector plus a style map. Style values may
  // be literals or (for node fill) a function of the element.
  export interface Stylesheet {
    selector: string;
    style: Record<string, unknown>;
  }

  export interface LayoutOptions {
    name: string;
    [key: string]: unknown;
  }

  // Core handle passed to the optional `cy` callback. Left opaque — unused here.
  export interface Core {
    [key: string]: unknown;
  }
}

declare module 'react-cytoscapejs' {
  import type { CSSProperties, ComponentType } from 'react';
  import type {
    Core,
    ElementDefinition,
    LayoutOptions,
    Stylesheet,
  } from 'cytoscape';

  export interface CytoscapeComponentProps {
    elements: ElementDefinition[];
    stylesheet?: Stylesheet[];
    layout?: LayoutOptions;
    style?: CSSProperties;
    className?: string;
    cy?: (cy: Core) => void;
    // Passthrough for DOM attributes the container div receives (e.g. `id`,
    // `data-testid`).
    [key: string]: unknown;
  }

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
