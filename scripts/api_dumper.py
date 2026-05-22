#!/usr/bin/env python3
import argparse, base64, json, os, sys, time, requests
import urllib3
from datetime import datetime
urllib3.disable_warnings()

CLIENT_PLATFORM = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_dump.log")


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")


class APIDumper:
    def __init__(self):
        self.headers = {}
        self.puuid = ""
        self.glz_url = ""
        self.pd_url = ""
        self.shared_url = ""
        self.local_url = ""
        self.lockfile = self._get_lockfile()
        self._init()

    def _get_lockfile(self):
        path = os.path.join(os.getenv('LOCALAPPDATA'), r'Riot Games\Riot Client\Config\lockfile')
        if not os.path.exists(path):
            log("Lockfile not found. Make sure VALORANT is running.")
            sys.exit(1)
        with open(path) as f:
            return dict(zip(['name','PID','port','password','protocol'], f.read().split(':')))

    def _get_region(self):
        pd, glz = None, None
        with open(os.path.join(os.getenv('LOCALAPPDATA'), R'VALORANT\Saved\Logs\ShooterGame.log'), encoding="utf8") as f:
            for line in reversed(f.readlines()):
                if '.a.pvp.net/account-xp/v1/' in line and not pd:
                    pd = line.split('.a.pvp.net/account-xp/v1/')[0].split('.')[-1]
                elif 'https://glz' in line and not glz:
                    parts = line.split('https://glz-')[1].split(".")
                    glz = (parts[0], parts[1])
                if pd and glz:
                    break
        if not pd or not glz:
            log("Could not determine region from logs.")
            sys.exit(1)
        return pd, glz

    def _get_version(self):
        with open(os.path.join(os.getenv('LOCALAPPDATA'), R'VALORANT\Saved\Logs\ShooterGame.log'), encoding="utf8") as f:
            for line in reversed(f.readlines()):
                if 'CI server version:' in line:
                    return line.split('CI server version: ')[1].strip()

    def _get_entitlements(self):
        auth = base64.b64encode(f"riot:{self.lockfile['password']}".encode()).decode()
        for _ in range(10):
            r = requests.get(f"https://127.0.0.1:{self.lockfile['port']}/entitlements/v1/token",
                            headers={"Authorization": f"Basic {auth}"}, verify=False, timeout=5)
            data = r.json()
            if "message" not in data:
                return data
            time.sleep(1)
        log("Failed to get entitlements.")
        sys.exit(1)

    def _init(self):
        pd, glz = self._get_region()
        self.pd_url = f"https://pd.{pd}.a.pvp.net"
        self.glz_url = f"https://glz-{glz[0]}.{glz[1]}.a.pvp.net"
        self.shared_url = f"https://shared.{pd}.a.pvp.net"
        self.local_url = f"https://127.0.0.1:{self.lockfile['port']}"

        ent = self._get_entitlements()
        self.puuid = ent['subject']
        self.headers = {
            'Authorization': f"Bearer {ent['accessToken']}",
            'X-Riot-Entitlements-JWT': ent['token'],
            'X-Riot-ClientPlatform': CLIENT_PLATFORM,
            'X-Riot-ClientVersion': self._get_version(),
            "User-Agent": "ShooterGame/13 Windows/10.0.19043.1.256.64bit"
        }
        log(f"[DUMPER] PUUID: {self.puuid}")
        log(f"[DUMPER] PD URL: {self.pd_url}")
        log(f"[DUMPER] GLZ URL: {self.glz_url}")
        log(f"[DUMPER] SHARED URL: {self.shared_url}")
        log(f"[DUMPER] LOCAL URL: {self.local_url}")

    def _refresh(self):
        ent = self._get_entitlements()
        self.headers = {
            'Authorization': f"Bearer {ent['accessToken']}",
            'X-Riot-Entitlements-JWT': ent['token'],
            'X-Riot-ClientPlatform': CLIENT_PLATFORM,
            'X-Riot-ClientVersion': self._get_version(),
            "User-Agent": "ShooterGame/13 Windows/10.0.19043.1.256.64bit"
        }

    def _fetch(self, url, endpoint, method="get", body=None, retry=True):
        try:
            r = requests.request(method, url + endpoint, headers=self.headers, json=body, verify=False, timeout=10)
            if not r.ok:
                data = r.json()
                if data.get("errorCode") == "BAD_CLAIMS" and retry:
                    self._refresh()
                    return self._fetch(url, endpoint, method, body, retry=False)
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def _fetch_local(self, endpoint, method="get", body=None):
        try:
            auth = base64.b64encode(f"riot:{self.lockfile['password']}".encode()).decode()
            r = requests.request(method, f"{self.local_url}{endpoint}",
                                headers={"Authorization": f"Basic {auth}"}, json=body, verify=False, timeout=10)
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def dump_apis(self, state):
        log("="*60)
        log(f"STATE: {state}")
        log("="*60)

        log(f"\n>>> API: https://127.0.0.1:{self.lockfile['port']}/entitlements/v1/token")
        log(f">>> STATE: {state}")
        ent = self._get_entitlements()
        log(json.dumps(ent))

        log(f"\n>>> API: /pregame/v1/players/{self.puuid} (GLZ)")
        log(f">>> STATE: {state}")
        pregame_player = self._fetch(self.glz_url, f"/pregame/v1/players/{self.puuid}")
        log(json.dumps(pregame_player))

        if state == "PRE-GAME":
            match_id = pregame_player.get("MatchID")
            if match_id:
                log(f"\n>>> API: /pregame/v1/matches/{match_id} (GLZ)")
                log(f">>> STATE: {state}")
                pregame_match = self._fetch(self.glz_url, f"/pregame/v1/matches/{match_id}")
                log(json.dumps(pregame_match))

                log(f"\n>>> API: /pregame/v1/matches/{match_id}/loadouts (GLZ)")
                log(f">>> STATE: {state}")
                loadouts = self._fetch(self.glz_url, f"/pregame/v1/matches/{match_id}/loadouts")
                log(json.dumps(loadouts))

                all_puuids = [player["Subject"] for player in loadouts.get("Loadouts", [])]
                log(f"\n>>> Found {len(all_puuids)} players in loadouts: {all_puuids}")
                for puuid in all_puuids:
                    log(f"\n>>> API: /account-xp/v1/players/{puuid} (PD)")
                    log(f">>> STATE: {state}")
                    account_xp = self._fetch(self.pd_url, f"/account-xp/v1/players/{puuid}")
                    log(json.dumps(account_xp))

        log(f"\n>>> API: /core-game/v1/players/{self.puuid} (GLZ)")
        log(f">>> STATE: {state}")
        core_player = self._fetch(self.glz_url, f"/core-game/v1/players/{self.puuid}")
        log(json.dumps(core_player))

        log(f"\n>>> API: /core-game/v1/matches (GLZ)")
        log(f">>> STATE: {state}")
        core_matches = self._fetch(self.glz_url, "/core-game/v1/matches")
        log(json.dumps(core_matches))

        if state == "CORE-GAME":
            core_match_id = core_player.get("MatchID") or core_player.get("matchId")
            if core_match_id:
                log(f"\n>>> API: /core-game/v1/matches/{core_match_id} (GLZ)")
                log(f">>> STATE: {state}")
                core_match = self._fetch(self.glz_url, f"/core-game/v1/matches/{core_match_id}")
                log(json.dumps(core_match))

                log(f"\n>>> API: /core-game/v1/matches/{core_match_id}/loadouts (GLZ)")
                log(f">>> STATE: {state}")
                core_loadouts = self._fetch(self.glz_url, f"/core-game/v1/matches/{core_match_id}/loadouts")
                log(json.dumps(core_loadouts))

                all_puuids = [player["Subject"] for player in core_loadouts.get("Loadouts", [])]
                log(f"\n>>> Found {len(all_puuids)} players in core-game loadouts: {all_puuids}")
                for puuid in all_puuids:
                    log(f"\n>>> API: /account-xp/v1/players/{puuid} (PD)")
                    log(f">>> STATE: {state}")
                    account_xp = self._fetch(self.pd_url, f"/account-xp/v1/players/{puuid}")
                    log(json.dumps(account_xp))

        log(f"\n>>> API: /session/v1/sessions (LOCAL)")
        log(f">>> STATE: {state}")
        session = self._fetch_local("/session/v1/sessions")
        log(json.dumps(session))

        log(f"\n>>> API: /chat/v4/presences (LOCAL)")
        log(f">>> STATE: {state}")
        presences = self._fetch_local("/chat/v4/presences")
        log(json.dumps(presences))

        log(f"\n>>> API: /player-account/lookup/v2/namesets-for-puuids (LOCAL)")
        log(f">>> STATE: {state}")
        namesets = self._fetch_local("/player-account/lookup/v2/namesets-for-puuids", "post", {"puuids": [self.puuid]})
        log(json.dumps(namesets))

        log(f"\n>>> API: /name-service/v2/players (PD)")
        log(f">>> STATE: {state}")
        try:
            name_service = self._fetch(self.pd_url, "/name-service/v2/players", "put", [self.puuid])
            log(json.dumps(name_service))
        except:
            log("{}")

        log(f"\n>>> API: /mmr/v1/players/{self.puuid} (PD)")
        log(f">>> STATE: {state}")
        mmr = self._fetch(self.pd_url, f"/mmr/v1/players/{self.puuid}")
        log(json.dumps(mmr))

        log(f"\n>>> API: /mmr/v1/players/{self.puuid}/leaderboards/Queue/competitive/Season/{self._get_season()} (PD)")
        log(f">>> STATE: {state}")
        try:
            leaderboard = self._fetch(self.pd_url, f"/mmr/v1/players/{self.puuid}/leaderboards/Queue/competitive/Season/{self._get_season()}")
            log(json.dumps(leaderboard))
        except:
            log("{}")

        log(f"\n>>> API: /account-xp/v1/players/{self.puuid} (PD)")
        log(f">>> STATE: {state}")
        account_xp = self._fetch(self.pd_url, f"/account-xp/v1/players/{self.puuid}")
        log(json.dumps(account_xp))

        log(f"\n>>> API: /contract-service/v1/players/{self.puuid}/contracts (PD)")
        log(f">>> STATE: {state}")
        contracts = self._fetch(self.pd_url, f"/contract-service/v1/players/{self.puuid}/contracts")
        log(json.dumps(contracts))

        log(f"\n>>> API: /store/v1/offers (PD)")
        log(f">>> STATE: {state}")
        store_offers = self._fetch(self.pd_url, "/store/v1/offers")
        log(json.dumps(store_offers))

        log(f"\n>>> API: /store/v1/wallet/{self.puuid} (PD)")
        log(f">>> STATE: {state}")
        wallet = self._fetch(self.pd_url, f"/store/v1/wallet/{self.puuid}")
        log(json.dumps(wallet))

        log(f"\n>>> API: /content-service/v1/content (SHARED)")
        log(f">>> STATE: {state}")
        content = self._fetch(self.shared_url, "/content-service/v1/content")
        log(json.dumps(content))

    def _get_season(self):
        try:
            content = self._fetch(self.shared_url, "/content-service/v1/content")
            seasons = content.get("Seasons", [])
            for s in seasons:
                if s.get("IsActive"):
                    return s.get("ID", "")
            return ""
        except:
            return ""

    def run(self):
        log("[DUMPER] Starting monitoring...")
        prev_state = None
        while True:
            try:
                pregame = self._fetch(self.glz_url, f"/pregame/v1/players/{self.puuid}")
                core_game = self._fetch(self.glz_url, f"/core-game/v1/players/{self.puuid}")

                current_state = None

                if pregame and isinstance(pregame, dict):
                    if "MatchID" in pregame:
                        current_state = "PRE-GAME"
                    elif "error" in pregame:
                        log(f"Pregame error: {pregame}")

                if not current_state and core_game and isinstance(core_game, dict):
                    log(f"DEBUG: Checking core_game, keys={list(core_game.keys())}")
                    if any(k.lower() == "matchid" for k in core_game.keys()):
                        current_state = "CORE-GAME"
                    elif "errorCode" in core_game:
                        log(f"Core-game error: {core_game}")

                if not current_state:
                    current_state = "LOBBY"

                log(f"[STATE CHECK] pregame_keys={list(pregame.keys()) if isinstance(pregame, dict) else pregame}, core_keys={list(core_game.keys()) if isinstance(core_game, dict) else core_game}, httpStatus={core_game.get('httpStatus', 'N/A') if isinstance(core_game, dict) else 'N/A'} -> {current_state}")

                if current_state != prev_state:
                    prev_state = current_state
                    log(f"\n*** STATE CHANGED: {current_state} ***")
                    self.dump_apis(current_state)

            except Exception as e:
                log(f"Error in run loop: {e}")

            time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="VALORANT API Dumper - Dump raw API responses")
    args = parser.parse_args()
    try:
        APIDumper().run()
    except KeyboardInterrupt:
        log("\nExiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()