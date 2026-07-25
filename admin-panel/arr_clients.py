"""Thin helpers for reading auto-generated API keys and talking to each *arr app's REST API."""
import configparser
import os
import xml.etree.ElementTree as ET

import requests
import yaml


def read_xml_api_key(config_path):
    """Sonarr/Radarr/Prowlarr all store their generated key in config.xml at first boot."""
    if not os.path.exists(config_path):
        return None
    try:
        return ET.parse(config_path).getroot().findtext("ApiKey")
    except ET.ParseError:
        return None


def read_sabnzbd_api_key(ini_path):
    if not os.path.exists(ini_path):
        return None
    # SABnzbd's ini starts with a bare "__version__ = N" line before any
    # [section] header, which configparser rejects outright — skip past it.
    parser = configparser.ConfigParser(strict=False)
    try:
        with open(ini_path) as f:
            lines = f.readlines()
        first_section = next((i for i, line in enumerate(lines) if line.strip().startswith("[")), None)
        if first_section is None:
            return None
        parser.read_string("".join(lines[first_section:]))
        return parser.get("misc", "api_key")
    except (configparser.Error, OSError):
        return None


def wait_for_key(config_path, reader, attempts=1):
    """Config files only appear after the app's first boot; caller retries via the UI, not here."""
    return reader(config_path)


class ArrClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    def get(self, path):
        r = requests.get(f"{self.base_url}{path}", headers=self.headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def post(self, path, payload):
        r = requests.post(f"{self.base_url}{path}", headers=self.headers, json=payload, timeout=10)
        return r

    def put(self, path, payload):
        r = requests.put(f"{self.base_url}{path}", headers=self.headers, json=payload, timeout=10)
        return r


def ensure_prowlarr_application(prowlarr, name, implementation, config_contract, internal_url, api_key):
    """Add Sonarr/Radarr as a synced application inside Prowlarr, if not already present."""
    existing = prowlarr.get("/api/v1/applications")
    for app in existing:
        if app.get("name") == name:
            return {"status": "already configured"}

    payload = {
        "name": name,
        "syncLevel": "fullSync",
        "implementation": implementation,
        "configContract": config_contract,
        "fields": [
            {"name": "prowlarrUrl", "value": f"http://prowlarr:9696"},
            {"name": "baseUrl", "value": internal_url},
            {"name": "apiKey", "value": api_key},
        ],
    }
    resp = prowlarr.post("/api/v1/applications", payload)
    if resp.status_code >= 300:
        return {"status": "error", "detail": resp.text}
    return {"status": "created"}


def ensure_prowlarr_indexer(prowlarr, name, kind, base_url, api_key):
    """Add a generic Newznab or Torznab indexer to Prowlarr."""
    implementation = "Newznab" if kind == "newznab" else "Torznab"
    config_contract = "NewznabSettings" if kind == "newznab" else "TorznabSettings"

    existing = prowlarr.get("/api/v1/indexer")
    for idx in existing:
        if idx.get("name") == name:
            return {"status": "already configured"}

    payload = {
        "name": name,
        "enable": True,
        "priority": 25,
        "implementation": implementation,
        "configContract": config_contract,
        "fields": [
            {"name": "baseUrl", "value": base_url},
            {"name": "apiPath", "value": "/api"},
            {"name": "apiKey", "value": api_key},
            {"name": "categories", "value": [5000, 5030, 5040, 2000, 2010, 2020, 2030, 2040, 2045]},
        ],
    }
    resp = prowlarr.post("/api/v1/indexer", payload)
    if resp.status_code >= 300:
        return {"status": "error", "detail": resp.text}
    return {"status": "created"}


def configure_sabnzbd_server(sabnzbd_url, sabnzbd_api_key, name, host, port, username, password, ssl):
    params = {
        "mode": "set_config",
        "section": "servers",
        "keyword": name,
        "name": name,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "ssl": "1" if ssl else "0",
        "enable": "1",
        "connections": "8",
        "apikey": sabnzbd_api_key,
        "output": "json",
    }
    resp = requests.get(f"{sabnzbd_url}/sabnzbd/api", params=params, timeout=10)
    if resp.status_code >= 300:
        return {"status": "error", "detail": resp.text}
    return {"status": "created", "response": resp.json()}


def patch_recyclarr_config(config_path, sonarr_key, radarr_key):
    """Fill in base_url/api_key under recyclarr.yml's sonarr:/radarr: instances,
    whatever those instances happen to be named. Leaves everything else (quality
    profiles, custom formats, trash IDs) exactly as the user configured it."""
    if not os.path.exists(config_path):
        return {"status": "skipped", "detail": "recyclarr.yml not found yet — copy the example config first."}

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        return {"status": "error", "detail": f"Couldn't parse recyclarr.yml: {exc}"}

    changed = False
    for app_name, internal_url, api_key in (
        ("sonarr", "http://sonarr:8989", sonarr_key),
        ("radarr", "http://radarr:7878", radarr_key),
    ):
        instances = config.get(app_name)
        if not isinstance(instances, dict):
            continue
        for instance in instances.values():
            if not isinstance(instance, dict):
                continue
            instance["base_url"] = internal_url
            instance["api_key"] = api_key
            changed = True

    if not changed:
        return {"status": "skipped", "detail": "No sonarr:/radarr: instances found in recyclarr.yml to fill in."}

    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return {"status": "created", "detail": "base_url/api_key filled in for all configured instances."}
