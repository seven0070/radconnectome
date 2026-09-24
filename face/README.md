# Face — visual surfaces (P3 honesty note)

No live server, no node toolchain in P3. Every surface here is a **static
snapshot export**: Python renders data → standalone HTML file → open in any
browser. Snapshots are labeled as such in the page itself.

- `canvas/` — plan DAG snapshots via `rcx/canvas.py::export_html()`
  (consumes `PlanGraph.to_flow()`).
- `panel/` — state dashboard snapshots via `rcx/panel.py::export_dashboard()`
  (connectome stats, tribe weights, cost rollup, ARC baseline).

A live studio (websocket, interactivity) is post-v1.0 work, explicitly out
of scope until the gates it would display are all green.
