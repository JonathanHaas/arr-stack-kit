import json
import os
from functools import wraps

from flask import Flask, redirect, render_template, request, session, url_for

from arr_clients import (
    ArrClient,
    configure_sabnzbd_server,
    ensure_prowlarr_application,
    ensure_prowlarr_indexer,
    read_sabnzbd_api_key,
    read_xml_api_key,
)

app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_PASSWORD", "dev-only-change-me")

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
SONARR_URL = os.environ.get("SONARR_URL", "http://sonarr:8989")
RADARR_URL = os.environ.get("RADARR_URL", "http://radarr:7878")
PROWLARR_URL = os.environ.get("PROWLARR_URL", "http://prowlarr:9696")
OVERSEERR_URL = os.environ.get("OVERSEERR_URL", "http://overseerr:5055")
SABNZBD_URL = os.environ.get("SABNZBD_URL", "http://sabnzbd:8080")

SETTINGS_PATH = os.environ.get("SETTINGS_PATH", "/data/settings.json")


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    return {"indexers": [], "usenet": {}}


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authed"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["authed"] = True
            return redirect(url_for("index"))
        error = "Wrong password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def detect_keys():
    return {
        "sonarr": read_xml_api_key("/mnt/sonarr-config/config.xml"),
        "radarr": read_xml_api_key("/mnt/radarr-config/config.xml"),
        "prowlarr": read_xml_api_key("/mnt/prowlarr-config/config.xml"),
        "sabnzbd": read_sabnzbd_api_key("/mnt/sabnzbd-config/sabnzbd.ini"),
    }


@app.route("/")
@login_required
def index():
    keys = detect_keys()
    settings = load_settings()
    return render_template(
        "index.html",
        keys=keys,
        settings=settings,
        overseerr_url=OVERSEERR_URL.replace("overseerr", request.host.split(":")[0]),
    )


@app.route("/save-usenet", methods=["POST"])
@login_required
def save_usenet():
    settings = load_settings()
    settings["usenet"] = {
        "name": request.form["name"],
        "host": request.form["host"],
        "port": request.form["port"],
        "username": request.form["username"],
        "password": request.form["password"],
        "ssl": bool(request.form.get("ssl")),
    }
    save_settings(settings)
    return redirect(url_for("index"))


@app.route("/add-indexer", methods=["POST"])
@login_required
def add_indexer():
    settings = load_settings()
    settings["indexers"].append({
        "name": request.form["name"],
        "kind": request.form["kind"],
        "base_url": request.form["base_url"],
        "api_key": request.form["api_key"],
    })
    save_settings(settings)
    return redirect(url_for("index"))


@app.route("/remove-indexer/<int:idx>", methods=["POST"])
@login_required
def remove_indexer(idx):
    settings = load_settings()
    if 0 <= idx < len(settings["indexers"]):
        settings["indexers"].pop(idx)
    save_settings(settings)
    return redirect(url_for("index"))


@app.route("/sync", methods=["POST"])
@login_required
def sync():
    keys = detect_keys()
    settings = load_settings()
    results = []

    missing = [name for name, key in keys.items() if name != "sabnzbd" and not key]
    if missing:
        results.append({
            "step": "check",
            "status": "error",
            "detail": f"Waiting on first boot for: {', '.join(missing)}. "
                      f"Open each app's web UI once, then retry sync.",
        })
        return render_template("sync_result.html", results=results)

    prowlarr = ArrClient(PROWLARR_URL, keys["prowlarr"])

    results.append({
        "step": "Prowlarr <-> Sonarr",
        **ensure_prowlarr_application(prowlarr, "Sonarr", "Sonarr", "SonarrSettings", "http://sonarr:8989", keys["sonarr"]),
    })
    results.append({
        "step": "Prowlarr <-> Radarr",
        **ensure_prowlarr_application(prowlarr, "Radarr", "Radarr", "RadarrSettings", "http://radarr:7878", keys["radarr"]),
    })

    for indexer in settings["indexers"]:
        results.append({
            "step": f"Indexer: {indexer['name']}",
            **ensure_prowlarr_indexer(prowlarr, indexer["name"], indexer["kind"], indexer["base_url"], indexer["api_key"]),
        })

    if settings.get("usenet", {}).get("host") and keys["sabnzbd"]:
        u = settings["usenet"]
        results.append({
            "step": "SABnzbd Usenet server",
            **configure_sabnzbd_server(SABNZBD_URL, keys["sabnzbd"], u["name"], u["host"], u["port"], u["username"], u["password"], u["ssl"]),
        })
    elif settings.get("usenet", {}).get("host"):
        results.append({
            "step": "SABnzbd Usenet server",
            "status": "error",
            "detail": "SABnzbd hasn't been opened once yet (no API key found). Open its web UI once, then retry.",
        })

    return render_template("sync_result.html", results=results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500)
