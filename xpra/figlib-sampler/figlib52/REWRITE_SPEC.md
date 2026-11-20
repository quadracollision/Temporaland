# FiggyGen Full Rewrite Spec (Real-Time Audio Engine)

## 1) Objective
Rewrite FiggyGen from an offline sample generator into a real-time audio engine with optional offline render modes.

Primary outcomes:
1. Hard real-time capable audio processing core.
2. Deterministic graph execution and stable low-latency playback.
3. Unified engine API for CLI, REPL, scripting, and future host/plugin integration.
4. Backward compatibility for existing presets/scripts where feasible.

## 2) Inputs Reviewed
- Docs: `README.md`, `CLI_REFERENCE.md`, `SCRIPTING_GUIDE.md`, `PSY2_GUIDE.md`, `AI_PROMPT_GUIDE.md`
- Runtime: `run.py`, `src/pySynth/{cli.py,main.py,generator.py,parsing.py}`
- PSY2 stack: `src/psy2/{lexer.py,parser.py,evaluator.py}`

## 3) Current-State Assessment
### 3.1 Gaps vs real-time requirements
- Current architecture is batch/render-first and file-output-centric.
- Execution orchestration is duplicated and not optimized for callback-time guarantees.
- Parsing/validation and processing are interleaved, unsafe for an audio thread.
- Randomization/state mutation occur in runtime paths without strict scheduling boundaries.

### 3.2 Risks if unchanged
- XRuns/dropouts under load.
- Non-deterministic runtime behavior.
- Unbounded latency from dynamic allocations/IO in processing path.
- Difficulty integrating MIDI transport and sample-accurate automation.

## 4) Product Pivot
FiggyGen becomes:
- A real-time engine with graph-based buses/FX/routing.
- A transport-aware runtime with MIDI/event scheduling.
- A dual-mode system:
  - `realtime`: live playback/interaction
  - `offline`: deterministic bounce/export (existing sample-generation workflows)

## 5) Scope
### 5.1 In scope (v1 RT rewrite)
- New callback-safe engine core.
- Graph compiler + scheduler.
- MIDI/event input and automation lanes.
- Shared plan/contracts across CLI/REPL/scripts.
- Offline renderer as a consumer of the same engine graph.
- Compatibility adapter for `.psy` and `.psy2`.

### 5.2 Out of scope (v1)
- Full DAW UI.
- Cross-process plugin sandboxing.
- Network audio collaboration.

## 6) Real-Time Requirements
### 6.1 Hard constraints
- No file IO on the audio callback thread.
- No memory allocation on the audio callback thread.
- No locks/mutex contention on the audio callback thread.
- All heavy parsing, preset loading, and graph compilation happen off-thread.

### 6.2 Performance targets
- Support 44.1k/48k/96k sample rates.
- Stable operation at 64-128 sample buffers on reference hardware.
- End-to-end roundtrip target: <= 10ms at 48k/128 where host/device permits.
- Callback deadline misses: 0 in standard smoke suite, < 0.01% under stress benchmarks.

## 7) Target Architecture
```text
apps/
  figgygen_cli/
  figgygen_repl/
  figgygen_rt_host/          # standalone RT host process
packages/
  figgygen_core/
    domain/
      models.py              # RunSpec, EngineSpec, GraphSpec, EventSpec
      errors.py
    parser/
      cli_normalizer.py
      psy_compat.py
      psy2_adapter.py
    graph/
      compiler.py            # specs -> compiled graph
      topo.py                # routing/order validation
      params.py              # automation/param map
    runtime/
      audio_engine.py        # audio callback entrypoint
      scheduler.py           # event queue + sample-accurate dispatch
      transport.py           # bpm/ppq/playhead/timebase
      voice_manager.py       # polyphony/voice stealing
      buffers.py             # preallocated block buffers
    synthesis/
      oscillators.py
      effects.py
      mixing.py
    realtime/
      ringbuffer.py          # lock-free queues
      command_bus.py         # UI/control thread -> audio thread messages
      metrics.py             # xruns/cpu/load telemetry
    render/
      offline_renderer.py    # uses same graph/scheduler without callback limits
    presets/
      loader.py
      schemas.py
    output/
      writer.py              # offline files only
      metadata.py
```

