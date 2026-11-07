import unittest
from cdn_event_filter import filter_cdn_sports_payload

class CompleteCdnAgendaTests(unittest.TestCase):
    def test_keeps_every_category_and_events_without_channels(self):
        payload = {"cdn-live-tv": {
            "Soccer": [{"gameID": "1", "channels": []}],
            "Badminton": [{"gameID": "2", "channels": []}],
            "Motorsport": [{"gameID": "3", "channels": [{"channel_name": "A"}]}],
        }}
        result, stats = filter_cdn_sports_payload(payload)
        root = result["cdn-live-tv"]
        self.assertEqual(sum(map(len, root.values())), 3)
        self.assertEqual(stats["total_kept"], 3)
        self.assertEqual(stats["total_removed"], 0)

    def test_preserves_event_fields_and_does_not_classify_or_rewrite(self):
        event = {"event": "Tournament", "status": "NS", "country": "Japan", "channels": []}
        result, _ = filter_cdn_sports_payload({"cdn-live-tv": {"Other Sport": [event]}})
        self.assertEqual(result["cdn-live-tv"]["Other Sport"][0], event)

    def test_omits_explicitly_age_restricted_events(self):
        result, stats = filter_cdn_sports_payload({"cdn-live-tv": {"Category": [
            {"event": "General"}, {"event": "Restricted", "age_restricted": True}
        ]}})
        self.assertEqual(len(result["cdn-live-tv"]["Category"]), 1)
        self.assertEqual(stats["total_removed"], 1)

if __name__ == "__main__":
    unittest.main()
