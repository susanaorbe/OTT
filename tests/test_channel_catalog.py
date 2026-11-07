import unittest
from channel_catalog import filter_playable_channels

VALID = "https://cdnlivetv.tv/api/v1/channels/player/?name=Example&code=&user=cdnlivetv&plan=free"

class CompleteChannelCatalogTests(unittest.TestCase):
    def test_offline_and_online_channels_are_both_kept(self):
        result = filter_playable_channels({"channels": [
            {"name": "Online", "status": "online", "url": VALID},
            {"name": "Offline", "status": "offline", "url": VALID},
        ]})
        self.assertEqual([c["name"] for c in result["channels"]], ["Offline", "Online"])
        self.assertEqual(result["catalog_check"]["total_channels"], 2)
        self.assertTrue(next(c for c in result["channels"] if c["name"] == "Offline")["playback_allowed"])

    def test_channel_without_valid_player_url_remains_visible_in_catalog(self):
        result = filter_playable_channels({"channels": [
            {"name": "No player", "status": "offline", "url": "https://example.com/"}
        ]})
        self.assertEqual(len(result["channels"]), 1)
        self.assertFalse(result["channels"][0]["playback_allowed"])
        self.assertNotIn("player_url", result["channels"][0])

    def test_uses_official_player_url_and_preserves_source_fields(self):
        result = filter_playable_channels({"channels": [
            {"name": "Example", "status": "offline", "url": VALID, "viewers": 0}
        ]})
        channel = result["channels"][0]
        self.assertEqual(channel["player_url"], VALID)
        self.assertEqual(channel["viewers"], 0)
        self.assertEqual(channel["status"], "offline")

    def test_does_not_publish_explicitly_restricted_entries(self):
        result = filter_playable_channels({"channels": [
            {"name": "General", "url": VALID},
            {"name": "Restricted flag", "url": VALID, "age_restricted": True},
            {"name": "Restricted category", "url": VALID, "content_category": "age-restricted"},
        ]})
        self.assertEqual([c["name"] for c in result["channels"]], ["General"])

if __name__ == "__main__":
    unittest.main()