## 8) Threading Model
Threads:
- Audio thread: DSP only, callback hard real-time.
- Control thread: UI/CLI/REPL command handling, parse/validate.
- Worker threads: preset loading, graph compile, sample decode, analysis.

Communication:
- Single-producer/single-consumer lock-free queues where possible.
- Immutable graph snapshots swapped atomically at safe boundaries.
- Command messages are timestamped in sample frames for deterministic apply points.

## 9) Engine Contracts
### 9.1 `EngineSpec`
- `sample_rate`
- `buffer_size`
- `channels_in`, `channels_out`
- `mode: "realtime" | "offline"`
- `transport_enabled`
- `max_polyphony`

### 9.2 `GraphSpec`
- Nodes: oscillators, samplers, FX, mixers, outputs.
- Edges: routed signal connections with channel policy.
- Bus metadata: gain, mute, solo, send/return.

### 9.3 `EventSpec`
- `timestamp_frames`
- `type`: note on/off, param change, transport, preset swap.
- `target_id`
- `payload`

### 9.4 `ExecutionSnapshot`
- Immutable compiled graph + resolved params.
- Versioned for safe hot-swap.

## 10) Real-Time Graph and Scheduling
1. Parse input/script into validated spec.
2. Compile graph off-thread.
3. Publish graph snapshot to engine at swap point.
4. Audio callback processes per buffer:
   - pop due events
   - process graph in topological order
   - write output buffer
5. Metrics capture xruns/callback load.

Hard rule: callback path must only access preallocated memory and lock-free data structures.

## 11) MIDI, Automation, and Transport
### 11.1 MIDI
- Support note on/off, velocity, pitch bend, aftertouch, CC.
- MIDI timestamp normalization to engine sample clock.
- Voice manager handles allocation/stealing deterministically.

### 11.2 Automation
- Sample-accurate parameter ramps for critical controls.
- Control-rate smoothing for non-critical parameters.
- Parameter updates queued as timestamped events.

### 11.3 Transport
- BPM, time signature, PPQ timeline.
- Play/stop/seek commands via command bus.
- Optional sync hooks for external host clock (future-compatible).

## 12) Compatibility Strategy
### 12.1 Preserved
- Existing `.psi` and `.psifx` assets.
- Existing core CLI generation flows as offline mode wrappers.
- Existing script syntax via adapters.

### 12.2 Adjusted semantics
- Randomization resolved at compile/snapshot boundaries, not mid-callback.
- Script `generate` maps to either:
  - offline bounce command, or
  - realtime scene instantiation with explicit duration/record intent.

### 12.3 Deprecations
- Direct path from parser to execution side effects.
- Any runtime behavior requiring IO from audio thread.

## 13) Validation and Diagnostics
Diagnostic schema:
- `code`
- `severity` (`error|warning|info`)
- `message`
- `location`
- `hint`

Validation gates:
1. Syntax (CLI/script)
2. Semantic (known nodes/FX/params)
3. Graph validity (acyclic, channel compatibility, output presence)
4. Realtime safety (disallowed operations flagged)

## 14) Determinism
- Seeded randomization resolved during graph compile.
- Runtime callback deterministic given:
  - fixed seed
  - same graph snapshot
  - same event stream and timestamps
  - same platform/dependencies
- Snapshot metadata stores `seed`, `graph_hash`, `preset_manifest_hash`, `engine_version`.

## 15) Testing Strategy
### 15.1 Unit
- Graph compiler correctness and topo ordering.
- Event queue ordering and timestamp dispatch.
- Parameter smoothing/ramp math.
- Voice allocation and stealing policy.

### 15.2 Integration
- Realtime smoke tests at multiple buffer sizes/sample rates.
- MIDI input -> audible state transitions.
- Graph hot-swap without callback glitches.
- Offline renderer parity with realtime graph processing.

