#!/usr/bin/env python3
import argparse, base64, json, os, sys, time, requests
import urllib3
urllib3.disable_warnings()

CLIENT_PLATFORM = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"

AGENTS = {
    "jett": "add6443a-41bd-e414-f6ad-e58d267f4e95",
    "phoenix": "eb93336a-449b-9c1b-0a54-a891f7921d69",
    "sage": "569fdd95-4d10-43ab-ca70-79becc718b46",
    "sova": "320b2a48-4d9b-a075-30f1-1f93a9b638fa",
    "viper": "707eab51-4836-f488-046a-cda6bf494859",
    "cypher": "117ed9e3-49f3-6512-3ccf-0cada7e3823b",
    "omen": "8e253930-4c05-31dd-1b6c-968525494517",
    "reyna": "a3bfb853-43b2-7238-a4f1-ad90e9e46bcc",
    "raze": "f94c3b30-42be-e959-889c-5aa313dba261",
    "breach": "5f8d3a7f-467b-97f3-062c-13acf203c006",
    "killjoy": "1e58de9c-4950-5125-93e9-a0aee9f98746",
    "brimstone": "9f0d8ba9-4140-b941-57d3-a7ad57c6b417",
    "astra": "41fb69c1-4189-7b37-f117-bcaf1e96f1bf",
    "skye": "6f2a04ca-43e0-be17-7f36-b3908627744d",
    "yoru": "7f94d92c-4234-0a36-9646-3a87eb8b5c89",
    "chamber": "22697a3d-45bf-8dd7-4fec-84a9e28c69d7",
    "harbor": "95b78ed7-4637-86d9-7e41-71ba8c293152",
    "neon": "bb2a4828-46eb-8cd1-e765-15848195d751",
    "fade": "dade69b4-4f5a-8528-247b-219e5a1facd6",
    "kay/o": "601dbbe7-43ce-be57-2a40-4abd24953621",
    "gekko": "e370fa57-4757-3604-3648-499e1f642d3f",
    "iso": "0e38b510-41a8-5780-5e8f-568b2a4f2d6c",
    "clove": "1dbf2edd-4729-0984-3115-daa5eed44993",
    "deadlock": "cc8b64c8-4b25-4ff9-6e7f-37b4da43d235",
    "vyse": "efba5359-4016-a1e5-7626-b1ae76895940",
    "tejo": "b444168c-4e35-8076-db47-ef9bf368f384",
    "waylay": "df1cb487-4902-002e-5c17-d28e83e78588",
    "miks": "7c8a4701-4de6-9355-b254-e09bc2a34b72",
}

class Instalocker:
    def __init__(self, agent):
        self.agent = agent.lower()
        self.uuid = AGENTS.get(self.agent)
        if not self.uuid:
            print(f"Unknown agent: {agent}")
            print("Available:", ", ".join(sorted(AGENTS.keys())))
            sys.exit(1)
        self.headers = {}
        self.puuid = ""
        self.glz_url = ""
        self.lockfile = self._get_lockfile()
        self._init()

    def _get_lockfile(self):
        path = os.path.join(os.getenv('LOCALAPPDATA'), r'Riot Games\Riot Client\Config\lockfile')
        if not os.path.exists(path):
            print("Lockfile not found. Make sure VALORANT is running.")
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
            print("Could not determine region from logs.")
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
        print("Failed to get entitlements.")
        sys.exit(1)

    def _init(self):
        pd, glz = self._get_region()
        self.glz_url = f"https://glz-{glz[0]}.{glz[1]}.a.pvp.net"
        
        ent = self._get_entitlements()
        self.puuid = ent['subject']
        self.headers = {
            'Authorization': f"Bearer {ent['accessToken']}",
            'X-Riot-Entitlements-JWT': ent['token'],
            'X-Riot-ClientPlatform': CLIENT_PLATFORM,
            'X-Riot-ClientVersion': self._get_version(),
            "User-Agent": "ShooterGame/13 Windows/10.0.19043.1.256.64bit"
        }
        print(f"[INSTALOCKER] Target: {self.agent}")

    def _refresh(self):
        ent = self._get_entitlements()
        self.headers = {
            'Authorization': f"Bearer {ent['accessToken']}",
            'X-Riot-Entitlements-JWT': ent['token'],
            'X-Riot-ClientPlatform': CLIENT_PLATFORM,
            'X-Riot-ClientVersion': self._get_version(),
            "User-Agent": "ShooterGame/13 Windows/10.0.19043.1.256.64bit"
        }

    def _fetch(self, endpoint, method="get", body=None, retry=True):
        r = requests.request(method, self.glz_url + endpoint, headers=self.headers, json=body, verify=False, timeout=10)
        if r.status_code == 404:
            return None
        if not r.ok:
            data = r.json()
            if data.get("errorCode") == "BAD_CLAIMS" and retry:
                self._refresh()
                return self._fetch(endpoint, method, body, retry=False)
            return data
        return r.json()

    def run(self):
        print(f"[INSTALOCKER] Waiting for match...")
        current_match = None
        while True:
            pregame = self._fetch(f"/pregame/v1/players/{self.puuid}")
            if pregame and "MatchID" in pregame:
                if pregame["MatchID"] != current_match:
                    current_match = pregame["MatchID"]
                    print(f"[INSTALOCKER] Match found! Locking {self.agent}...")
                    time.sleep(5)
                    self._lock(current_match)
                    print(f"[INSTALOCKER] Locked! Waiting 30s before next match...")
                    time.sleep(30)
                    current_match = None
            else:
                current_match = None
            time.sleep(0.25)

    def _lock(self, match_id):
        self._fetch(f"/pregame/v1/matches/{match_id}/select/{self.uuid}", "post")
        time.sleep(1)
        self._fetch(f"/pregame/v1/matches/{match_id}/lock/{self.uuid}", "post")
        print(f"[INSTALOCKER] *** {self.agent.upper()} LOCKED ***")

def main():
    parser = argparse.ArgumentParser(description="VALORANT Python Instalocker")
    parser.add_argument("agent", help="Agent name (e.g., jett, sage, neon)")
    args = parser.parse_args()
    try:
        Instalocker(args.agent).run()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()