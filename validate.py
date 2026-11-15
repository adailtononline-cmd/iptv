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
assert report.get("retained_after_deduplication") == len(channels), "Retained count mismatch"
assert report.get("excluded_after_checks", -1) >= 0, "Invalid exclusion count"
assert report.get("duplicate_candidates", -1) >= 0, "Invalid duplicate count"
required_countries = set("US CA UK FR PT BR CN JP AU IT TR".split())
missing_countries = required_countries - set(report["countries"])
assert not missing_countries, f"Missing required countries: {sorted(missing_countries)}"
assert report["excluded_after_checks"] + report["total"] >= report["total"], "Invalid totals"
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
    extinf = playlist[2 * index + 1]
    assert f'tvg-id="{channel["id"]}"' in extinf, f"TVG ID mismatch at {index}"
    expected_group = channel["category"]
    assert f' | {expected_group}"' in extinf, f"Category mismatch at {index}"
    if channel.get("logo"):
        assert f'tvg-logo="{channel["logo"]}"' in extinf, f"Logo mismatch at {index}"
    if channel.get("languages"):
        expected_languages = ",".join(channel["languages"])
        assert f'tvg-language="{expected_languages}"' in extinf, f"Language mismatch at {index}"

    metadata = channel.get("metadata") or {}
    cats = metadata.get("categories") or []
    assert not metadata.get("is_nsfw"), f"NSFW channel: {name}"
    assert not any(c.lower() in {"xxx", "adult", "porn", "pornography", "erotic"} for c in cats), f"Adult category: {name}"
assert dict(Counter(x["country"] for x in channels)) == report["countries"], "Country counts mismatch"
if report.get("weekly_http_test"):
    status = json.loads((root / "stream_status.json").read_text(encoding="utf-8"))
    assert sum(report.get("test_results", {}).values()) == report.get("tested_streams"), "Test result totals mismatch"
    assert report["tested_streams"] >= len(channels), "Fewer tests than published channels"
    assert all(x["url"] in status for x in channels), "Missing stream diagnostic"
    confirmed_dead = {"404", "410", "invalid_hls", "html"}
    assert not any(status[x["url"]].get("failures", 0) >= 2 and status[x["url"]].get("status") in confirmed_dead for x in channels), "Confirmed dead stream retained"
    assert sum(status[x["url"]]["status"] == "ok" for x in channels) == report["http_positive_selected"], "Positive count mismatch"
print(f"VALIDATED: {len(channels)} channels, {len(report['countries'])} countries, metadata and deduplication")