### 15.3 Realtime stress
- Synthetic heavy patches for xrun profiling.
- Long-run stability soak tests.
- CPU and heap telemetry assertions.

### 15.4 Golden
- Offline deterministic output hashes for known fixtures.
- Realtime capture fingerprint tolerance tests.

## 16) Performance Budgets
- Callback CPU headroom target: <= 60% average on reference patch set.
- 99th percentile callback duration < 80% of deadline.
- Graph swap operation amortized off-thread; atomic swap on buffer boundary.
- Memory churn on audio thread: zero allocations (verified by instrumentation).

## 17) Security and Safety
- Strict path validation for offline IO.
- Controlled sample decoder pipeline off-thread.
- Defensive handling of malformed presets/scripts.
- Crash containment strategy in standalone host process.

## 18) Delivery Plan
### Phase 0: Baseline and harness (1-2 weeks)
- Capture current behavior fixtures.
- Build realtime benchmark harness and telemetry.
Exit criteria:
- Baseline suite and profiling scaffolding in CI.

### Phase 1: Core contracts + graph compiler (2 weeks)
- Introduce `EngineSpec`, `GraphSpec`, `EventSpec`.
- Compile existing patch/preset flow into graph snapshots.
Exit criteria:
- Offline mode runs through new graph compiler.

### Phase 2: Callback runtime skeleton (2 weeks)
- Implement audio engine loop, buffers, lock-free command bus.
- Integrate simple oscillator + mixer pipeline.
Exit criteria:
- Stable tone generation in realtime at 48k/128.

### Phase 3: FX and routing integration (2-3 weeks)
- Port effect chain and bus routing into callback-safe nodes.
- Add automation/event dispatch.
Exit criteria:
- Existing bus/FX scenarios run in realtime without xruns in smoke suite.

### Phase 4: Script and control-plane convergence (1-2 weeks)
- Route CLI/REPL/.psy/.psy2 into common graph pipeline.
- Add offline bounce mode using same graph/executor.
Exit criteria:
- One planner path for realtime and offline.

### Phase 5: Hardening and release candidate (2 weeks)
- Stress tests, determinism audits, docs/migration finalize.
Exit criteria:
- Meets realtime perf budgets and acceptance checklist.

## 19) Acceptance Criteria
- Single shared graph pipeline for realtime and offline modes.
- Zero allocation and zero blocking locks in callback thread.
- Stable realtime playback at target buffer sizes on reference hardware.
- MIDI and automation are sample-accurate within buffer scheduling guarantees.
- Legacy presets/scripts execute through compatibility adapters.
- CI gates include realtime stress and determinism suites.

## 20) Risks and Mitigations
- DSP code not callback-safe in current form.
  - Mitigation: node-by-node port with realtime safety checklist.
- Latency and xrun regressions under complex patches.
  - Mitigation: profiling-first rollout and budget gates.
- Feature parity delays during architecture shift.
  - Mitigation: maintain offline compatibility path while RT core matures.
- Script semantic ambiguity between render and live modes.
  - Mitigation: explicit mode declarations and migration diagnostics.

## 21) Open Design Decisions
1. Standalone host backend: PortAudio, RtAudio, or host abstraction layer?
2. Plugin target in roadmap: VST3/AU/LV2 vs standalone-first only?
3. Strict realtime-safe subset of FX in v1 vs full parity target?
4. Default mode for existing CLI commands: offline or realtime session bootstrap?
5. Determinism guarantees across OS/CPU boundaries in published contract.

## 22) Deliverables
- `figgygen_core` realtime engine package.
- Standalone realtime host app (`figgygen_rt_host`).
- Unified planner/compiler used by CLI/REPL/scripts.
- Offline bounce pipeline using same graph runtime.
- Compatibility adapters for `.psy` and `.psy2`.
- Realtime benchmark harness, telemetry, and CI gates.
- Updated docs:
  - realtime architecture
  - thread-safety model
  - migration from sample-generation workflow
  - API and scripting mode behavior

