"""Thin helpers for reading auto-generated API keys and talking to each *arr app's REST API."""
import configparser
import os
import xml.etree.ElementTree as ET

import requests


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
    parser = configparser.ConfigParser(strict=False)
    parser.read(ini_path)
    try:
        return parser.get("misc", "api_key")
    except (configparser.NoSectionError, configparser.NoOptionError):
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
