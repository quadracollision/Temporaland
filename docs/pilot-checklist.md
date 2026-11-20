# Two-player Audacity pilot checklist

Record the date, Kasm version, Audacity version, browsers, participant locations, and approximate latency before testing.

## Access and isolation

- [ ] An unauthenticated browser cannot reach the Audacity workspace.
- [ ] User A and User B sign in using separate accounts.
- [ ] A user outside the collaborators group cannot launch the Audacity workspace.
- [ ] User B cannot join until User A shares the instance URL.
- [ ] Ending sharing invalidates access through the old sharing URL.

## Shared control

- [ ] User A launches one Audacity instance.
- [ ] User B joins that exact running instance rather than a second container.
- [ ] User A can edit using keyboard and pointer.
- [ ] User B can edit using keyboard and pointer.
- [ ] Both users see changes made by the other within an acceptable delay.
- [ ] The pair can follow a driver/navigator handoff without disruptive control collisions.

## Audio and files

- [ ] User A uploads and imports a WAV file.
- [ ] User B uploads and imports a second audio file.
- [ ] Both users hear Audacity playback clearly.
- [ ] Mute, solo, cut, move, undo, and redo behave normally.
- [ ] Audacity saves the `.aup3` project under `/projects`.
- [ ] Audacity exports a WAV mix under `/projects/.../exports`.
- [ ] A user downloads the exported WAV through Kasm.

## Persistence and recovery

- [ ] Both users sign out and the session is stopped normally.
- [ ] A new session can open the saved `.aup3` project with all media present.
- [ ] A server-side backup contains the project, media, and export.
- [ ] The project opens successfully from a restored copy of that backup.

## Real-world usability

- [ ] A continuous 60-minute editing session completes without disconnects.
- [ ] Playback latency is acceptable for editing and review.
- [ ] Display quality is sufficient to read waveforms and Audacity controls.
- [ ] CPU, memory, disk, and network usage stay within host capacity.
- [ ] Both participants agree the shared-pointer workflow is usable.

The pilot passes only when every required item succeeds. A failure of the shared-pointer workflow is a product limitation, not a login-site bug; choose a collaboration-aware DAW if that interaction is unacceptable.
