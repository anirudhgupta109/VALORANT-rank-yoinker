from src.constants import PARTYICONLIST


class Menu:
    def __init__(self, Requests, log, presences):
        self.Requests = Requests
        self.log = log
        self.presences = presences

    def get_party_json(self, GamePlayersPuuid, presencesDICT):
        party_json = {}
        for presence in presencesDICT:
            if presence["puuid"] in GamePlayersPuuid:
                decodedPresence = self.presences.decode_presence(presence["private"])
                if decodedPresence["isValid"]:
                    
                    # Temp fix: Riot is swapping between nested and flat API structures.
                    party_size = 0
                    party_id = ""
                    if "partyPresenceData" in decodedPresence: # Check for nested structure
                        party_size = decodedPresence["partyPresenceData"]["partySize"]
                        party_id = decodedPresence["partyPresenceData"]["partyId"]
                    elif "partySize" in decodedPresence: # Check for flattened structure
                        party_size = decodedPresence["partySize"]
                        party_id = decodedPresence["partyId"]
                    else:
                        # No known structure found, log and fail
                        self.log("ERROR: Unknown presence API structure in 'get_party_json'.")
                        party_id = decodedPresence["partyPresenceData"]["partyId"]

                    if party_size > 1:
                        try:
                            party_json[party_id].append(presence["puuid"])
                        except KeyError:
                            party_json.update({party_id: [presence["puuid"]]})

        #remove non-in-game parties from with one player in game
        parties_to_delete = []
        for party in party_json:
            if len(party_json[party]) == 1:
                parties_to_delete.append(party)
        for party in parties_to_delete:
            del party_json[party]

        self.log(f"retrieved party json: {party_json}")
        return party_json

    def get_party_members(self, self_puuid, presencesDICT):
        res = []
        party_id = ""

        fallback_mode = False

        for presence in presencesDICT:
            if presence["puuid"] == self_puuid:
                if presence.get("private") == "" and presence.get("product") == "valorant":
                    fallback_mode = True
                    break
                decodedPresence = self.presences.decode_presence(presence["private"])
                if decodedPresence["isValid"]:
                    
                    # Temp fix: Riot is swapping between nested and flat API structures.
                    account_level = 0
                    if "partyPresenceData" in decodedPresence: # Check for nested structure
                        party_id = decodedPresence["partyPresenceData"]["partyId"]
                        account_level = decodedPresence["playerPresenceData"]["accountLevel"]
                    elif "partyId" in decodedPresence: # Check for flattened structure
                        party_id = decodedPresence["partyId"]
                        account_level = decodedPresence["accountLevel"]
                    else:
                        # No known structure found, log and fail
                        self.log("ERROR: Unknown presence API structure in 'get_party_members' (self).")
                        party_id = decodedPresence["partyPresenceData"]["partyId"]
                        
                    res.append({"Subject": presence["puuid"], "PlayerIdentity": {"AccountLevel": account_level}})

        if fallback_mode:
            self.log("get_party_members: Using fallback mode - returning self only")
            res.append({"Subject": self_puuid, "PlayerIdentity": {"AccountLevel": 0}})
            return res

        # Find other party members
        for presence in presencesDICT:
            if presence["puuid"] == self_puuid:
                continue # Skip self

            if presence.get("private") == "" and presence.get("product") == "valorant":
                continue

            decodedPresence = self.presences.decode_presence(presence["private"])
            if decodedPresence["isValid"]:
                
                # Temp fix: Riot is swapping between nested and flat API structures.
                current_party_id = ""
                account_level = 0
                if "partyPresenceData" in decodedPresence: # Check for nested structure
                    current_party_id = decodedPresence["partyPresenceData"]["partyId"]
                    account_level = decodedPresence["playerPresenceData"]["accountLevel"]
                elif "partyId" in decodedPresence: # Check for flattened structure
                    current_party_id = decodedPresence["partyId"]
                    account_level = decodedPresence["accountLevel"]
                else:
                    # No known structure found, log and fail
                    self.log("ERROR: Unknown presence API structure in 'get_party_members'.")
                    current_party_id = decodedPresence["partyPresenceData"]["partyId"]

                if current_party_id == party_id:
                    res.append({"Subject": presence["puuid"], "PlayerIdentity": {"AccountLevel": account_level}})
                    
        self.log(f"retrieved party members: {res}")
        return res

    def process(self, presence, namesClass, rank, seasonID, previousSeasonID, pstats, cfg, colors, Ranks, table, rpc, heartbeat_data, richConsole, color, format_heartbeat_player, format_player_stats):
        Players = self.get_party_members(self.Requests.puuid, presence)
        names = namesClass.get_names_from_puuids(Players)
        playersLoaded = 1
        is_leaderboard_needed = False
        with richConsole.status("Loading Players...") as status:
            Players.sort(
                key=lambda Players: Players["PlayerIdentity"].get(
                    "AccountLevel"
                ),
                reverse=True,
            )
            seen = []
            for player in Players:

                if player["Subject"] not in seen:
                    status.update(
                        f"Loading players... [{playersLoaded}/{len(Players)}]"
                    )
                    playersLoaded += 1
                    party_icon = PARTYICONLIST[0]
                    playerRank = rank.get_rank(player["Subject"], seasonID)
                    previousPlayerRank = rank.get_rank(
                        player["Subject"], previousSeasonID
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

                    ppstats = pstats.get_stats(player["Subject"])
                    
                    stats_fmt = format_player_stats(playerRank, previousPlayerRank, ppstats, colors, Ranks, cfg)

                    last_active = ""

                    player_level = player["PlayerIdentity"].get("AccountLevel")
                    PLcolor = colors.level_to_color(player_level)

                    # AGENT
                    agent = ""

                    # NAME
                    name = color(names[player["Subject"]], fore=(76, 151, 237))

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
                        ""
                    )
                    seen.append(player["Subject"])
        return is_leaderboard_needed



