import unittest

from cdn_event_filter import filter_cdn_sports_payload


def event(tournament, home, away, **extra):
    return {
        "gameID": f"{home}-{away}",
        "tournament": tournament,
        "homeTeam": home,
        "awayTeam": away,
        "channels": [{"channel_name": "Canal de prueba"}],
        **extra,
    }


class CdnEventFilterTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "cdnlivetv.tv": {
                "Soccer": [
                    event("LaLiga EA Sports", "Real Madrid", "Barcelona"),
                    event("Premier League", "Arsenal", "Chelsea"),
                    event("Francia - Ligue 1", "PSG", "Lyon"),
                    event("Alemania - Bundesliga", "Bayern", "Dortmund"),
                    event("Brasil - Serie A", "Vasco da Gama", "Flamengo"),
                    event("LaLiga Hypermotion", "Eibar", "Málaga"),
                    event("Liga F", "Barcelona", "Real Madrid"),
                    event("Primera Federación - Grupo 1", "Real Madrid Castilla", "Unionistas"),
                    event("Primera Federación - Grupo 1", "Deportivo", "Celta Fortuna"),
                    event("Competición desconocida", "Equipo A", "Equipo B"),
                    event("Liga desconocida", "Equipo C", "Equipo D", country="Portugal"),
                ],
                "NBA": [
                    event("NBA", "Los Angeles Lakers", "Boston Celtics"),
                    event("Basketball Champions League", "Equipo A", "Equipo B"),
                ],
                "NHL": [event("NHL", "Chicago Blackhawks", "Buffalo Sabres")],
                "NFL": [event("NFL", "Kansas City Chiefs", "Indianapolis Colts")],
                "total_events": 14,
                "total_events_soccer": 10,
                "total_events_nba": 2,
                "total_events_nhl": 1,
                "total_events_NFL": 1,
            }
        }

    def test_applies_futbolenlatv_competition_rules_to_soccer(self):
        filtered, stats = filter_cdn_sports_payload(self.payload)
        root = filtered["cdnlivetv.tv"]
        self.assertEqual(
            [item["tournament"] for item in root["Soccer"]],
            [
                "LaLiga EA Sports",
                "Premier League",
                "Francia - Ligue 1",
                "Alemania - Bundesliga",
                "Liga F",
                "Primera Federación - Grupo 1",
            ],
        )
        self.assertEqual(stats["removed"]["Soccer"], 5)

    def test_filters_nba_using_the_same_classifier(self):
        filtered, stats = filter_cdn_sports_payload(self.payload)
        root = filtered["cdnlivetv.tv"]
        self.assertEqual(len(root["NBA"]), 1)
        self.assertEqual(root["NBA"][0]["homeTeam"], "Los Angeles Lakers")
        self.assertEqual(stats["removed"]["NBA"], 1)

    def test_keeps_nhl_and_nfl_for_all_view_only(self):
        filtered, _stats = filter_cdn_sports_payload(self.payload)
        root = filtered["cdnlivetv.tv"]
        self.assertEqual(len(root["NHL"]), 1)
        self.assertEqual(len(root["NFL"]), 1)

    def test_updates_api_totals_and_does_not_mutate_input(self):
        filtered, _stats = filter_cdn_sports_payload(self.payload)
        root = filtered["cdnlivetv.tv"]
        self.assertEqual(root["total_events"], 9)
        self.assertEqual(root["total_events_soccer"], 6)
        self.assertEqual(root["total_events_nba"], 1)
        self.assertEqual(root["total_events_nhl"], 1)
        self.assertEqual(root["total_events_NFL"], 1)
        self.assertEqual(len(self.payload["cdnlivetv.tv"]["Soccer"]), 11)

    def test_rejects_unrecognized_api_shape(self):
        with self.assertRaises(ValueError):
            filter_cdn_sports_payload({"unexpected": []})


if __name__ == "__main__":
    unittest.main()
