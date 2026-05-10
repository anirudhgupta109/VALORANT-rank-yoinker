import requests
from src.constants import hide_names


class Names:

    def __init__(self, Requests, log):
        self.Requests = Requests
        self.log = log

    def get_name_from_puuid(self, puuid):
        names = self.get_multiple_names_from_puuid([puuid])
        return names.get(puuid, "")

    def _fetch_names_local(self, puuids):
        response = self.Requests.fetch(url_type="local", endpoint="/player-account/lookup/v2/namesets-for-puuids", method="post", body={"puuids": puuids})
        if response and response.get("namesets"):
            return {item["puuid"]: f"{item['alias']['gameName']}#{item['alias']['tagLine']}" for item in response["namesets"] if item.get("alias", {}).get("gameName")}
        return {}

    def get_multiple_names_from_puuid(self, puuids):
        name_dict = self._fetch_names_local(puuids)
        failed_puuids = [p for p in puuids if p not in name_dict]

        if failed_puuids:
            try:
                pd_response = requests.put(self.Requests.pd_url + "/name-service/v2/players", headers=self.Requests.get_headers(), json=failed_puuids, verify=False)
                if pd_response.ok and 'errorCode' not in pd_response.json():
                    name_dict.update({p["Subject"]: f"{p['GameName']}#{p['TagLine']}" for p in pd_response.json() if p.get("GameName")})
            except Exception as e:
                self.log(f"PD API lookup failed: {e}")

        return name_dict

    def _get_hidden_names(self, puuids):
        return self.get_multiple_names_from_puuid(puuids)

    def get_names_from_puuids(self, players):
        return self.get_multiple_names_from_puuid([p["Subject"] for p in players])

    def get_players_puuid(self, Players):
        return [p["Subject"] for p in Players]