import socket
import time
import sys

def program_exit(log, status: int):  # so we don't need to import the entire sys module
    log(f"exited program with error code {status}")
    raise sys.exit(status)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(("10.254.254.254", 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP

def format_last_active(last_active_epoch):
    if not last_active_epoch:
        return "N/A"

    try:
        seconds_ago = max(0, int(time.time() - float(last_active_epoch)))
    except (TypeError, ValueError):
        return "N/A"

    if seconds_ago < 60:
        return "now"
    if seconds_ago < 3600:
        return f"{seconds_ago // 60}m ago"
    if seconds_ago < 86400:
        return f"{seconds_ago // 3600}h ago"
    return f"{seconds_ago // 86400}d ago"

def get_short_server_name(server: str) -> str:
    if not server:
        return ""

    lower_server = server.lower()
    gp_index = lower_server.find("gp-")
    if gp_index != -1:
        after_gp = lower_server[gp_index + 3:]
        return after_gp.split("-")[0].upper()

    parts = server.split('.')
    if len(parts) > 2:
        return '.'.join(parts[2:])
    return server

def format_heartbeat_player(name, playerRank, peakRankAct, player_level, ppstats, last_active, party_num=None, agent=None, puuid=None, loadout_player_data=None):
    data = {
        "name": name,
        "rank": playerRank["rank"],
        "peakRank": playerRank["peakrank"],
        "peakRankAct": peakRankAct,
        "level": player_level,
        "rr": playerRank["rr"],
        "kd": ppstats["kd"],
        "headshotPercentage": ppstats["hs"],
        "winPercentage": f"{playerRank['wr']} ({playerRank['numberofgames']})",
        "lastActive": last_active,
    }
    if party_num is not None:
        data["partyNumber"] = party_num
    if agent is not None:
        data["agent"] = agent
    if puuid is not None:
        data["puuid"] = puuid
    
    if loadout_player_data is not None:
        data.update({
            "agentImgLink": loadout_player_data.get("Agent"),
            "team": loadout_player_data.get("Team"),
            "sprays": loadout_player_data.get("Sprays"),
            "title": loadout_player_data.get("Title"),
            "playerCard": loadout_player_data.get("PlayerCard"),
            "weapons": loadout_player_data.get("Weapons"),
        })
    return data

def format_player_stats(playerRank, previousPlayerRank, ppstats, colors, Ranks, cfg):
    # RANK
    rankName = Ranks[playerRank["rank"]]
    if cfg.get_feature_flag("aggregate_rank_rr") and cfg.table.get("rr"):
        rankName += f" ({playerRank['rr']})"

    # PEAK RANK ACT
    has_letter = any(c.isalpha() for c in str(playerRank["peakrankep"]))
    peakRankAct = (
        f" ({playerRank['peakrankep']}a{playerRank['peakrankact']})"
        if has_letter
        else f" (e{playerRank['peakrankep']}a{playerRank['peakrankact']})"
    )
    if not cfg.get_feature_flag("peak_rank_act"):
        peakRankAct = ""

    # PEAK RANK
    peakRank = Ranks[playerRank["peakrank"]] + peakRankAct

    # PREVIOUS RANK
    previousRank = Ranks[previousPlayerRank["rank"]]

    # Gradients
    hs = colors.get_hs_gradient(ppstats["hs"])
    wr = colors.get_wr_gradient(playerRank["wr"]) + f" ({playerRank['numberofgames']})"
    
    rr_numeric_value = ppstats["RankedRatingEarned"]
    afk_penalty = ppstats["AFKPenalty"]
    rr_earned = colors.get_rr_gradient(rr_numeric_value, afk_penalty)
    
    return {
        "rankName": rankName,
        "peakRank": peakRank,
        "peakRankAct": peakRankAct,
        "previousRank": previousRank,
        "hs": hs,
        "wr": wr,
        "rr_earned": rr_earned
    }

def get_player_name_color(player, name, self_puuid, colors, party_members, played_before=False):
    agent_id = player["CharacterID"] if player["PlayerIdentity"]["Incognito"] else None
    return colors.get_color_from_team(
        player["TeamID"],
        name,
        player["Subject"],
        self_puuid,
        agent=agent_id,
        party_members=party_members,
        played_before=played_before
    )
