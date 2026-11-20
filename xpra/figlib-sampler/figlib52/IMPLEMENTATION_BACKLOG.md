# FiggyGen RT Rewrite v1 Backlog

## 1) Planning Assumptions
- Timebox target: 10-14 weeks.
- Team shape: 2-4 engineers.
- Priority order: real-time stability first, compatibility second, ergonomics third.
- Definition of done for all tickets:
  - tests added/updated
  - docs updated where behavior changes
  - no realtime-thread safety violations introduced

## 2) Milestone Map
1. M0: Baseline + harness
2. M1: Core contracts + graph compiler
3. M2: Callback runtime skeleton
4. M3: FX/routing + automation
5. M4: Script/control-plane convergence
6. M5: Hardening + release candidate

## 3) Ownership Model
- Runtime owner: `packages/figgygen_core/runtime/*`, `realtime/*`
- Graph owner: `packages/figgygen_core/graph/*`
- DSP owner: `packages/figgygen_core/synthesis/*`
- Parser/compat owner: `packages/figgygen_core/parser/*`, `compat/*`
- Tools/CI owner: benchmark harness, telemetry, CI gates, docs

## 4) Epic Backlog

## EPIC RT-00: Baseline and Safety Harness
Goal: lock current behavior and create realtime regression tooling.

### RT-001: Fixture corpus capture
- Scope: capture representative CLI/.psy/.psy2 configs and output artifacts.
- Output: `tests/fixtures/*`, fixture manifest JSON.
- Estimate: 2 days
- Depends on: none

### RT-002: Realtime benchmark harness scaffold
- Scope: callback duration/xrun instrumentation skeleton.
- Output: `bench/realtime_harness/*`
- Estimate: 3 days
- Depends on: none

### RT-003: CI job for perf smoke
- Scope: add CI target that runs harness in reduced mode.
- Output: CI workflow + threshold config.
- Estimate: 1 day
- Depends on: RT-002

### RT-004: Realtime safety lint/checklist
- Scope: codify "no alloc/no IO/no locks in callback" checks and reviewer checklist.
- Output: `docs/realtime_safety.md`, optional static checks.
- Estimate: 1 day
- Depends on: none

## EPIC RT-10: Domain Contracts and Planner
Goal: introduce canonical typed specs and planning path.

### RT-101: Define typed models
- Scope: `EngineSpec`, `GraphSpec`, `EventSpec`, `ExecutionSnapshot`.
- Output: `packages/figgygen_core/domain/models.py`
- Estimate: 2 days
- Depends on: RT-001

### RT-102: Diagnostic/error model
- Scope: structured diagnostics and error classes.
- Output: `packages/figgygen_core/domain/errors.py`
- Estimate: 1 day
- Depends on: RT-101

### RT-103: Planner skeleton
- Scope: normalize input specs into plan/snapshot structures.
- Output: `packages/figgygen_core/orchestration/planner.py`
- Estimate: 3 days
- Depends on: RT-101, RT-102

### RT-104: Graph validation pass
- Scope: acyclic checks, channel/output validation.
- Output: `packages/figgygen_core/graph/topo.py`
- Estimate: 2 days
- Depends on: RT-103

## EPIC RT-20: Real-Time Runtime Skeleton
Goal: first end-to-end tone in realtime with safe threading model.

### RT-201: Audio engine callback shell
- Scope: callback API wrapper and buffer lifecycle.
- Output: `packages/figgygen_core/runtime/audio_engine.py`
- Estimate: 4 days
- Depends on: RT-103

### RT-202: Lock-free command bus
- Scope: control->audio thread messaging primitives.
- Output: `packages/figgygen_core/realtime/{ringbuffer.py,command_bus.py}`
- Estimate: 3 days
- Depends on: RT-201

### RT-203: Preallocated buffer pool
- Scope: block buffers and memory reuse in callback.
- Output: `packages/figgygen_core/runtime/buffers.py`
- Estimate: 2 days
- Depends on: RT-201

### RT-204: Minimal oscillator+mixer node path
- Scope: render stable tone with graph execution.
- Output: `packages/figgygen_core/synthesis/{oscillators.py,mixing.py}`
- Estimate: 4 days
- Depends on: RT-201, RT-203

