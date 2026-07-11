import { useCallback, useMemo, useRef, useState } from "react";
import { GraphNode, GraphEdge } from "../types";

const edgeKey = (a: string, b: string) => [a, b].sort().join("|");

export function useGraphState() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const edgeIndexRef = useRef<Map<string, number>>(new Map());

  const loadInitial = useCallback((n: GraphNode[], e: GraphEdge[]) => {
    setNodes(n);
    setEdges(e);
    const idx = new Map<string, number>();
    e.forEach((edge, i) => idx.set(edgeKey(edge.from, edge.to), i));
    edgeIndexRef.current = idx;
  }, []);

  const applyEdgeUpdates = useCallback((changed: GraphEdge[]) => {
    setEdges((prev) => {
      const copy = [...prev];
      changed.forEach((ce) => {
        if (!ce) return;
        const key = edgeKey(ce.from, ce.to);
        const i = edgeIndexRef.current.get(key);
        if (i !== undefined) copy[i] = ce;
      });
      return copy;
    });
  }, []);

  const nodesById = useMemo(() => {
    const map = new Map<string, GraphNode>();
    nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [nodes]);

  const floodedEdges = useMemo(() => edges.filter((e) => e.depth_cm > 0), [edges]);

  return { nodes, edges, nodesById, floodedEdges, loadInitial, applyEdgeUpdates };
}