import base64
import json
import time

class Presences:
    def __init__(self, Requests, log):
        self.Requests = Requests
        self.log = log

    def get_presence(self):
        if self.Requests.is_deceive_running():
            return self._get_presence_via_glz()

        presences = self.Requests.fetch(url_type="local", endpoint="/chat/v4/presences", method="get")
        if presences is None:
            return None
        return presences['presences']

    def _get_presence_via_glz(self):
        try:
            match_response = self.Requests.fetch(url_type="glz",
                endpoint=f"/core-game/v1/players/{self.Requests.puuid}", method="get")

            if match_response and isinstance(match_response, dict) and match_response.get("MatchID"):
                match_data = self.Requests.fetch(url_type="glz",
                    endpoint=f"/core-game/v1/matches/{match_response['MatchID']}", method="get")

                if match_data and "Players" in match_data:
                    return [{"puuid": p["Subject"], "private": "", "product": "valorant", "game_state": "INGAME"}
                            for p in match_data["Players"]]

            pregame_response = self.Requests.fetch(url_type="glz",
                endpoint=f"/pregame/v1/players/{self.Requests.puuid}", method="get")

            if pregame_response and isinstance(pregame_response, dict) and pregame_response.get("MatchID"):
                pregame_data = self.Requests.fetch(url_type="glz",
                    endpoint=f"/pregame/v1/matches/{pregame_response['MatchID']}", method="get")

                if pregame_data and "AllyTeam" in pregame_data and "Players" in pregame_data["AllyTeam"]:
                    return [{"puuid": p["Subject"], "private": "", "product": "valorant", "game_state": "PREGAME"}
                            for p in pregame_data["AllyTeam"]["Players"]]

            return [{"puuid": self.Requests.puuid, "private": "", "product": "valorant", "game_state": "MENUS"}]

        except:
            return [{"puuid": self.Requests.puuid, "private": "", "product": "valorant", "game_state": "MENUS"}]

    def get_game_state(self, presences):
        private_presence = self.get_private_presence(presences)
        if private_presence:
            # Temp fix: Riot is swapping between nested and flat API structures.
            # Check for nested structure.
            if "matchPresenceData" in private_presence:
                return private_presence["matchPresenceData"]["sessionLoopState"]
            # Check for flattened structure.
            elif "sessionLoopState" in private_presence:
                return private_presence["sessionLoopState"]
            # Check for fallback mode (Deceive)
            elif "fallback_game_state" in private_presence:
                return private_presence.get("matchPresenceData", {}).get("sessionLoopState")
            else:
                # No known structure found, log and fail
                self.log("ERROR: Unknown presence API structure in 'get_game_state'.")
                return private_presence["matchPresenceData"]["sessionLoopState"]

        if presences and isinstance(presences, list):
            for presence in presences:
                if presence.get('puuid') == self.Requests.puuid and 'game_state' in presence:
                    return presence['game_state']

        return None

    def get_private_presence(self, presences):
        for presence in presences:
            if presence['puuid'] == self.Requests.puuid:
                #preventing vry from crashing when lol is open
                # print(presence)
                # print(presence.get("championId"))
                if presence.get("championId") is not None or presence.get("product") == "league_of_legends":
                    return None
                else:
                    if 'game_state' in presence:
                        return {
                            "matchPresenceData": {"sessionLoopState": presence['game_state']},
                            "partyPresenceData": {"partyState": "DEFAULT"},
                            "provisioningFlow": "Valid",
                            "queueId": "competitive",
                            "fallback_game_state": True
                        }

                    if presence['private'] == "":
                        return None
                    decoded_private = json.loads(base64.b64decode(presence['private']))
                    # Debug
                    # self.log(f"DEBUG: Decoded Private Presence -> {decoded_private}")
                    return decoded_private
        return None

    def decode_presence(self, private):
        if "{" not in str(private) and private is not None and str(private) != "":
            decoded_party_presence = json.loads(base64.b64decode(str(private)).decode("utf-8"))
            if isinstance(decoded_party_presence, dict) and decoded_party_presence.get('isValid'):
                return decoded_party_presence
        return {
            "isValid": False,
            "partyId": 0,
            "partySize": 0,
            "partyVersion": 0,
        }

    def wait_for_presence(self, PlayersPuuids):
        while True:
            presence = self.get_presence()
            for puuid in PlayersPuuids:
                if puuid not in str(presence):
                    time.sleep(1)
                    continue
            break
