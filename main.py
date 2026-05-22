import asyncio
import os
import sys
import time
import traceback

import requests
import urllib3
from src.colors import color as colr
from InquirerPy import inquirer
from rich.console import Console as RichConsole

from src.colors import Colors
from src.config import Config
from src.configurator import configure
from src.constants import *
from src.content import Content
from src.errors import Error
from src.Loadouts import Loadouts
from src.logs import Logging
from src.names import Names
from src.player_stats import PlayerStats
from src.presences import Presences
from src.rank import Rank
from src.requestsV import Requests
from src.rpc import Rpc
from src.server import Server
from src.states.coregame import Coregame
from src.states.menu import Menu
from src.states.pregame import Pregame
from src.stats import Stats
from src.table import Table
from src.websocket import Ws
from src.os_info import get_os

from src.account_manager.account_manager import AccountManager
from src.account_manager.account_config import AccountConfig
from src.account_manager.account_auth import AccountAuth
from src.utils import get_ip, get_short_server_name, format_last_active, program_exit, format_heartbeat_player, format_player_stats, get_player_name_color
from src.match_cache import MatchCache

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

os.system(f"title VALORANT rank yoinker v{version}")

server = ""
team_side = None

try:
    Logging = Logging()
    log = Logging.log

    # OS Logging
    log(f"Operating system: {get_os()}\n")

    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--config":
            configure()
            run_app = inquirer.confirm(
                message="Do you want to run vRY now?", default=True
            ).execute()
            if run_app:
                os.system("cls")
            else:
                os._exit(0)
        else:
            os.system("cls")
    except Exception as e:
        print("Something went wrong while running configurator!")
        log(f"configurator encountered an error")
        log(str(traceback.format_exc()))
        input("press enter to exit...\n")
        os._exit(1)

    acc_manager = AccountManager(log, AccountConfig, AccountAuth, NUMBERTORANKS)

    ErrorSRC = Error(log, acc_manager)

    Requests.check_version(version, Requests.copy_run_update_script)
    Requests.check_status()
    Requests = Requests(version, log, ErrorSRC)
    log(f"PUUID: {Requests.puuid}")

    cfg = Config(log)

    content = Content(Requests, log)

    rank = Rank(Requests, log, content, before_ascendant_seasons)
    pstats = PlayerStats(Requests, log, cfg)

    namesClass = Names(Requests, log)

    presences = Presences(Requests, log)

    menu = Menu(Requests, log, presences)
    pregame = Pregame(Requests, log)
    coregame = Coregame(Requests, log)

    Server = Server(log, ErrorSRC)
    Server.start_server()

    agent_dict = content.get_all_agents()

    map_info = content.get_all_maps()
    map_urls = content.get_map_urls(map_info)
    map_splashes = content.get_map_splashes(map_info)

    current_map = coregame.get_current_map(map_urls, map_splashes)

    colors = Colors(log, hide_names, agent_dict, AGENTCOLORLIST, tierDict)

    loadoutsClass = Loadouts(Requests, log, colors, Server, current_map)
    table = Table(cfg, log)

    stats = Stats()

    if cfg.get_feature_flag("discord_rpc"):
        rpc = Rpc(map_urls, gamemodes, colors, log)
    else:
        rpc = None

    Wss = Ws(Requests.lockfile, Requests, cfg, colors, hide_names, Server, rpc)

    log(f"VALORANT rank yoinker v{version}")

    valoApiSkins = requests.get("https://valorant-api.com/v1/weapons/skins")
    gameContent = content.get_content()
    seasonID = content.get_latest_season_id(gameContent)
    previousSeasonID = content.get_previous_season_id(gameContent)
    lastGameState = ""

    match_cache = MatchCache(log, rank, pstats, seasonID, previousSeasonID)

    print("\nvRY Mobile", color(f"- {get_ip()}:{cfg.port}", fore=(255, 127, 80)))

    print(
        color(
            "\nVisit https://vry.netlify.app/matchLoadouts to view full player inventories\n",
            fore=(255, 253, 205),
        )
    )

    richConsole = RichConsole()

    firstTime = True
    firstPrint = True
    while True:
        table.clear()
        table.set_default_field_names()
        table.reset_runtime_col_flags()

        # check if short ranks should be used
        if cfg.get_feature_flag("short_ranks"):
            Ranks = SHORT_NUMBERTORANKS
        else:
            Ranks = NUMBERTORANKS

        try:
            if firstTime:
                run = True
                while run:
                    presence = presences.get_presence()
                    private_presence = presences.get_private_presence(presence)
                    # wait until your own valorant presence is initialized
                    if private_presence is not None:
                        if cfg.get_feature_flag("discord_rpc"):
                            rpc.set_rpc(private_presence)
                        game_state = presences.get_game_state(presence)
                        if game_state is not None:
                            run = False
                    else:
                        log(f"waiting for presence... (presence: {presence is not None}, private: {private_presence is not None})")
                    time.sleep(2)
                log(f"first game state: {game_state}")
            else:
                previous_game_state = game_state
                if Requests.is_deceive_running():
                    presence = presences.get_presence()
                    private_presence = presences.get_private_presence(presence)
                    game_state = presences.get_game_state(presence)
                else:
                    game_state = asyncio.run(
                        Wss.recconect_to_websocket(game_state)
                    )
                # We invalidate the cached responses when going from any state to menus
                if previous_game_state != game_state and game_state == "MENUS":
                    rank.invalidate_cached_responses()
                    match_cache.reset()
                    if hasattr(pstats, "clear_runtime_cache"):
                        pstats.clear_runtime_cache()
                log(f"new game state: {game_state}")
            firstTime = False
        except TypeError:
            game_state = "DISCONNECTED"
            match_cache.reset()
            if hasattr(pstats, "clear_runtime_cache"):
                pstats.clear_runtime_cache()

        if game_state == "DISCONNECTED":
            richConsole.print("[yellow]Disconnected from Valorant. Attempting to reconnect...[/yellow]")
            # Loop waits for the Valorant client to respond
            while True:
                # Rereads the lockfile
                Requests.lockfile = Requests.get_lockfile()

                if Requests.lockfile is None:
                    time.sleep(5)
                    continue

                presence_check = presences.get_presence()
                
                if presence_check is not None:
                    break 
                
                time.sleep(5)

            richConsole.print("[green]Reconnected successfully! Loading...[/green]")
            
            Requests.get_headers(refresh=True)

            Wss = Ws(Requests.lockfile, Requests, cfg, colors, hide_names, Server, rpc)

            firstTime = True 
            lastGameState = ""
            match_cache.reset()
            if hasattr(pstats, "clear_runtime_cache"):
                pstats.clear_runtime_cache()
            continue

        if game_state == lastGameState:
            time.sleep(cfg.cooldown)
            continue

        if True:
            log(f"getting new {game_state} scoreboard")
            lastGameState = game_state
            game_state_dict = {
                "INGAME": color("In-Game", fore=(241, 39, 39)),
                "PREGAME": color("Agent Select", fore=(103, 237, 76)),
                "MENUS": color("In-Menus", fore=(238, 241, 54)),
            }

            if (not firstPrint) and cfg.get_feature_flag("pre_cls"):
                os.system("cls")

            is_leaderboard_needed = False
            current_map_name = None
            
            # get new presence
            presence = presences.get_presence()
            priv_presence = presences.get_private_presence(presence)
            
            # Temp fix: Riot is swapping between nested and flat API structures.
            party_state = ""
            if "partyPresenceData" in priv_presence: # Check for nested structure
                party_state = priv_presence["partyPresenceData"]["partyState"]
            elif "partyState" in priv_presence: # Check for flattened structure
                party_state = priv_presence["partyState"]
            elif "fallback_game_state" in priv_presence:
                party_state = "DEFAULT"
            else:
                # No known structure found, log and fail
                log("ERROR: Unknown presence API structure in 'main'.")
                party_state = "DEFAULT"
            
            if (
                priv_presence["provisioningFlow"] == "CustomGame"
                or party_state == "CUSTOM_GAME_SETUP"
            ):
                gamemode = "Custom Game"
            else:
                gamemode = gamemodes.get(priv_presence["queueId"])

            heartbeat_data = {
                "time": int(time.time()),
                "state": game_state,
                "mode": gamemode,
                "puuid": Requests.puuid,
                "players": {},
            }

            already_played_with = []
            isRange = False

            if game_state == "INGAME":
                coregame_stats = coregame.get_coregame_stats()
                if coregame_stats == None:
                    continue
                coregame_match_id = coregame.get_coregame_match_id()
                
                is_leaderboard_needed, already_played_with, server, current_map_name, isRange = coregame.process(
                    coregame_stats, coregame_match_id, map_urls, namesClass, presences, menu, match_cache, cfg, rpc, colors, Ranks, table, heartbeat_data, richConsole, color, agent_dict, format_last_active, loadoutsClass, Wss, valoApiSkins, stats, format_heartbeat_player, format_player_stats, get_player_name_color
                )
            elif game_state == "PREGAME":
                pregame_stats = pregame.get_pregame_stats()
                if pregame_stats == None:
                    continue
                
                is_leaderboard_needed, server, current_map_name = pregame.process(
                    pregame_stats, map_urls, namesClass, presences, menu, match_cache, cfg, rpc, colors, Ranks, table, heartbeat_data, richConsole, color, agent_dict, format_last_active, loadoutsClass, format_heartbeat_player, format_player_stats, get_player_name_color
                )
            elif game_state == "MENUS":
                match_cache.reset()
                if hasattr(pstats, "clear_runtime_cache"):
                    pstats.clear_runtime_cache()

                server = ""
                is_leaderboard_needed = menu.process(
                    presence, namesClass, rank, seasonID, previousSeasonID, pstats, cfg, colors, Ranks, table, rpc, heartbeat_data, richConsole, color, format_heartbeat_player, format_player_stats
                )

            if (title := game_state_dict.get(game_state)) is None:
                time.sleep(9)
            
            title_parts = [f"VALORANT status: {title}"]

            if current_map_name and game_state in ("INGAME", "PREGAME"):
                title_parts.append(f" | {colr(gamemode, fore=(0, 191, 255))}")
                title_parts.append(f" | {colr(current_map_name, fore=(255, 255, 0))}")

            if server:
                short_server = get_short_server_name(server)
                if short_server:
                    server_color = (255, 182, 193) if (game_state in ("INGAME", "PREGAME") and current_map_name) else (200, 200, 200) if cfg.get_feature_flag("server_id") else None
                    if server_color:
                        title_parts.append(f" | {colr(short_server, fore=server_color)}")

            if game_state == "PREGAME" and pregame_stats is not None and cfg.get_feature_flag("starting_side"):
                team_side = "Attacker" if pregame_stats["AllyTeam"]["TeamID"] == "Red" else "Defender"
                title_parts.append(f" | {colr(team_side, fore=(76, 151, 237) if team_side == 'Defender' else (238, 77, 77))}")
            
            table.set_title(''.join(title_parts))
            
            if title is not None:
                if cfg.get_feature_flag("auto_hide_leaderboard") and (
                    not is_leaderboard_needed
                ):
                    table.set_runtime_col_flag("Pos.", False)

                if game_state == "MENUS":
                    table.set_runtime_col_flag("Party", False)
                    table.set_runtime_col_flag("Agent", False)
                    table.set_runtime_col_flag(cfg.weapon.capitalize(), False)
                    table.set_runtime_col_flag("Last Active", False)

                if game_state == "INGAME":
                    if isRange:
                        table.set_runtime_col_flag("Party", False)
                        table.set_runtime_col_flag("Agent", False)

                # We don't to show the RR column if the "aggregate_rank_rr" feature flag is True.
                table.set_runtime_col_flag(
                    "RR",
                    cfg.table.get("rr")
                    and not cfg.get_feature_flag("aggregate_rank_rr"),
                )

                table.set_caption(f"VALORANT rank yoinker v{version}")
                Server.send_payload("heartbeat", heartbeat_data)
                table.display()
                firstPrint = False

                if cfg.get_feature_flag("last_played"):
                    if len(already_played_with) > 0:
                        print("\n")
                        for played in already_played_with:
                            print(
                                f"Already played with {played['name']} (last {played['agent']}) {stats.convert_time(played['time_diff'])} ago. (Total played {played['times']} times)"
                            )
                already_played_with = []
        if cfg.cooldown == 0:
            input("Press enter to fetch again...")
        else:
            pass
except KeyboardInterrupt:
    os._exit(0)
except:
    log(traceback.format_exc())
    print(
        color(
            "The program has encountered an error. If the problem persists, please reach support"
            f" with the logs found in {os.getcwd()}\\logs",
            fore=(255, 0, 0),
        )
    )
    input("press enter to exit...\n")
    os._exit(1)
