#!/usr/bin/env python3
import argparse, json, os, sys, time
from datetime import datetime
import urllib3

# Add project root to sys.path to allow imports from src
root_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.append(root_path)

from src.requestsV import Requests
from src.constants import version as VRY_VERSION

urllib3.disable_warnings()

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_dump.log")


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")

class MockError:
    def LockfileError(self, path, ignoreLockfile=False):
        if not os.path.exists(path):
            log("Lockfile not found. Make sure VALORANT is running.")
            sys.exit(1)
        return True

class APIDumper:
    def __init__(self):
        self.requests = Requests(VRY_VERSION, log, MockError())
        self.puuid = self.requests.puuid
        self.shared_url = f"https://shared.{self.requests.region}.a.pvp.net"
        
        log(f"[DUMPER] PUUID: {self.puuid}")
        log(f"[DUMPER] PD URL: {self.requests.pd_url}")
        log(f"[DUMPER] GLZ URL: {self.requests.glz_url}")
        log(f"[DUMPER] SHARED URL: {self.shared_url}")
        log(f"[DUMPER] LOCAL URL: https://127.0.0.1:{self.requests.lockfile['port']}")

    def dump_apis(self, state):
        log("="*60)
        log(f"STATE: {state}")
        log("="*60)

        log(f"\n>>> API: https://127.0.0.1:{self.requests.lockfile['port']}/entitlements/v1/token")
        log(f">>> STATE: {state}")
        ent = self.requests.fetch("local", "/entitlements/v1/token", "get")
        log(json.dumps(ent))

        log(f"\n>>> API: /pregame/v1/players/{self.puuid} (GLZ)")
        log(f">>> STATE: {state}")
        pregame_player = self.requests.fetch("glz", f"/pregame/v1/players/{self.puuid}", "get")
        log(json.dumps(pregame_player))

        if state == "PRE-GAME":
            match_id = pregame_player.get("MatchID")
            if match_id:
                log(f"\n>>> API: /pregame/v1/matches/{match_id} (GLZ)")
                log(f">>> STATE: {state}")
                pregame_match = self.requests.fetch("glz", f"/pregame/v1/matches/{match_id}", "get")
                log(json.dumps(pregame_match))

                log(f"\n>>> API: /pregame/v1/matches/{match_id}/loadouts (GLZ)")
                log(f">>> STATE: {state}")
                loadouts = self.requests.fetch("glz", f"/pregame/v1/matches/{match_id}/loadouts", "get")
                log(json.dumps(loadouts))

                all_puuids = [player["Subject"] for player in loadouts.get("Loadouts", [])]
                log(f"\n>>> Found {len(all_puuids)} players in loadouts: {all_puuids}")
                for puuid in all_puuids:
                    log(f"\n>>> API: /account-xp/v1/players/{puuid} (PD)")
                    log(f">>> STATE: {state}")
                    account_xp = self.requests.fetch("pd", f"/account-xp/v1/players/{puuid}", "get").json()
                    log(json.dumps(account_xp))

        log(f"\n>>> API: /core-game/v1/players/{self.puuid} (GLZ)")
        log(f">>> STATE: {state}")
        core_player = self.requests.fetch("glz", f"/core-game/v1/players/{self.puuid}", "get")
        log(json.dumps(core_player))

        log(f"\n>>> API: /core-game/v1/matches (GLZ)")
        log(f">>> STATE: {state}")
        core_matches = self.requests.fetch("glz", "/core-game/v1/matches", "get")
        log(json.dumps(core_matches))

        if state == "CORE-GAME":
            core_match_id = core_player.get("MatchID") or core_player.get("matchId")
            if core_match_id:
                log(f"\n>>> API: /core-game/v1/matches/{core_match_id} (GLZ)")
                log(f">>> STATE: {state}")
                core_match = self.requests.fetch("glz", f"/core-game/v1/matches/{core_match_id}", "get")
                log(json.dumps(core_match))

                log(f"\n>>> API: /core-game/v1/matches/{core_match_id}/loadouts (GLZ)")
                log(f">>> STATE: {state}")
                core_loadouts = self.requests.fetch("glz", f"/core-game/v1/matches/{core_match_id}/loadouts", "get")
                log(json.dumps(core_loadouts))

                all_puuids = [player["Subject"] for player in core_loadouts.get("Loadouts", [])]
                log(f"\n>>> Found {len(all_puuids)} players in core-game loadouts: {all_puuids}")
                for puuid in all_puuids:
                    log(f"\n>>> API: /account-xp/v1/players/{puuid} (PD)")
                    log(f">>> STATE: {state}")
                    account_xp = self.requests.fetch("pd", f"/account-xp/v1/players/{puuid}", "get").json()
                    log(json.dumps(account_xp))

        log(f"\n>>> API: /session/v1/sessions (LOCAL)")
        log(f">>> STATE: {state}")
        session = self.requests.fetch("local", "/session/v1/sessions", "get")
        log(json.dumps(session))

        log(f"\n>>> API: /chat/v4/presences (LOCAL)")
        log(f">>> STATE: {state}")
        presences = self.requests.fetch("local", "/chat/v4/presences", "get")
        log(json.dumps(presences))

        log(f"\n>>> API: /player-account/lookup/v2/namesets-for-puuids (LOCAL)")
        log(f">>> STATE: {state}")
        namesets = self.requests.fetch("local", "/player-account/lookup/v2/namesets-for-puuids", "post", body={"puuids": [self.puuid]})
        log(json.dumps(namesets))

        log(f"\n>>> API: /name-service/v2/players (PD)")
        log(f">>> STATE: {state}")
        try:
            name_service = self.requests.fetch("pd", "/name-service/v2/players", "put", body=[self.puuid]).json()
            log(json.dumps(name_service))
        except:
            log("{}")

        log(f"\n>>> API: /mmr/v1/players/{self.puuid} (PD)")
        log(f">>> STATE: {state}")
        mmr = self.requests.fetch("pd", f"/mmr/v1/players/{self.puuid}", "get").json()
        log(json.dumps(mmr))

        log(f"\n>>> API: /mmr/v1/players/{self.puuid}/leaderboards/Queue/competitive/Season/{self._get_season()} (PD)")
        log(f">>> STATE: {state}")
        try:
            leaderboard = self.requests.fetch("pd", f"/mmr/v1/players/{self.puuid}/leaderboards/Queue/competitive/Season/{self._get_season()}", "get").json()
            log(json.dumps(leaderboard))
        except:
            log("{}")

        log(f"\n>>> API: /account-xp/v1/players/{self.puuid} (PD)")
        log(f">>> STATE: {state}")
        account_xp = self.requests.fetch("pd", f"/account-xp/v1/players/{self.puuid}", "get").json()
        log(json.dumps(account_xp))

        log(f"\n>>> API: /contract-service/v1/players/{self.puuid}/contracts (PD)")
        log(f">>> STATE: {state}")
        contracts = self.requests.fetch("pd", f"/contract-service/v1/players/{self.puuid}/contracts", "get").json()
        log(json.dumps(contracts))

        log(f"\n>>> API: /store/v1/offers (PD)")
        log(f">>> STATE: {state}")
        store_offers = self.requests.fetch("pd", "/store/v1/offers", "get").json()
        log(json.dumps(store_offers))

        log(f"\n>>> API: /store/v1/wallet/{self.puuid} (PD)")
        log(f">>> STATE: {state}")
        wallet = self.requests.fetch("pd", f"/store/v1/wallet/{self.puuid}", "get").json()
        log(json.dumps(wallet))

        log(f"\n>>> API: /content-service/v1/content (SHARED)")
        log(f">>> STATE: {state}")
        content = self.requests.fetch("custom", f"{self.shared_url}/content-service/v1/content", "get")
        log(json.dumps(content))

    def _get_season(self):
        try:
            content = self.requests.fetch("custom", f"{self.shared_url}/content-service/v1/content", "get")
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
                pregame = self.requests.fetch("glz", f"/pregame/v1/players/{self.puuid}", "get")
                core_game = self.requests.fetch("glz", f"/core-game/v1/players/{self.puuid}", "get")

                current_state = None

                if pregame and isinstance(pregame, dict):
                    if "MatchID" in pregame:
                        current_state = "PRE-GAME"
                    elif "error" in pregame:
                        log(f"Pregame error: {pregame}")

                if not current_state and core_game and isinstance(core_game, dict):
                    if any(k.lower() == "matchid" for k in core_game.keys()):
                        current_state = "CORE-GAME"
                    elif "errorCode" in core_game:
                        log(f"Core-game error: {core_game}")

                if not current_state:
                    current_state = "LOBBY"

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
