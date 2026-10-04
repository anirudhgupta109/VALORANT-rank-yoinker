import argparse, os, sys, time, base64, json
import urllib3
import requests
from requests.exceptions import ConnectionError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_all_agents():
    print("[INSTALOCKER] Fetching agents from API...")
    try:
        response = requests.get("https://valorant-api.com/v1/agents?isPlayableCharacter=true")
        response.raise_for_status()
        data = response.json()["data"]
        agents = {agent["displayName"].lower(): agent["uuid"] for agent in data}
        return agents
    except Exception as e:
        print(f"Failed to fetch agents: {e}")
        sys.exit(1)

def get_all_maps():
    print("[INSTALOCKER] Fetching maps from API...")
    try:
        response = requests.get("https://valorant-api.com/v1/maps")
        response.raise_for_status()
        data = response.json()["data"]
        maps = {m["mapUrl"]: m["displayName"].lower() for m in data}
        return maps
    except Exception as e:
        print(f"Failed to fetch maps: {e}")
        return {}

class Requests:
    def __init__(self):
        self.headers = {}
        self.lockfile = self.get_lockfile()
        region_info = self.get_region()
        if not region_info:
            print("Failed to get region from logs.")
            sys.exit(1)
        self.pd_url = f"https://pd.{region_info[0]}.a.pvp.net"
        self.glz_url = f"https://glz-{region_info[1][0]}.{region_info[1][1]}.a.pvp.net"
        self.region = region_info[0]
        self.puuid = ''
        
        if not self.get_headers():
            print("Failed to initialize API headers.")
            sys.exit(1)

    def get_lockfile(self):
        path = os.path.join(os.getenv('LOCALAPPDATA'), R'Riot Games\Riot Client\Config\lockfile')
        if not os.path.exists(path):
            print("Lockfile not found. Make sure VALORANT is running.")
            sys.exit(1)
        with open(path) as lockfile:
            data = lockfile.read().split(':')
            keys = ['name', 'PID', 'port', 'password', 'protocol']
            return dict(zip(keys, data))

    def get_region(self):
        path = os.path.join(os.getenv('LOCALAPPDATA'), R'VALORANT\Saved\Logs\ShooterGame.log')
        if not os.path.exists(path): return None
        with open(path, "r", encoding="utf8") as file:
            lines = file.readlines()
            pd_url = None
            glz_url = None
            for line in reversed(lines):
                if '.a.pvp.net/account-xp/v1/' in line and pd_url is None:
                    pd_url = line.split('.a.pvp.net/account-xp/v1/')[0].split('.')[-1]
                elif 'https://glz' in line and glz_url is None:
                    glz_url = [(line.split('https://glz-')[1].split(".")[0]),
                               (line.split('https://glz-')[1].split(".")[1])]
                if pd_url and glz_url:
                    break
            if pd_url and glz_url:
                if pd_url == "pbe":
                    return ["na", "na-1", "na"]
                return [pd_url, glz_url]
        return None

    def get_current_version(self):
        path = os.path.join(os.getenv('LOCALAPPDATA'), R'VALORANT\Saved\Logs\ShooterGame.log')
        if not os.path.exists(path): return ""
        with open(path, "r", encoding="utf8") as file:
            lines = file.readlines()
            for line in reversed(lines):
                if 'CI server version:' in line:
                    version_without_shipping = line.split('CI server version: ')[1].strip()
                    version = version_without_shipping.split("-")
                    return "-".join(version)
        return ""

    def get_headers(self, refresh=False):
        if self.headers == {} or refresh:
            try_again = True
            while try_again:
                local_headers = {'Authorization': 'Basic ' + base64.b64encode(
                    ('riot:' + self.lockfile['password']).encode()).decode()}
                try:
                    response = requests.get(f"https://127.0.0.1:{self.lockfile['port']}/entitlements/v1/token",
                                            headers=local_headers, verify=False)
                except ConnectionError:
                    print("Connection error, retrying in 1 second...")
                    time.sleep(1)
                    self.lockfile = self.get_lockfile()
                    continue
                entitlements = response.json()
                if entitlements.get("message") == "Entitlements token is not ready yet":
                    try_again = True
                    time.sleep(1)
                elif entitlements.get("message") == "Invalid URI format":
                    try_again = True
                    time.sleep(5)
                else:
                    try_again = False

            self.puuid = entitlements['subject']
            headers = {
                'Authorization': f"Bearer {entitlements['accessToken']}",
                'X-Riot-Entitlements-JWT': entitlements['token'],
                'X-Riot-ClientPlatform': "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjog"
                                         "IldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5"
                                         "MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9",
                'X-Riot-ClientVersion': self.get_current_version(),
                "User-Agent": "ShooterGame/13 Windows/10.0.19043.1.256.64bit"
            }
            self.headers = headers
        return self.headers

    def fetch(self, url_type: str, endpoint: str, method: str):
        try:
            if url_type == "glz":
                response = requests.request(method, self.glz_url + endpoint, headers=self.get_headers(), verify=False)
                if response.status_code == 404:
                    return response.json()
                try:
                    if response.json().get("errorCode") == "BAD_CLAIMS":
                        self.headers = {}
                        return self.fetch(url_type, endpoint, method)
                except json.decoder.JSONDecodeError:
                    pass
                if not response.ok:
                    time.sleep(5)
                    self.headers = {}
                    return self.fetch(url_type, endpoint, method)
                return response.json()
        except Exception as e:
            pass