### RT-205: Callback metrics + xrun telemetry
- Scope: callback timing histograms/xrun counters.
- Output: `packages/figgygen_core/realtime/metrics.py`
- Estimate: 2 days
- Depends on: RT-201

## EPIC RT-30: Graph Compiler and Node Runtime
Goal: compile user specs into executable realtime node graph.

### RT-301: Graph compiler v1
- Scope: compile nodes/edges into ordered runtime graph.
- Output: `packages/figgygen_core/graph/compiler.py`
- Estimate: 4 days
- Depends on: RT-104, RT-204

### RT-302: Snapshot hot-swap protocol
- Scope: atomic graph version swap at safe boundary.
- Output: runtime graph manager module and tests.
- Estimate: 3 days
- Depends on: RT-301, RT-202

### RT-303: Bus gain/mute/solo semantics
- Scope: enforce deterministic bus controls.
- Output: graph node logic + tests.
- Estimate: 2 days
- Depends on: RT-301

### RT-304: Send/return routing support
- Scope: support auxiliary routing with cycle safeguards.
- Output: compiler + topo validation updates.
- Estimate: 3 days
- Depends on: RT-303

## EPIC RT-40: MIDI, Events, Automation, Transport
Goal: sample-accurate control plane.

### RT-401: Event scheduler with frame timestamps
- Scope: queue + due-event dispatch by frame.
- Output: `packages/figgygen_core/runtime/scheduler.py`
- Estimate: 3 days
- Depends on: RT-202, RT-301

### RT-402: Voice manager
- Scope: polyphony + deterministic voice stealing.
- Output: `packages/figgygen_core/runtime/voice_manager.py`
- Estimate: 3 days
- Depends on: RT-401

### RT-403: MIDI adapter
- Scope: normalize MIDI to event specs.
- Output: runtime MIDI input module.
- Estimate: 3 days
- Depends on: RT-401

### RT-404: Parameter automation ramps
- Scope: sample-accurate ramps + control smoothing.
- Output: `packages/figgygen_core/graph/params.py`
- Estimate: 3 days
- Depends on: RT-401

### RT-405: Transport model
- Scope: bpm/time signature/playhead/seek/play-state.
- Output: `packages/figgygen_core/runtime/transport.py`
- Estimate: 2 days
- Depends on: RT-401

## EPIC RT-50: FX Porting and Realtime Safety
Goal: bring existing effects into callback-safe runtime.

### RT-501: FX audit and tiering
- Scope: classify FX as realtime-ready / needs refactor / offline-only.
- Output: `docs/fx_realtime_matrix.md`
- Estimate: 2 days
- Depends on: RT-004

### RT-502: Realtime-safe FX wrapper API
- Scope: unified processing API with preallocated state.
- Output: `packages/figgygen_core/synthesis/effects.py`
- Estimate: 3 days
- Depends on: RT-501, RT-301

### RT-503: Port critical FX set
- Scope: minimal set for v1 (filter, delay, reverb-lite, distortion, compressor-lite).
- Output: callback-safe implementations + tests.
- Estimate: 8 days
- Depends on: RT-502

### RT-504: FX chain integration in compiler/runtime
- Scope: attach effect chains per bus.
- Output: compiler/runtime integration tests.
- Estimate: 3 days
- Depends on: RT-503, RT-304

## EPIC RT-60: Parser/Compatibility Convergence
Goal: one planner path for CLI/REPL/.psy/.psy2.

### RT-601: CLI normalizer rewrite
- Scope: argv -> typed spec only (no direct execution).
- Output: `packages/figgygen_core/parser/cli_normalizer.py`
- Estimate: 3 days
- Depends on: RT-101

### RT-602: `.psy2` adapter to Script/Graph spec
- Scope: AST/evaluator output mapped into canonical contracts.
- Output: `packages/figgygen_core/parser/psy2_adapter.py`
- Estimate: 4 days
- Depends on: RT-103

### RT-603: `.psy` compatibility adapter
- Scope: legacy commands mapped into canonical contracts.
- Output: `packages/figgygen_core/parser/psy_compat.py`
- Estimate: 4 days
- Depends on: RT-103

