# `runeo-deploy` host audit

Audited read-only on 2026-11-19 using the SSH identity at `/home/jacob/src/JacobScape/runeo-deploy`.

## Identified target

- Host: `67.207.88.225`
- Provider shape: DigitalOcean droplet (`ubuntu-s-1vcpu-512mb-10gb-nyc1` hostname)
- Operating system: Ubuntu 24.04.4 LTS, x86-64
- SSH account: `root`
- CPU: 1 vCPU
- Memory: approximately 1 GB RAM plus 2 GB swap
- Root disk: 24 GB total, 6.1 GB free
- Docker: not installed

The private key itself must remain outside this repository. Do not copy it into deployment archives, images, shell history, or source control.

## Existing production workload

The host is not empty. It currently runs:

- JacobScape/OpenRSC on TCP 43494 and 43594;
- nginx on TCP 80 and 443;
- PostgreSQL 16;
- Margeux services;
- TypeBook;
- a JacobScape download service on TCP 8000.

Existing nginx names include `typebook.lol`, `margeux.com`, `margeux.duckdns.org`, and a journal `sslip.io` hostname. Kasm cannot take over TCP 443 directly without displacing these sites.

## Capacity verdict

Do **not** run the Kasm installer on the current host size.

Current Kasm requirements list a minimum of 2 CPU cores, 4 GB RAM, and 75 GB SSD. The default workspace allocation itself is 2 cores and 2768 MB RAM. The target fails all three capacity requirements while already supporting live services.

For this shared Audacity workload alongside the existing services, use at least:

- 4 vCPUs;
- 8 GB RAM;
- 100 GB SSD;
- the existing 2 GB swap or larger;
- a fresh snapshot/backup before any resize or installation.

This recommendation leaves headroom for the game server, PostgreSQL, Kasm control services, one Audacity container, audio streaming, and image updates. Kasm recommends a single-purpose host, so a separate droplet is safer than enlarging this shared production server.

## Recommended deployment choices

### Preferred: separate Kasm droplet

Create a new Ubuntu 24.04 droplet with 4 vCPUs, 8 GB RAM, and at least 100 GB SSD. Point a dedicated hostname such as `studio.example.com` at it and run the repository installer there. This isolates Audacity resource spikes and Docker maintenance from JacobScape.

### Acceptable pilot: resize this droplet

If this exact server must be used:

1. Take a DigitalOcean snapshot and verify application/database backups.
2. Resize CPU/RAM and permanently expand disk to at least the recommendation above. This requires a shutdown/reboot and causes downtime.
3. Re-run `scripts/check-host.sh` remotely.
4. Install Kasm on an alternate internal HTTPS port such as 8443 rather than claiming port 443.
5. Add an nginx virtual host for a dedicated studio hostname that proxies WebSocket and HTTPS traffic to Kasm.
6. Keep Kasm's Docker and project storage under monitored disk quotas.
7. Run `scripts/verify-kasm-host.sh`, then the complete two-user pilot checklist.

Do not begin this path until the resize, associated billing change, maintenance window, hostname, and backup state are explicitly approved.

## Unresolved deployment inputs

- Whether to resize the current production droplet or create a separate one.
- The hostname to use for the studio.
- The maintenance window if resizing the current droplet.
- Confirmation that current PostgreSQL and project backups are restorable.