class Instalocker:
    def __init__(self, agent=None, config_path="instalock_config.json"):
        self.agents = get_all_agents()
        self.maps = get_all_maps()
        
        self.config = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.config = json.load(f)
        else:
            print(f"[INSTALOCKER] No config found at {config_path}")

        if agent:
            self.default_agent = agent.lower()
        else:
            def_ag = self.config.get("default_agent")
            self.default_agent = def_ag.lower() if def_ag else None
            
        if self.default_agent and self.default_agent not in self.agents:
            print(f"Unknown default agent: {self.default_agent}")
            print("Available:", ", ".join(sorted(self.agents.keys())))
            sys.exit(1)
        
        self.requests = Requests()
        self.puuid = self.requests.puuid
        print(f"[INSTALOCKER] Base target: {self.default_agent or 'None'}")

    def run(self):
        print(f"[INSTALOCKER] Waiting for match...")
        current_match = None
        while True:
            pregame = self.requests.fetch("glz", f"/pregame/v1/players/{self.puuid}", "get")
            if pregame and "MatchID" in pregame:
                if pregame["MatchID"] != current_match:
                    current_match = pregame["MatchID"]
                    
                    match_details = self.requests.fetch("glz", f"/pregame/v1/matches/{current_match}", "get")
                    map_url = match_details.get("MapID", "") if match_details else ""
                    map_name = self.maps.get(map_url, "unknown")
                    
                    print(f"[INSTALOCKER] Match found! Map: {map_name.capitalize()}")
                    
                    target_agent = self.default_agent
                    if self.config and "maps" in self.config:
                        target_agent = self.config["maps"].get(map_name, self.default_agent)
                        
                    if target_agent:
                        target_agent = target_agent.lower()
                        uuid = self.agents.get(target_agent)
                        if not uuid:
                            print(f"[INSTALOCKER] Invalid agent '{target_agent}'. Falling back to default.")
                            target_agent = self.default_agent
                            uuid = self.agents.get(target_agent) if target_agent else None
                    else:
                        uuid = None
                    
                    if uuid:
                        print(f"[INSTALOCKER] Locking {target_agent}...")
                        time.sleep(5)
                        self._lock(current_match, uuid, target_agent)
                        print(f"[INSTALOCKER] Locked! Waiting 30s before next match...")
                        time.sleep(30)
                        current_match = None
                    else:
                        print(f"[INSTALOCKER] No agent configured for {map_name.capitalize()}. Skipping instalock.")
            else:
                current_match = None
            time.sleep(0.25)

    def _lock(self, match_id, uuid, agent_name):
        self.requests.fetch("glz", f"/pregame/v1/matches/{match_id}/select/{uuid}", "post")
        time.sleep(1)
        #self.requests.fetch("glz", f"/pregame/v1/matches/{match_id}/lock/{uuid}", "post")
        #print(f"[INSTALOCKER] *** {agent_name.upper()} LOCKED ***")

def main():
    parser = argparse.ArgumentParser(description="VALORANT Python Instalocker (Standalone)")
    parser.add_argument("agent", nargs='?', help="Agent name (e.g., jett). Overrides config default if provided.")
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "instalock_config.json")
    
    try:
        Instalocker(args.agent, config_path).run()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()
