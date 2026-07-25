# Arr Stack Kit

A self-hosted media automation stack (Sonarr, Radarr, Prowlarr, Transmission, SABnzbd, Overseerr, Homer) plus a small setup/admin panel that wires the pieces together, so you don't have to hand-copy API keys between apps.

## What's included

- **docker-compose.yml** — brings up the whole stack, plus [gluetun](https://github.com/qdm12/gluetun) to route Transmission's traffic through a Mullvad VPN tunnel.
- **admin-panel/** — a small password-protected web app (port 5500) where you paste in your *external* credentials (indexer API keys, Usenet provider login, etc.) and it configures everything else automatically via each app's REST API.

## Quick start

1. Copy `.env.example` to `.env` and fill in values (admin password, Mullvad credentials, media paths).
2. `docker compose up -d`
3. Open each of these once, so they generate their config/API key on first boot:
   - Sonarr: `http://<host>:8989`
   - Radarr: `http://<host>:7878`
   - Prowlarr: `http://<host>:9696`
   - SABnzbd: `http://<host>:8090`
   - Overseerr: `http://<host>:5055` — this one needs a real interactive Plex login, so its setup can't be automated
4. Open the admin panel: `http://<host>:5500`, log in with `ADMIN_PASSWORD`.
5. Fill in your Usenet provider details and any indexers you use, then click **Sync now**.
   - This adds Sonarr/Radarr as synced applications inside Prowlarr, adds your indexers, and configures SABnzbd's server — all using each app's auto-generated API key, which the panel reads directly off disk.
6. Point Homer's dashboard config (`data/homer/config.yml`) at whichever services you want cards for. See `homer-config-example.yml` for a starting point matching this stack.

## What the admin panel does NOT do (yet)

- **Overseerr setup** — needs a real Plex account login, so it's a manual one-time step (linked from the panel).
- **Quality profiles / custom formats** — use [Recyclarr](https://recyclarr.dev/) separately if you want TRaSH Guides-style quality profiles; not wired into this panel yet.
- **Mullvad WireGuard key generation** — you need to generate and register a WireGuard keypair with your Mullvad account yourself (see comments in `.env.example`); the panel doesn't do this for you since it involves an external account API call best done once by hand.

## Why gluetun instead of a manual WireGuard config

The original bare-metal version of this stack (running natively on a Raspberry Pi) configured WireGuard directly via `wg-quick`. For a Docker-based distribution, [gluetun](https://github.com/qdm12/gluetun) is the standard approach — it's a purpose-built container that handles the VPN tunnel and lets you route just one other container's (Transmission's) network traffic through it, without needing host-level WireGuard setup on whatever machine this gets deployed to.

## Remote access via Cloudflare Tunnel (optional)

To reach the admin panel remotely without opening any ports on your router, this stack includes an opt-in Cloudflare Tunnel service.

1. In the [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com/) -> Networks -> Tunnels, create a tunnel.
2. Add a Published Application Route for your chosen hostname (e.g. `admin.yourdomain.com`) pointing at `http://admin-panel:5500` — use the Docker service name, not `localhost`, since the tunnel container talks to `admin-panel` over the internal Docker network.
3. Copy the tunnel's token into `.env` as `CLOUDFLARE_TUNNEL_TOKEN`.
4. Start the stack including the tunnel:
   ```bash
   docker compose --profile cloudflare up -d
   ```
   (the plain `docker compose up -d` from Quick Start intentionally skips the tunnel, so nothing breaks if you haven't set a token)

Media files themselves never touch Cloudflare — the tunnel only proxies the admin panel's web UI; all downloads/library files stay on local disk via the bind mounts in `docker-compose.yml`.

## Security notes

- The admin panel is guarded by a single shared password (`ADMIN_PASSWORD`) — fine for a home network, but don't expose port 5500 directly to the internet. Put it behind a VPN or a reverse-proxy with proper auth (e.g. Cloudflare Zero Trust) if you need remote access.
- API keys read from each app's config are only ever read (mounted `:ro`), never written by the panel.
