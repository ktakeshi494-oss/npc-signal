import time, requests
from .config import USER_AGENT

S = requests.Session()
S.headers["User-Agent"] = USER_AGENT

def get_json(url, params=None, tries=4, timeout=25):
    """GET with polite retry on 429/503 (honours Retry-After, per Polymarket docs)."""
    for i in range(tries):
        r = S.get(url, params=params, timeout=timeout)
        if r.status_code in (429, 503) and i < tries - 1:
            time.sleep(min(float(r.headers.get("Retry-After", 2 ** i)), 30)); continue
        r.raise_for_status()
        return r.json()

def post_json(url, payload, tries=3, timeout=25, headers=None):
    for i in range(tries):
        r = S.post(url, json=payload, timeout=timeout, headers=headers)
        if r.status_code in (429, 503) and i < tries - 1:
            time.sleep(min(float(r.headers.get("Retry-After", 2 ** i)), 30)); continue
        r.raise_for_status()
        return r.json()
