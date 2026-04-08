# Frontend Roadmap

Decomposition of the market data frontend into sequential sub-projects. Each
sub-project gets its own spec → plan → implementation cycle.

## Sub-projects (in build order)

1. **Foundation: API + UI shell**
   Backend HTTP/WebSocket API layer on top of existing Python services,
   frontend framework choice, app shell, routing, config page. Everything
   below depends on this.

2. **Watchlists**
   CRUD, default list, symbol management, persistence.

3. **Scanner control panel**
   Selecting scanners, on-demand runs, viewing results, "save results as
   watchlist" action.

4. **Scheduler UI**
   Managing scheduled scanner runs (wraps existing APScheduler).

5. **Charting**
   Multi-timeframe realtime charts with basic indicators. Largest and
   hardest single piece.

6. **Chart alerts**
   Drawing alert levels on charts; wires into existing `AlertEngine`.
   Depends on #5.

## Cross-cutting requirements

- **Lightweight + high performance** — shapes framework choice, bundle
  size, rendering strategy across every sub-project.

## Status

- [ ] 1. Foundation — *brainstorming in progress (2026-04-08)*
- [ ] 2. Watchlists
- [ ] 3. Scanner control panel
- [ ] 4. Scheduler UI
- [ ] 5. Charting
- [ ] 6. Chart alerts
