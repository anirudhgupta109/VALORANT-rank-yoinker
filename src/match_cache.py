import time

class MatchCache:
    def __init__(self, log, rank, pstats, seasonID, previousSeasonID):
        self.log = log
        self.rank = rank
        self.pstats = pstats
        self.seasonID = seasonID
        self.previousSeasonID = previousSeasonID
        self.match_id = None
        self.players = {}  # puuid -> {"playerRank", "previousPlayerRank", "ppstats", "ts"}
        self.TTL_SECONDS = 300

    def reset(self, match_id=None):
        self.match_id = match_id
        self.players = {}

    def ensure_cache(self, match_id):
        if not match_id:
            return

        # New match => reset cache
        if self.match_id != match_id:
            self.reset(match_id)
            return

        # TTL cleanup (safety)
        now = time.time()
        expired = []
        for puuid, cached in self.players.items():
            ts = cached.get("ts", now)
            if (now - ts) > self.TTL_SECONDS:
                expired.append(puuid)

        for puuid in expired:
            del self.players[puuid]

    def get_or_fetch(self, player_subject, current_match_id):
        if current_match_id:
            self.ensure_cache(current_match_id)
            cached = self.players.get(player_subject)
            if cached is not None:
                return (
                    cached["playerRank"],
                    cached["previousPlayerRank"],
                    cached["ppstats"],
                )

        # Cache miss -> fetch
        playerRank = self.rank.get_rank(player_subject, self.seasonID)
        previousPlayerRank = self.rank.get_rank(player_subject, self.previousSeasonID)
        ppstats = self.pstats.get_stats(player_subject)

        if current_match_id and self.match_id == current_match_id:
            self.players[player_subject] = {
                "playerRank": dict(playerRank) if isinstance(playerRank, dict) else playerRank,
                "previousPlayerRank": dict(previousPlayerRank) if isinstance(previousPlayerRank, dict) else previousPlayerRank,
                "ppstats": dict(ppstats) if isinstance(ppstats, dict) else ppstats,
                "ts": time.time(),
            }

        return playerRank, previousPlayerRank, ppstats
