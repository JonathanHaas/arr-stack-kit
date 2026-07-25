# Arr Stack Kit

A self-hosted media automation stack (Sonarr, Radarr, Prowlarr, Transmission, SABnzbd, Overseerr, Homer) plus a small setup/admin panel that wires the pieces together, so you don't have to hand-copy API keys between apps.

## What's included

- **docker-compose.yml** — brings up the whole stack, plus [gluetun](https://github.com/qdm12/gluetun) to route Transmission's traffic through a Mullvad VPN tunnel.
- **admin-panel/** — a small password-protected web app (port 5500) where you paste in your *external* credentials (indexer API keys, Usenet provider login, etc.) and it configures everything else automatically via each app's REST API.

## System requirements

- **Docker Desktop** (Mac/Windows) or **Docker Engine + Compose plugin** (Linux)
- **CPU architecture**: amd64 (Intel/AMD) or arm64 (Apple Silicon, Raspberry Pi 4/5 on 64-bit OS) — all images used are multi-arch. 32-bit ARM (`armhf`) is **not** supported.
- **RAM**: 4GB minimum, 8GB+ recommended if you'll actually be downloading/transcoding, not just testing the setup
- **Disk space**: negligible for the apps themselves (a few hundred MB of config); your actual media library size is on you
- **Ports used on the host**: 8989 (Sonarr), 7878 (Radarr), 9696 (Prowlarr), 9091 (Transmission), 8090 (SABnzbd), 5055 (Overseerr), 8080 (Homer), 5500 (admin panel) — make sure nothing else on your machine is already using these
- **A Mullvad account** (or skip VPN entirely by removing the `gluetun`/`transmission` network dependency, if you don't need it)
- **A Usenet provider and/or torrent indexer account(s)** — this stack doesn't include or recommend any; bring your own

## Quick start (no terminal needed)

For friends who don't use the command line: install [Docker Desktop](https://www.docker.com/products/docker-desktop/), open it once and leave it running, then double-click:

- **Mac**: `start-mac.command`
- **Windows**: `start-windows.bat`

That's it. It sets everything up and opens the admin panel in your browser automatically, with no separate password required — see [Security notes](#security-notes) for why this is safe as long as you're accessing it either on your own LAN, or through a Cloudflare Tunnel + Access policy rather than exposed raw to the internet.

## Quick start (terminal)

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

## Admin panel configuration reference

All of these are read from `.env` (see `.env.example` for the full annotated list).

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ADMIN_PASSWORD` | Yes, unless `DISABLE_AUTH=true` | *(none)* | Password to log into the admin panel at `:5500`. |
| `DISABLE_AUTH` | No | `false` | Skips the login page entirely. **Local testing only** — never set `true` on anything reachable outside your own machine. |
| `CLOUDFLARE_TUNNEL_TOKEN` | Only if using the `cloudflare` profile | *(none)* | Token from Cloudflare Zero Trust; see [Remote access](#remote-access-via-cloudflare-tunnel-optional) below. |

The panel also auto-detects these — you don't set them, it reads them off each app's own config file the first time that app has been opened once in a browser:

| App | Where the key comes from |
|---|---|
| Sonarr | `data/sonarr/config.xml` |
| Radarr | `data/radarr/config.xml` |
| Prowlarr | `data/prowlarr/config.xml` |
| SABnzbd | `data/sabnzbd/sabnzbd.ini` |

If the panel's key-detection table shows "missing" for any of these, open that app's web UI once (first load generates its config), then refresh the panel.

Settings you enter directly in the panel's forms (Usenet provider login, indexer list) are stored in `data/admin-panel/settings.json` — not in `.env` — so they persist across container restarts/rebuilds without needing to re-enter them.

**Changing the password**: there's a "Change password" form directly in the admin panel — no need to edit `.env` or rebuild. It's stored hashed in `settings.json` and takes effect immediately. This is what lets a non-technical friend set their own password after first getting in via `DISABLE_AUTH=true` or the original `ADMIN_PASSWORD`, without ever touching a config file.

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

Two supported ways to gate access to the admin panel — pick one, don't mix them:

- **App-level password** (`ADMIN_PASSWORD` + `DISABLE_AUTH=false`, the default in `.env.example`): the panel's own login screen is the only thing standing between anyone and your config. Fine on a trusted home LAN with no remote exposure.
- **Cloudflare Zero Trust in front, `DISABLE_AUTH=true`**: if you're publishing the admin panel through a Cloudflare Tunnel with an Access policy (gating by email/login before Cloudflare's edge ever reaches your network), a second password on top is redundant — Cloudflare is already the real authentication layer. This is the intended setup for the double-click launcher scripts, and matches how the rest of this stack (Sonarr, Radarr, Transmission, etc.) already assumes Cloudflare Zero Trust handles auth rather than each app's own login.

**The one combination to avoid**: `DISABLE_AUTH=true` with the admin panel's port reachable directly from the internet with no Access policy in front of it. That leaves it completely open to anyone who finds the port.

API keys read from each app's config are only ever read (mounted `:ro`), never written by the panel.
