"""Validate generated IPTV artifacts before publishing."""
import json
import re
from collections import Counter
from pathlib import Path

root = Path(__file__).parent
report = json.loads((root / "report.json").read_text(encoding="utf-8"))
channels = json.loads((root / "channels.json").read_text(encoding="utf-8"))
playlist = (root / "playlist.m3u").read_text(encoding="utf-8-sig").splitlines()
assert playlist and playlist[0] == "#EXTM3U", "Missing M3U header"
assert len(playlist) == 1 + 2 * len(channels), "M3U/channel count mismatch"
assert len(channels) == report["total"], "Report/channel count mismatch"
assert len(channels) >= 100, "Unexpectedly small playlist"
seen = set()
for index, channel in enumerate(channels):
    country = channel["country"]
    name = channel["name"]
    url = channel["url"]
    key = (country, re.sub(r"\s*\(\d{3,4}p\)", "", name).strip().casefold())
    assert key not in seen, f"Duplicate country/name: {key}"
    seen.add(key)
    assert url.startswith(("http://", "https://")), f"Invalid URL: {url}"
    assert playlist[2 * index + 1].startswith("#EXTINF:"), f"Invalid EXTINF at {index}"
    assert playlist[2 * index + 2] == url, f"URL mismatch at {index}"
    assert f'tvg-country="{country}"' in playlist[2 * index + 1], f"Missing country at {index}"
    assert 'group-title="' in playlist[2 * index + 1], f"Missing group at {index}"
    metadata = channel.get("metadata") or {}
    cats = metadata.get("categories") or []
    assert not metadata.get("is_nsfw"), f"NSFW channel: {name}"
    assert not any(c.lower() in {"xxx", "adult", "porn", "pornography", "erotic"} for c in cats), f"Adult category: {name}"
assert dict(Counter(x["country"] for x in channels)) == report["countries"], "Country counts mismatch"
if report.get("weekly_http_test"):
    status = json.loads((root / "stream_status.json").read_text(encoding="utf-8"))
    assert all(x["url"] in status for x in channels), "Missing stream diagnostic"
    assert sum(status[x["url"]]["status"] == "ok" for x in channels) == report["http_positive_selected"], "Positive count mismatch"
print(f"VALIDATED: {len(channels)} channels, {len(report['countries'])} countries, metadata and deduplication")
