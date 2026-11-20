# Configure Kasm for shared Audacity

These steps begin after `scripts/install-kasm-host.sh` completes on a dedicated server.

## 1. Secure the installation

1. Open `https://SERVER_ADDRESS/` and sign in as `admin@kasm.local` using the generated password from the installer.
2. Replace both generated default passwords, then disable or remove the generic `user@kasm.local` account.
3. Put the host behind a real DNS name and trusted TLS certificate before allowing internet access.
4. Create two named user accounts. Do not share one Kasm account between collaborators.
5. Enable two-factor authentication if the server will be reachable from the internet.

Kasm itself is the login system. A separate login website is unnecessary for the pilot and would create a second authentication layer to maintain.

## 2. Install Audacity

1. In the admin interface, open **Workspaces** and then **Workspace Registry**.
2. Use Kasm's pre-installed first-party registry. If it was removed, add `https://registry.kasmweb.com/`.
3. Find **Audacity** and install it.
4. Use a static release image for the pilot so both test sessions run the same software. The host installer selects Kasm 1.19.0 static images.
5. Allocate at least 2 CPU cores and 3–4 GB RAM to the Audacity workspace for the pilot.

Do not use the standalone `docker run` example as the finished system. Kasm documents that audio, upload, download, and microphone services require full Workspaces orchestration.

## 3. Create the collaborators group

Create a group named `Audacity Collaborators`, add the two named accounts, then add these Group Settings:

| Variable | Value | Purpose |
| --- | --- | --- |
| `allow_kasm_sharing` | `true` | Enables **Share Instance**. |
| `shared_session_full_control` | `true` | Lets the joining collaborator control Audacity. |
| `allow_kasm_audio` | `true` | Streams Audacity playback to browsers. |
| `allow_kasm_uploads` | `true` | Enables importing local audio through Kasm's upload control. |
| `allow_kasm_downloads` | `true` | Enables downloading exported mixes and projects. |
| `allow_persistent_profile` | `true` | Allows projects to survive session deletion. |
| `allow_kasm_clipboard_up` | `true` | Optional convenience for text copied into the session. |
| `allow_kasm_clipboard_down` | `true` | Optional convenience for text copied out of the session. |

Settings from multiple groups can conflict. In Kasm, the lowest-priority-number group setting wins, so confirm each user's **effective** settings rather than checking only this group.

## 4. Add durable project storage

Create a server directory owned by the container user:

```bash
sudo mkdir -p /srv/doubletrack/projects
sudo chown -R 1000:1000 /srv/doubletrack/projects
sudo chmod 0770 /srv/doubletrack/projects
```

Edit the Audacity Workspace and add this **Volume Mappings** JSON:

```json
{
  "/srv/doubletrack/projects": {
    "bind": "/projects",
    "mode": "rw",
    "uid": 1000,
    "gid": 1000,
    "required": true,
    "skip_check": false
  }
}
```

This is a deliberately shared folder: either collaborator can change or delete its contents. Back it up. For a multi-server Kasm deployment, replace the local directory with shared storage accessible to every agent.

Uploaded files normally appear in the Kasm session's upload location. Move source audio into `/projects/PROJECT_NAME/media/` before importing it into Audacity. Store the `.aup3` file in `/projects/PROJECT_NAME/` and exports in `/projects/PROJECT_NAME/exports/`.

## 5. Start a two-player session

1. User A signs in and launches the Audacity workspace.
2. User A opens Kasm's in-session control panel, selects **Share Instance**, and copies the generated URL.
3. User B signs into their own Kasm account and opens that URL.
4. Confirm User B can move the pointer and use Audacity controls.
5. Agree on a driver/navigator rule. Both clients control one OS pointer and keyboard focus; this is not independent-cursor collaboration.

## 6. Import audio

1. Open the Kasm control panel and select **Upload**.
2. Upload a small WAV file during the first test.
3. In Audacity choose **File → Import → Audio**, locate the uploaded file, and import it.
4. Move or copy the source into the project's durable `/projects/.../media` directory.
5. Confirm both users hear playback through Kasm.

Do not use remote microphone passthrough for musical overdubbing. Browser/network latency prevents dependable monitoring. Record takes locally, then upload them.

## 7. Run the acceptance test

Complete every item in `docs/pilot-checklist.md`. Do not build a branded portal until the shared-control pilot passes.
