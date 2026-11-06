import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup

import agenda_futbolenlatv as agenda


class FakeResponse:
    def __init__(self, content):
        self.content = content.encode("utf-8")

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, content):
        self.response = FakeResponse(content)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, *_args, **_kwargs):
        return self.response


class FutbolenlatvParserTests(unittest.TestCase):
    def test_keeps_match_when_atp_tv_and_other_channels_are_present(self):
        html = """<tr><td>12:00</td><td>ATP 250</td>
        <td>Jugador A - Jugador B</td><td>ATP Tennis TV</td>
        <td>M+ Deportes 2</td><td>Eurosport 2</td></tr>"""
        row = BeautifulSoup(html, "html.parser").find("tr")
        parsed = agenda.parse_row_elements(row)
        self.assertEqual(parsed[2], ["M+ Deportes 2", "Eurosport 2"])
        blob = agenda.normalize_search_text(" ".join(parsed[4]) + " " + parsed[3] + " " + " ".join(parsed[2]))
        classification = agenda.get_sport_and_competition(blob, parsed[3], " ".join(parsed[2]).lower(), parsed[4])
        self.assertEqual(classification[0], "Tenis")

    def test_drops_match_if_atp_tv_is_the_only_channel(self):
        html = """<tr><td>13:30</td><td>ATP 250</td>
        <td>Jugador C - Jugador D</td><td>ATP Tennis TV</td></tr>"""
        row = BeautifulSoup(html, "html.parser").find("tr")
        parsed = agenda.parse_row_elements(row)
        self.assertEqual(parsed[0], "")
        self.assertEqual(parsed[2], [])

    def test_serializes_futbolenlatv_events(self):
        html = """<table><tr><td>06/11/2026</td></tr>
        <tr><td>18:00</td><td>LaLiga</td><td>Real Madrid - Barcelona</td>
        <td>M+ LaLiga</td><td>DAZN 1</td></tr></table>"""
        with patch.object(agenda, "create_http_session", return_value=FakeSession(html)):
            payload = agenda.get_agenda_payload()
        self.assertEqual(payload["count"], 1)
        event = payload["events"][0]
        self.assertEqual(event["date"], "2026-11-06")
        self.assertEqual(event["time"], "18:00")
        self.assertEqual(event["event"], "Real Madrid - Barcelona")
        self.assertTrue(event["featured"])


if __name__ == "__main__":
    unittest.main()
