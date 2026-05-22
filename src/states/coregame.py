import time
from src.constants import PARTYICONLIST, hide_names, hide_levels


class Coregame:
    def __init__(self, Requests, log):
        self.log = log

        self.Requests = Requests

        self.response = ""

    def get_coregame_match_id(self):
        try:
            self.response = self.Requests.fetch(url_type="glz",
                                                endpoint=f"/core-game/v1/players/{self.Requests.puuid}",
                                                method="get")
            if self.response.get("errorCode") == "RESOURCE_NOT_FOUND":
                return 0
            match_id = self.response['MatchID']
            self.log(f"retrieved coregame match id: '{match_id}'")
            return match_id
        except (KeyError, TypeError):
            self.log(f"cannot find coregame match id: ")
            # print(f"No match id found. {self.response}")
            time.sleep(5)
            try:
                self.response = self.Requests.fetch(url_type="glz",
                                                    endpoint=f"/core-game/v1/players/{self.Requests.puuid}",
                                                    method="get")
                match_id = self.response['MatchID']
                self.log(f"retrieved coregame match id: '{match_id}'")
                return match_id
            except (KeyError, TypeError):
                self.log(f"cannot find coregame match id: ")
                print(f"No match id found. {self.response}")
            return 0

    def get_coregame_stats(self):
        self.match_id = self.get_coregame_match_id()
        if self.match_id != 0:
            return self.Requests.fetch(url_type="glz",
                                       endpoint=f"/core-game/v1/matches/{self.match_id}",
                                       method="get")
        else:
            return None

    def get_current_map(self, map_urls, map_splashes) -> dict:
        """
        Abstracts get_coregame_stats() to get the current map name and splash.
        :return: Dictionary of appropriate name and splash.
        """
        coregame_stats = self.get_coregame_stats()

        if coregame_stats is None:
            return 'N/A'

        current_map = map_urls.get(coregame_stats['MapID'].lower())
        return {'name': current_map, 'splash': map_splashes[current_map]}

    def process(self, coregame_stats, coregame_match_id, map_urls, namesClass, presences, menu, match_cache, cfg, rpc, colors, Ranks, table, heartbeat_data, richConsole, color, agent_dict, format_last_active, loadoutsClass, Wss, valoApiSkins, stats, format_heartbeat_player, format_player_stats, get_player_name_color):
        match_cache.ensure_cache(coregame_match_id)
        Players = coregame_stats["Players"]
        # data for chat to function
        presence = presences.get_presence()
        partyMembers = menu.get_party_members(self.Requests.puuid, presence)
        partyMembersList = [a["Subject"] for a in partyMembers]

        players_data = {}
        players_data.update({"ignore": partyMembersList})
        for player in Players:
            if player["Subject"] == self.Requests.puuid:
                if cfg.get_feature_flag("discord_rpc"):
                    rpc.set_data({"agent": player["CharacterID"]})
            players_data.update(
                {
                    player["Subject"]: {
                        "team": player["TeamID"],
                        "agent": player["CharacterID"],
                        "streamer_mode": player["PlayerIdentity"]["Incognito"],
                    }
                }
            )
        Wss.set_player_data(players_data)

        server = coregame_stats.get("GamePodID", "")
        map_id = coregame_stats.get("MapID", "").lower()
        current_map_name = map_urls.get(map_id)
        presences.wait_for_presence(namesClass.get_players_puuid(Players))
        names = namesClass.get_names_from_puuids(Players)
        loadouts_arr = loadoutsClass.get_match_loadouts(
            coregame_match_id,
            Players,
            cfg.weapon,
            valoApiSkins,
            names,
            state="game",
        )
        loadouts = loadouts_arr[0]
        loadouts_data = loadouts_arr[1]
        
        isRange = False
        playersLoaded = 1
        is_leaderboard_needed = False

        heartbeat_data["map"] = (map_urls[coregame_stats["MapID"].lower()],)
        with richConsole.status("Loading Players...") as status:
            partyOBJ = menu.get_party_json(
                namesClass.get_players_puuid(Players), presence
            )
            # log(f"retrieved names dict: {names}")
            Players.sort(
                key=lambda Players: Players["PlayerIdentity"].get(
                    "AccountLevel"
                ),
                reverse=True,
            )
            Players.sort(key=lambda Players: Players["TeamID"], reverse=True)
            partyCount = 0
            partyNum = 0
            partyIcons = {}
            lastTeamBoolean = False
            lastTeam = "Red"

            already_played_with = []
            stats_data = stats.read_data()

            for p in Players:
                if p["Subject"] == self.Requests.puuid:
                    allyTeam = p["TeamID"]
                    break
            for player in Players:
                # used to change player name color
                already_seen = False
                status.update(
                    f"Loading players... [{playersLoaded}/{len(Players)}]"
                )
                playersLoaded += 1

                if player["Subject"] in stats_data.keys():
                    if (
                        player["Subject"] != self.Requests.puuid
                        and player["Subject"] not in partyMembersList
                    ):
                        curr_player_stat = stats_data[player["Subject"]][-1]
                        i = 1
                        while (
                            curr_player_stat["match_id"] == self.match_id
                            and len(stats_data[player["Subject"]]) > i
                        ):
                            i += 1
                            curr_player_stat = stats_data[player["Subject"]][-i]
                        if curr_player_stat["match_id"] != self.match_id:
                            # checking for party memebers and self players
                            times = 0
                            m_set = ()
                            for m in stats_data[player["Subject"]]:
                                if (
                                    m["match_id"] != self.match_id
                                    and m["match_id"] not in m_set
                                ):
                                    times += 1
                                    m_set += (m["match_id"],)
                            
                            if player["PlayerIdentity"]["Incognito"] == False or hide_names == False:
                                already_played_with.append(
                                    {
                                        "times": times,
                                        "name": curr_player_stat["name"],
                                        "agent": curr_player_stat["agent"],
                                        "time_diff": time.time()
                                        - curr_player_stat["epoch"],
                                    }
                                )
                                # used to change player name color
                                already_seen = True
                            else:
                                if player["TeamID"] == allyTeam:
                                    team_string = "your"
                                else:
                                    team_string = "enemy"
                                already_played_with.append(
                                    {
                                        "times": times,
                                        "name": agent_dict.get(
                                            player["CharacterID"].lower(), "Unknown"
                                        )
                                        + " on "
                                        + team_string
                                        + " team",
                                        "agent": curr_player_stat["agent"],
                                        "time_diff": time.time()
                                        - curr_player_stat["epoch"],
                                    }
                                )
                                # used to change player name color
                                already_seen = True

                party_icon = ""
                # set party premade icon
                for party in partyOBJ:
                    if player["Subject"] in partyOBJ[party]:
                        if party not in partyIcons:
                            partyIcons.update(
                                {party: PARTYICONLIST[partyCount]}
                            )
                            # PARTY_ICON
                            party_icon = PARTYICONLIST[partyCount]
                            partyNum = partyCount + 1
                            partyCount += 1
                        else:
                            # PARTY_ICON
                            party_icon = partyIcons[party]
                playerRank, previousPlayerRank, ppstats = match_cache.get_or_fetch(
                    player["Subject"], coregame_match_id
                )

                if player["Subject"] == self.Requests.puuid:
                    if cfg.get_feature_flag("discord_rpc"):
                        rpc.set_data(
                            {
                                "rank": playerRank["rank"],
                                "rank_name": colors.escape_ansi(
                                    Ranks[playerRank["rank"]]
                                )
                                + " | "
                                + str(playerRank["rr"])
                                + "rr",
                            }
                        )

                stats_fmt = format_player_stats(playerRank, previousPlayerRank, ppstats, colors, Ranks, cfg)

                last_active = format_last_active(ppstats.get("LastActiveEpoch"))

                player_level = player["PlayerIdentity"].get("AccountLevel")

                Namecolor = get_player_name_color(player, names[player["Subject"]], self.Requests.puuid, colors, partyMembersList, played_before=already_seen)

                if lastTeam != player["TeamID"]:
                    if lastTeamBoolean:
                        table.add_empty_row()
                lastTeam = player["TeamID"]
                lastTeamBoolean = True
                if player["PlayerIdentity"]["HideAccountLevel"]:
                    if (
                        player["Subject"] == self.Requests.puuid
                        or player["Subject"] in partyMembersList
                        or hide_levels == False
                    ):
                        PLcolor = colors.level_to_color(player_level)
                    else:
                        PLcolor = ""
                else:
                    PLcolor = colors.level_to_color(player_level)
                # AGENT
                # agent = str(agent_dict.get(player["CharacterID"].lower()))
                agent = colors.get_agent_from_uuid(
                    player["CharacterID"].lower()
                )
                if agent == "" and len(Players) == 1:
                    isRange = True

                # NAME
                name = Namecolor

                # skin
                skin = loadouts.get(player["Subject"], "")

                # LEADERBOARD
                leaderboard = playerRank["leaderboard"]

                if int(leaderboard) > 0:
                    is_leaderboard_needed = True

                # LEVEL
                level = PLcolor
                table.add_row_table(
                    [
                        party_icon,
                        agent,
                        name,
                        skin,
                        stats_fmt["rankName"],
                        playerRank["rr"],
                        stats_fmt["peakRank"],
                        stats_fmt["previousRank"],
                        leaderboard,
                        stats_fmt["hs"],
                        stats_fmt["wr"],
                        ppstats["kd"],
                        level,
                        stats_fmt["rr_earned"],
                        last_active,
                    ]
                )

                heartbeat_data["players"][player["Subject"]] = format_heartbeat_player(
                    names[player["Subject"]],
                    playerRank,
                    stats_fmt["peakRankAct"],
                    player_level,
                    ppstats,
                    last_active,
                    party_num=partyNum if party_icon != "" else 0,
                    agent=agent_dict.get(player["CharacterID"].lower(), "Unknown"),
                    puuid=player["Subject"],
                    loadout_player_data=loadouts_data["Players"][player["Subject"]]
                )

                stats.save_data(
                    {
                        player["Subject"]: {
                            "name": names[player["Subject"]],
                            "agent": agent_dict.get(player["CharacterID"].lower(), "Unknown"),
                            "map": current_map_name,
                            "rank": playerRank["rank"],
                            "rr": playerRank["rr"],
                            "match_id": self.match_id,
                            "epoch": time.time(),
                        }
                    }
                )
        return is_leaderboard_needed, already_played_with, server, current_map_name, isRange

