import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import channel_catalog as catalog

PLAYER = "https://cdnlivetv.tv/api/v1/channels/player/?name=abc&code=us&user=cdnlivetv&plan=free"


class ChannelCatalogTests(unittest.TestCase):
    def test_accepts_only_expected_https_provider_player_url(self):
        self.assertTrue(catalog.valid_player_url(PLAYER))
        self.assertFalse(catalog.valid_player_url(PLAYER.replace("https://", "http://")))
        self.assertFalse(catalog.valid_player_url(PLAYER.replace("cdnlivetv.tv", "other.example")))
        self.assertFalse(catalog.valid_player_url(PLAYER.replace("/channels/player/", "/channels/raw/")))

    def test_keeps_online_channel_when_player_page_is_accessible(self):
        payload = {"channels": [{"name": "ABC", "code": "us", "status": "online", "url": PLAYER}]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(catalog, "probe_player_url", return_value=(True, "ok")):
            result = catalog.filter_playable_channels(payload, Path(tmp) / "checks.json")
        self.assertEqual([c["name"] for c in result["channels"]], ["ABC"])
        self.assertTrue(result["channels"][0]["playback_allowed"])
        self.assertEqual(result["channels"][0]["player_url"], PLAYER)

    def test_hides_offline_channel_and_channel_without_player_url(self):
        payload = {"channels": [
            {"name": "Offline", "code": "us", "status": "offline", "url": PLAYER},
            {"name": "No URL", "code": "us", "status": "online"},
        ]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(catalog, "probe_player_url") as probe:
            result = catalog.filter_playable_channels(payload, Path(tmp) / "checks.json")
        self.assertEqual(result["channels"], [])
        probe.assert_not_called()
        self.assertEqual(result["catalog_check"]["excluded_offline"], 1)

    def test_hides_channel_when_player_page_probe_fails(self):
        payload = {"channels": [{"name": "ABC", "code": "us", "status": "online", "url": PLAYER}]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(catalog, "probe_player_url", return_value=(False, "HTTP 403")):
            result = catalog.filter_playable_channels(payload, Path(tmp) / "checks.json")
        self.assertEqual(result["channels"], [])

    def test_reuses_recent_successful_probe(self):
        payload = {"channels": [{"name": "ABC", "code": "us", "status": "online", "url": PLAYER}]}
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "checks.json"
            cache_path.write_text(json.dumps({"checks": {"abc|us": {
                "url": PLAYER, "ok": True, "reason": "ok", "checked_at": datetime.now(timezone.utc).isoformat()
            }}}), encoding="utf-8")
            with patch.object(catalog, "probe_player_url") as probe:
                result = catalog.filter_playable_channels(payload, cache_path)
        probe.assert_not_called()
        self.assertEqual(len(result["channels"]), 1)

    def test_sorts_channels_alphabetically(self):
        payload = {"channels": [
            {"name": "Zeta", "code": "us", "status": "online", "url": PLAYER.replace("name=abc", "name=zeta")},
            {"name": "Alpha", "code": "us", "status": "online", "url": PLAYER.replace("name=abc", "name=alpha")},
        ]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(catalog, "probe_player_url", return_value=(True, "ok")):
            result = catalog.filter_playable_channels(payload, Path(tmp) / "checks.json")
        self.assertEqual([c["name"] for c in result["channels"]], ["Alpha", "Zeta"])


if __name__ == "__main__":
    unittest.main()
