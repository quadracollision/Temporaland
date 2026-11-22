# Releasing

The repository version is stored in `VERSION`. A release is ready when the
repository validator passes from a clean checkout:

```bash
./scripts/validate-repository.sh
```

Before publishing:

1. Review `CHANGELOG.md` and update the version/date.
2. Confirm no deployment password, browser cookie, media upload, database, SSH
   key, or server backup is present in the repository.
3. Test the base installer on Ubuntu 24.04.
4. Choose and add a project license before describing the repository as open
   source. Bundled third-party code retains its own license.
5. Create a signed tag matching `VERSION`, for example `v0.1.0`, and attach the
   generated source archive and checksum. Use
   `docs/release-notes-v0.1.0.md` as the initial release body.

Build a deterministic source archive with:

```bash
./scripts/build-release.sh
```

The command writes the archive and SHA-256 checksum under `dist/`.

When Git and GitHub authentication are configured, publish with:

```bash
git tag -s "v$(cat VERSION)" -m "Temporaman Shrine v$(cat VERSION)"
git push origin "v$(cat VERSION)"
gh release create "v$(cat VERSION)" \
  "dist/temporaman-shrine-v$(cat VERSION).tar.gz" \
  "dist/temporaman-shrine-v$(cat VERSION).tar.gz.sha256" \
  --title "Temporaman Shrine v$(cat VERSION)" \
  --notes-file "docs/release-notes-v$(cat VERSION).md"
```