### RT-604: Compatibility diagnostics
- Scope: warnings/errors for deprecated/ambiguous semantics.
- Output: parser diagnostic coverage tests.
- Estimate: 2 days
- Depends on: RT-602, RT-603

## EPIC RT-70: Offline Renderer Parity
Goal: keep existing generation/bounce workflows on same core.

### RT-701: Offline renderer using graph snapshot
- Scope: block render runner not bound to callback deadlines.
- Output: `packages/figgygen_core/render/offline_renderer.py`
- Estimate: 4 days
- Depends on: RT-301, RT-401

### RT-702: Metadata/provenance writer
- Scope: hashes, seed, graph version, preset manifest.
- Output: `packages/figgygen_core/output/metadata.py`
- Estimate: 2 days
- Depends on: RT-701

### RT-703: Naming/writer cleanup
- Scope: centralized output naming and file write paths.
- Output: `packages/figgygen_core/output/writer.py`
- Estimate: 2 days
- Depends on: RT-701

## EPIC RT-80: Host, Tooling, and Developer UX
Goal: runnable standalone realtime host and operational tools.

### RT-801: Standalone host app skeleton
- Scope: start/stop engine, audio device selection.
- Output: `apps/figgygen_rt_host/*`
- Estimate: 4 days
- Depends on: RT-201

### RT-802: REPL control-plane integration
- Scope: REPL sends commands/events over command bus.
- Output: `apps/figgygen_repl/*`
- Estimate: 3 days
- Depends on: RT-202, RT-601

### RT-803: CLI mode split (realtime/offline)
- Scope: explicit mode flags and command ergonomics.
- Output: `apps/figgygen_cli/*`
- Estimate: 3 days
- Depends on: RT-601, RT-701

### RT-804: Plan inspect/validate commands
- Scope: `validate-script`, `explain-plan`, `migrate-script`.
- Output: command handlers + docs.
- Estimate: 4 days
- Depends on: RT-602, RT-603

## EPIC RT-90: Hardening and Release
Goal: production confidence and release assets.

### RT-901: Long-run soak suite
- Scope: 1h+ stress scenarios with assertions.
- Output: `tests/soak/*`
- Estimate: 3 days
- Depends on: RT-503, RT-801

### RT-902: Determinism audit suite
- Scope: fixture-based deterministic verification.
- Output: determinism tests + tolerance docs.
- Estimate: 3 days
- Depends on: RT-701

### RT-903: Performance threshold gates
- Scope: enforce callback/CPU/xrun thresholds in CI.
- Output: CI benchmark gates.
- Estimate: 2 days
- Depends on: RT-003, RT-901

### RT-904: Migration docs + release notes
- Scope: upgrade guide from generator-first to realtime-first usage.
- Output: docs and changelog.
- Estimate: 2 days
- Depends on: RT-804, RT-902

## 5) Critical Path
1. RT-101 -> RT-103 -> RT-201 -> RT-301 -> RT-401 -> RT-503 -> RT-701 -> RT-801 -> RT-901 -> RT-903

## 6) Parallelization Plan
- Stream A (Runtime): RT-201/202/203/205, then RT-401/402/405
- Stream B (Graph/DSP): RT-301/302/303/304 + RT-502/503/504
- Stream C (Parser/UX): RT-601/602/603/604 + RT-802/803/804
- Stream D (Quality): RT-001/002/003/004 + RT-901/902/903/904

## 7) Milestone Exit Checklist
### M1 exit
- Typed contracts landed
- Planner + graph validation passing
- No direct parser->synth execution in new path

### M2 exit
- Realtime callback stable for oscillator tone at 48k/128
- Zero allocations and no locks in callback (instrumented)

### M3 exit
- Core FX set realtime-safe
- Bus routing and sends functional in realtime
- MIDI note on/off and automation ramps verified

### M4 exit
- CLI/REPL/.psy/.psy2 converge to common planner path
- Offline renderer parity tests pass for selected fixtures

### M5 exit
- Stress, soak, determinism, and perf gates green
- Migration docs complete

## 8) Immediate Next Sprint (Recommended)
1. RT-001 Fixture corpus capture
2. RT-101 Typed model definitions
3. RT-002 Realtime harness scaffold
4. RT-103 Planner skeleton
5. RT-201 Callback shell


