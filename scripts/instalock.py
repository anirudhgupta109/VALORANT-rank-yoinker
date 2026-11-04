#!/usr/bin/env python3
import argparse, os, sys, time
import urllib3

# Add project root to sys.path to allow imports from src
root_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.append(root_path)

from src.requestsV import Requests
from src.content import Content
from src.constants import version as VRY_VERSION

urllib3.disable_warnings()

class MockError:
    def LockfileError(self, path, ignoreLockfile=False):
        if not os.path.exists(path):
            print("Lockfile not found. Make sure VALORANT is running.")
            sys.exit(1)
        return True

class Instalocker:
    def __init__(self, agent):
        self.agent = agent.lower()

        content = Content(None, lambda x: None)
        try:
            agent_dict = content.get_all_agents()
        except Exception as e:
            print(f"Failed to fetch agents: {e}")
            sys.exit(1)

        agents_by_name = {
            name.lower(): uuid
            for uuid, name in agent_dict.items()
            if name and uuid
        }
        for uuid, name in agent_dict.items():
            if name and "/" in name:
                agents_by_name[name.lower().replace("/", "")] = uuid

        self.uuid = agents_by_name.get(self.agent)
        if not self.uuid:
            print(f"Unknown agent: {agent}")
            available = sorted({name.lower() for name in agent_dict.values() if name})
            print("Available:", ", ".join(available))
            sys.exit(1)
        
        # Requests(version, log_function, Error_class)
        self.requests = Requests(VRY_VERSION, lambda x: None, MockError())
        self.puuid = self.requests.puuid
        print(f"[INSTALOCKER] Target: {self.agent}")

    def run(self):
        print(f"[INSTALOCKER] Waiting for match...")
        current_match = None
        while True:
            pregame = self.requests.fetch("glz", f"/pregame/v1/players/{self.puuid}", "get")
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
        self.requests.fetch("glz", f"/pregame/v1/matches/{match_id}/select/{self.uuid}", "post")
        time.sleep(1)
        #self.requests.fetch("glz", f"/pregame/v1/matches/{match_id}/lock/{self.uuid}", "post")
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
