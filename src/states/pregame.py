from src.constants import PARTYICONLIST, hide_names, hide_levels


class Pregame:
    def __init__(self, Requests, log):
        self.log = log

        self.Requests = Requests

        self.response = ""



    def get_pregame_match_id(self):
        global response
        try:
            response = self.Requests.fetch(url_type="glz", endpoint=f"/pregame/v1/players/{self.Requests.puuid}", method="get")
            if response.get("errorCode") == "RESOURCE_NOT_FOUND":
                return 0
            match_id = response['MatchID']
            self.log(f"retrieved pregame match id: '{match_id}'")
            return match_id
        except (KeyError, TypeError):
            self.log(f"cannot find pregame match id: {response}")
            # print(f"No match id found. {response}")
            try:
                self.response = self.Requests.fetch(url_type="glz", endpoint=f"/pregame/v1/players/{self.Requests.puuid}", method="get")
                match_id = self.response['MatchID']
                self.log(f"retrieved pregame match id: '{match_id}'")
                return match_id
            except (KeyError, TypeError):
                self.log(f"cannot find pregame match id: ")
                print(f"No match id found. {self.response}")
            return 0

    def get_pregame_stats(self):
        match_id = self.get_pregame_match_id()
        if match_id != 0:
            return self.Requests.fetch("glz", f"/pregame/v1/matches/{match_id}", "get")
        else:
            return None

    def process(self, pregame_stats, map_urls, namesClass, presences, menu, match_cache, cfg, rpc, colors, Ranks, table, heartbeat_data, richConsole, color, agent_dict, format_last_active, loadoutsClass, format_heartbeat_player, format_player_stats, get_player_name_color):
        server = pregame_stats.get("GamePodID", "")
        map_id = pregame_stats.get("MapID", "").lower()
        current_map_name = map_urls.get(map_id)
        Players = pregame_stats["AllyTeam"]["Players"]
        for p in Players: p["TeamID"] = pregame_stats["AllyTeam"]["TeamID"]
        pregame_match_id = pregame_stats.get("ID")

        # utilize loadouts API for name extraction (enemy discovery)
        try:
            pregame_loadouts = loadoutsClass.get_pregame_loadouts(pregame_match_id)
            ally_puuids = [p["Subject"] for p in Players]
            enemy_team_id = "Red" if pregame_stats["AllyTeam"]["TeamID"] == "Blue" else "Blue"
            for l in pregame_loadouts.get("Loadouts", []):
                if l["Subject"] not in ally_puuids:
                    Players.append({"Subject": l["Subject"], "CharacterID": "", "CharacterSelectionState": "", "PlayerIdentity": {"AccountLevel": 0, "Incognito": False, "HideAccountLevel": True}, "TeamID": enemy_team_id})
        except: pass

        presences.wait_for_presence(namesClass.get_players_puuid(Players))
        names = namesClass.get_names_from_puuids(Players)
        
        playersLoaded = 1
        is_leaderboard_needed = False
        with richConsole.status("Loading Players...") as status:
            presence = presences.get_presence()
            partyOBJ = menu.get_party_json(
                namesClass.get_players_puuid(Players), presence
            )
            partyMembers = menu.get_party_members(self.Requests.puuid, presence)
            partyMembersList = [a["Subject"] for a in partyMembers]
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
            for player in Players:
                status.update(
                    f"Loading players... [{playersLoaded}/{len(Players)}]"
                )
                playersLoaded += 1
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
                        else:
                            # PARTY_ICON
                            party_icon = partyIcons[party]
                        partyCount += 1
                playerRank, previousPlayerRank, ppstats = match_cache.get_or_fetch(
                    player["Subject"], pregame_match_id
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
                
                NameColor = get_player_name_color(player, names[player["Subject"]], self.Requests.puuid, colors, partyMembersList)

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
                if player["CharacterSelectionState"] == "locked":
                    agent_color = color(
                        agent_dict.get(player["CharacterID"].lower(), "Unknown"),
                        fore=(255, 255, 255),
                    )
                elif player["CharacterSelectionState"] == "selected":
                    agent_color = color(
                        agent_dict.get(player["CharacterID"].lower(), "Unknown"),
                        fore=(128, 128, 128),
                    )
                else:
                    agent_color = color(
                        agent_dict.get(player["CharacterID"].lower(), "Unknown"),
                        fore=(54, 53, 51),
                    )

                # AGENT
                agent = agent_color

                # NAME
                name = NameColor

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
                        "",
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
                    agent=agent_dict.get(player["CharacterID"].lower(), "Unknown")
                )
        return is_leaderboard_needed, server, current_map_name

