import unittest

from cdn_event_filter import filter_cdn_sports_payload


def event(tournament, home="", away="", **extra):
    return {
        "gameID": f"{home}-{away}-{tournament}",
        "tournament": tournament,
        "homeTeam": home,
        "awayTeam": away,
        "channels": [{"channel_name": "Canal de prueba"}],
        **extra,
    }


class CdnEventFilterTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "cdn-live-tv": {
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
                "Tennis": [
                    event("ATP 500", "Jugador A", "Jugador B", eventTitle="Jugador A - Jugador B"),
                ],
                "Motorsport": [
                    event("Formula 1", eventTitle="Carrera"),
                ],
                "NHL": [event("NHL", "Chicago Blackhawks", "Buffalo Sabres")],
                "NFL": [event("NFL", "Kansas City Chiefs", "Indianapolis Colts")],
                "total_events": 17,
                "total_events_soccer": 11,
                "total_events_nba": 2,
                "total_events_tennis": 1,
                "total_events_motorsport": 1,
                "total_events_nhl": 1,
                "total_events_NFL": 1,
            }
        }

    def test_applies_futbolenlatv_competition_rules_to_soccer(self):
        filtered, stats = filter_cdn_sports_payload(self.payload)
        root = filtered["cdn-live-tv"]
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

    def test_uses_the_same_classifier_for_basketball_tennis_and_motor(self):
        filtered, _stats = filter_cdn_sports_payload(self.payload)
        root = filtered["cdn-live-tv"]
        self.assertEqual(len(root["NBA"]), 1)
        self.assertEqual(root["NBA"][0]["agenda_sport"], "Baloncesto")
        self.assertEqual(root["NBA"][0]["agenda_competition"], "NBA")
        self.assertEqual(len(root["Tennis"]), 1)
        self.assertEqual(root["Tennis"][0]["agenda_sport"], "Tenis")
        self.assertEqual(len(root["Motorsport"]), 1)
        self.assertEqual(root["Motorsport"][0]["agenda_sport"], "Motor")
        self.assertEqual(root["Motorsport"][0]["agenda_competition"], "Fórmula 1")

    def test_excludes_sports_not_allowed_by_personal_agenda(self):
        filtered, stats = filter_cdn_sports_payload(self.payload)
        root = filtered["cdn-live-tv"]
        self.assertEqual(root["NHL"], [])
        self.assertEqual(root["NFL"], [])
        self.assertEqual(stats["removed"]["NHL"], 1)
        self.assertEqual(stats["removed"]["NFL"], 1)

    def test_updates_api_totals_and_does_not_mutate_input(self):
        filtered, _stats = filter_cdn_sports_payload(self.payload)
        root = filtered["cdn-live-tv"]
        self.assertEqual(root["total_events"], 9)
        self.assertEqual(root["total_events_soccer"], 6)
        self.assertEqual(root["total_events_nba"], 1)
        self.assertEqual(root["total_events_tennis"], 1)
        self.assertEqual(root["total_events_motorsport"], 1)
        self.assertEqual(root["total_events_nhl"], 0)
        self.assertEqual(root["total_events_NFL"], 0)
        self.assertEqual(len(self.payload["cdn-live-tv"]["Soccer"]), 11)

    def test_accepts_nested_and_legacy_root_keys(self):
        nested = {"data": {"cdn-live-tv": {"Soccer": [event("Premier League", "Arsenal", "Chelsea")]}}}
        filtered, _stats = filter_cdn_sports_payload(nested)
        self.assertEqual(len(filtered["data"]["cdn-live-tv"]["Soccer"]), 1)

        legacy = {"cdnlivetv.tv": {"Soccer": [event("Premier League", "Arsenal", "Chelsea")]}}
        filtered, _stats = filter_cdn_sports_payload(legacy)
        self.assertEqual(len(filtered["cdnlivetv.tv"]["Soccer"]), 1)

    def test_rejects_unrecognized_api_shape(self):
        with self.assertRaises(ValueError):
            filter_cdn_sports_payload({"unexpected": []})


if __name__ == "__main__":
    unittest.main()
