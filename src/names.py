import requests
from src.constants import hide_names


class Names:

    def __init__(self, Requests, log):
        self.Requests = Requests
        self.log = log

    def get_name_from_puuid(self, puuid):
        response = requests.put(self.Requests.pd_url + "/name-service/v2/players", headers=self.Requests.get_headers(), json=[puuid], verify=False)
        return response.json()[0]["GameName"] + "#" + response.json()[0]["TagLine"]


    def get_multiple_names_from_puuid(self, puuids):
        response = requests.put(self.Requests.pd_url + "/name-service/v2/players", headers=self.Requests.get_headers(), json=puuids, verify=False)

        if 'errorCode' in response.json():
            self.log(f'{response.json()["errorCode"]}, new token retrieved')
            response = requests.put(self.Requests.pd_url + "/name-service/v2/players", headers=self.Requests.get_headers(refresh=True), json=puuids, verify=False)

        hidden_puuids = []
        name_dict = {}
        for player in response.json():
            puuid = player["Subject"]
            if player.get("GameName"):
                name_dict[puuid] = f"{player['GameName']}#{player['TagLine']}"
            else:
                hidden_puuids.append(puuid)
                name_dict[puuid] = ""

        if hidden_puuids and not hide_names:
            name_dict.update(self._get_hidden_names(hidden_puuids))

        return name_dict

    def _get_hidden_names(self, puuids):
        try:
            response = self.Requests.fetch(url_type="local", endpoint="/player-account/lookup/v2/namesets-for-puuids", method="post", body={"puuids": puuids})
            if response:
                return {item["puuid"]: f"{item['alias']['gameName']}#{item['alias']['tagLine']}" for item in response.get("namesets", []) if item.get("alias", {}).get("gameName")}
        except Exception as e:
            self.log(f"Local API lookup failed: {e}")
        return {}

    def get_names_from_puuids(self, players):
        players_puuid = [player["Subject"] for player in players]
        return self.get_multiple_names_from_puuid(players_puuid)

    def get_players_puuid(self, Players):
        return [player["Subject"] for player in Players]
