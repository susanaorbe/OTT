import tempfile
import unittest
from pathlib import Path

import channel_catalog as catalog

PLAYER_WITH_CODE = "https://cdnlivetv.tv/api/v1/channels/player/?name=abc&code=us&user=cdnlivetv&plan=free"
PLAYER_WITHOUT_CODE = "https://cdnlivetv.tv/api/v1/channels/player/?name=abc&code=&user=cdnlivetv&plan=free"


class ChannelCatalogTests(unittest.TestCase):
    def test_accepts_official_player_url_with_or_without_code(self):
        self.assertTrue(catalog.valid_player_url(PLAYER_WITH_CODE))
        self.assertTrue(catalog.valid_player_url(PLAYER_WITHOUT_CODE))

    def test_rejects_non_official_or_incomplete_player_urls(self):
        self.assertFalse(catalog.valid_player_url(PLAYER_WITH_CODE.replace("https://", "http://")))
        self.assertFalse(catalog.valid_player_url(PLAYER_WITH_CODE.replace("cdnlivetv.tv", "other.example")))
        self.assertFalse(catalog.valid_player_url(PLAYER_WITH_CODE.replace("/channels/player/", "/channels/raw/")))
        self.assertFalse(catalog.valid_player_url(PLAYER_WITHOUT_CODE.replace("name=abc&", "")))
        self.assertFalse(catalog.valid_player_url(PLAYER_WITHOUT_CODE.replace("code=&", "")))
        self.assertFalse(catalog.valid_player_url(PLAYER_WITHOUT_CODE.replace("plan=free", "plan=premium")))

    def test_keeps_online_channel_even_when_code_is_empty(self):
        payload = {"channels": [{
            "name": "ABC", "code": "", "status": "online", "url": PLAYER_WITHOUT_CODE
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            result = catalog.filter_playable_channels(payload, Path(tmp) / "checks.json")
        self.assertEqual([c["name"] for c in result["channels"]], ["ABC"])
        self.assertTrue(result["channels"][0]["playback_allowed"])
        self.assertEqual(result["channels"][0]["player_url"], PLAYER_WITHOUT_CODE)
        self.assertEqual(result["channels"][0]["player_check"], "api_status_online_official_url")

    def test_keeps_online_and_live_but_excludes_offline(self):
        payload = {"channels": [
            {"name": "Live", "code": "", "status": "live", "url": PLAYER_WITHOUT_CODE},
            {"name": "Online", "code": "us", "status": "online", "url": PLAYER_WITH_CODE},
            {"name": "Offline", "code": "us", "status": "offline", "url": PLAYER_WITH_CODE},
        ]}
        result = catalog.filter_playable_channels(payload)
        self.assertEqual({c["name"] for c in result["channels"]}, {"Live", "Online"})
        self.assertEqual(result["catalog_check"]["excluded_offline"], 1)

    def test_does_not_require_or_create_a_probe_cache(self):
        payload = {"channels": [{
            "name": "ABC", "code": "", "status": "online", "url": PLAYER_WITHOUT_CODE
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "checks.json"
            result = catalog.filter_playable_channels(payload, cache_path)
            self.assertFalse(cache_path.exists())
        self.assertEqual(len(result["channels"]), 1)

    def test_sorts_channels_alphabetically(self):
        payload = {"channels": [
            {"name": "Zeta", "code": "", "status": "online", "url": PLAYER_WITHOUT_CODE.replace("name=abc", "name=zeta")},
            {"name": "Alpha", "code": "", "status": "online", "url": PLAYER_WITHOUT_CODE.replace("name=abc", "name=alpha")},
        ]}
        result = catalog.filter_playable_channels(payload)
        self.assertEqual([c["name"] for c in result["channels"]], ["Alpha", "Zeta"])


if __name__ == "__main__":
    unittest.main()
