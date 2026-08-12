"""Flattens raw Wyscout API v3 JSON into rows matching db/schema.sql.

Player -> team assignment is deliberately NOT taken from /seasons/{id}/players'
currentTeamId (some players have that null, and it reflects their CURRENT team,
not necessarily the team they played for in a given historical season). Instead
it's derived from each match's actual lineup/bench data during the backfill
loop, which is historically accurate per-match and never null for a player who
actually appeared in a match.
"""

DURATION_TO_SCORE_FIELD = {
    "Regular": "score",
    "ExtraTime": "scoreET",
    "Penalties": "scoreP",
}

MATCH_PERIOD_TO_INT = {
    "1H": 1,
    "2H": 2,
    "1E": 3,
    "2E": 4,
    "P": 5,
}


def transform_team(raw_team):
    return {
        "wy_team_id": raw_team["wyId"],
        "wy_team_name": raw_team["name"],
    }


def transform_player(raw_player):
    """wy_team_id is filled in later from observed match lineups, not here."""
    return {
        "wy_player_id": raw_player["wyId"],
        "wy_player_name": raw_player["shortName"],
        "wy_team_id": raw_player.get("currentTeamId"),
    }


def _final_score(team_entry, duration):
    field = DURATION_TO_SCORE_FIELD.get(duration, "score")
    return team_entry.get(field)


def transform_match(raw_match):
    teams_data = raw_match["teamsData"]
    home = next(t for t in teams_data.values() if t["side"] == "home")
    away = next(t for t in teams_data.values() if t["side"] == "away")
    duration = raw_match.get("duration")

    return {
        "wy_match_id": raw_match["wyId"],
        "wy_season_id": raw_match["seasonId"],
        "wy_competition_id": raw_match["competitionId"],
        "wy_round_id": raw_match["roundId"],
        "home_team_id": home["teamId"],
        "away_team_id": away["teamId"],
        "status": raw_match.get("status"),
        "duration": duration,
        "game_week": raw_match.get("gameweek"),
        "has_data_available": raw_match.get("hasDataAvailable"),
        "home_score": _final_score(home, duration),
        "away_score": _final_score(away, duration),
        "date": raw_match.get("date"),
        "match_datetime": raw_match.get("dateutc"),
        "label": raw_match.get("label"),
        "label_date": f"{raw_match.get('label')} {raw_match.get('date')}",
    }


def transform_lineup_rows(raw_match):
    """Returns (player_match_mapping_rows, player_team_observations) for one
    match. player_team_observations is [(wy_player_id, wy_team_id), ...] for
    every player who actually appeared in this match's lineup or bench --
    used to backfill player_data.wy_team_id without relying on currentTeamId."""
    match_id = raw_match["wyId"]
    mapping_rows = []
    observations = []

    for team_id_str, team_entry in raw_match["teamsData"].items():
        team_id = int(team_id_str)
        formation = team_entry.get("formation") or {}
        for group in ("lineup", "bench"):
            for player_entry in formation.get(group, []):
                player_id = player_entry["playerId"]
                mapping_rows.append({
                    "wy_player_id": player_id,
                    "wy_match_id": match_id,
                    "wy_player_name": None,
                    "wy_team_id": team_id,
                })
                observations.append((player_id, team_id))

    return mapping_rows, observations


def transform_duels(raw_advancedstats_players, team_of_player):
    """team_of_player: dict mapping wy_player_id -> wy_team_id, needed because
    the advancedstats/players endpoint doesn't include team id directly."""
    rows = []
    for p in raw_advancedstats_players["players"]:
        player_id = p["playerId"]
        team_id = team_of_player.get(player_id)
        if team_id is None:
            continue
        total = p.get("total", {})
        rows.append({
            "wy_team_id": team_id,
            "wy_match_id": p["matchId"],
            "wy_player_id": player_id,
            "duels_count": total.get("duels"),
            "duels_won_count": total.get("duelsWon"),
            "offensive_duels_count": total.get("offensiveDuels"),
            "offensive_duels_won_count": total.get("offensiveDuelsWon"),
            "defensive_duels_count": total.get("defensiveDuels"),
            "defensive_duels_won_count": total.get("defensiveDuelsWon"),
            "aerial_duels_count": total.get("aerialDuels"),
            "aerial_duels_won_count": total.get("aerialDuelsWon"),
            "loose_ball_duels_count": total.get("looseBallDuels"),
            "loose_ball_duels_won_count": total.get("looseBallDuelsWon"),
            "pressing_duels_count": total.get("pressingDuels"),
            "pressing_duels_won_count": total.get("pressingDuelsWon"),
        })
    return rows


def _fmt_secondary(secondary_list):
    # Matches the existing data's format exactly: "[tag_one, tag_two]",
    # unquoted -- app code does substring matching via .str.contains(), and
    # some call sites do exact-match against this literal format (e.g. == "[foul]").
    return f"[{', '.join(secondary_list or [])}]"


def transform_event(raw_event, match_context):
    """match_context: the dict returned by transform_match() for this event's
    match -- supplies the match-level columns denormalized onto every event
    row (date, label, home_score, etc.), matching the existing event_data shape."""
    type_ = raw_event.get("type") or {}
    location = raw_event.get("location") or {}
    team = raw_event.get("team") or {}
    opponent_team = raw_event.get("opponentTeam") or {}
    player = raw_event.get("player") or {}

    pass_ = raw_event.get("pass") or {}
    pass_recipient = pass_.get("recipient") or {}
    pass_end = pass_.get("endLocation") or {}

    shot = raw_event.get("shot") or {}
    shot_goalkeeper = shot.get("goalkeeper") or {}

    ground_duel = raw_event.get("groundDuel") or {}
    ground_opponent = ground_duel.get("opponent") or {}

    aerial_duel = raw_event.get("aerialDuel") or {}
    aerial_opponent = aerial_duel.get("opponent") or {}

    infraction = raw_event.get("infraction") or {}
    infraction_opponent = infraction.get("opponent") or {}

    carry = raw_event.get("carry") or {}
    carry_end = carry.get("endLocation") or {}

    possession = raw_event.get("possession") or {}
    possession_start = possession.get("startLocation") or {}
    possession_end = possession.get("endLocation") or {}
    possession_team = possession.get("team") or {}
    possession_attack = possession.get("attack") or {}

    match_timestamp = raw_event.get("matchTimestamp")
    timestamp = match_timestamp.split(".")[0] if match_timestamp else None

    return {
        "wy_event_id": raw_event["id"],
        "wy_season_id": match_context.get("wy_season_id"),
        "wy_match_id": raw_event["matchId"],
        "period": MATCH_PERIOD_TO_INT.get(raw_event.get("matchPeriod")),
        "timestamp": timestamp,
        "minute": raw_event.get("minute"),
        "second": raw_event.get("second"),
        "video_timestamp": raw_event.get("videoTimestamp"),
        "type_primary": type_.get("primary"),
        "type_secondary": _fmt_secondary(type_.get("secondary")),
        "related_event_id": raw_event.get("relatedEventId"),
        "location_x": location.get("x"),
        "location_y": location.get("y"),
        "wy_team_id": team.get("id"),
        "team_name": team.get("name"),
        "team_formation": team.get("formation"),
        "opponent_team_id": opponent_team.get("id"),
        "opponent_team_name": opponent_team.get("name"),
        "opponent_team_formation": opponent_team.get("formation"),
        "wy_player_id": player.get("id"),
        "player_name": player.get("name"),
        "player_position": player.get("position"),
        "pass_accurate": pass_.get("accurate"),
        "pass_angle": pass_.get("angle"),
        "pass_length": pass_.get("length"),
        "pass_height": pass_.get("height"),
        "pass_end_location_x": pass_end.get("x"),
        "pass_end_location_y": pass_end.get("y"),
        "pass_recipient_id": pass_recipient.get("id"),
        "pass_recipient_name": pass_recipient.get("name"),
        "pass_recipient_position": pass_recipient.get("position"),
        "shot_body_part": shot.get("bodyPart"),
        "shot_is_goal": shot.get("isGoal"),
        "shot_on_target": shot.get("onTarget"),
        "shot_goal_zone": shot.get("goalZone"),
        "shot_end_location_x": None,
        "shot_end_location_y": None,
        "shot_end_location_z": None,
        "shot_goalkeeper_id": shot_goalkeeper.get("id"),
        "shot_goalkeeper_name": shot_goalkeeper.get("name"),
        "shot_goalkeeper_action_id": shot.get("goalkeeperActionId"),
        "shot_xg": shot.get("xg"),
        "shot_post_shot_xg": shot.get("postShotXg"),
        "ground_duel_type": ground_duel.get("duelType"),
        "ground_duel_kept_possession": ground_duel.get("keptPossession"),
        "ground_duel_opponent_id": ground_opponent.get("id"),
        "ground_duel_opponent_name": ground_opponent.get("name"),
        "ground_duel_opponent_position": ground_opponent.get("position"),
        "ground_duel_progressed_with_ball": ground_duel.get("progressedWithBall"),
        "ground_duel_recovered_possession": ground_duel.get("recoveredPossession"),
        "ground_duel_related_duel_id": ground_duel.get("relatedDuelId"),
        "ground_duel_side": ground_duel.get("side"),
        "ground_duel_stopped_progress": ground_duel.get("stoppedProgress"),
        "ground_duel_take_on": ground_duel.get("takeOn"),
        "aerial_duel_opponent_id": aerial_opponent.get("id"),
        "aerial_duel_opponent_name": aerial_opponent.get("name"),
        "aerial_duel_opponent_position": aerial_opponent.get("position"),
        "aerial_duel_opponent_height": aerial_opponent.get("height"),
        "aerial_duel_first_touch": aerial_duel.get("firstTouch"),
        "aerial_duel_height": aerial_duel.get("height"),
        "aerial_duel_related_duel_id": aerial_duel.get("relatedDuelId"),
        "infraction_yellow_card": infraction.get("yellowCard"),
        "infraction_red_card": infraction.get("redCard"),
        "infraction_type": infraction.get("type"),
        "infraction_opponent_id": infraction_opponent.get("id"),
        "infraction_opponent_name": infraction_opponent.get("name"),
        "infraction_opponent_position": infraction_opponent.get("position"),
        "carry_progression": carry.get("progression"),
        "carry_end_location_x": carry_end.get("x"),
        "carry_end_location_y": carry_end.get("y"),
        "possession_id": possession.get("id"),
        "possession_duration": possession.get("duration"),
        "possession_event_index": possession.get("eventIndex"),
        "possession_events_number": possession.get("eventsNumber"),
        "possession_start_location_x": possession_start.get("x"),
        "possession_start_location_y": possession_start.get("y"),
        "possession_end_location_x": possession_end.get("x"),
        "possession_end_location_y": possession_end.get("y"),
        "possession_types": _fmt_secondary(possession.get("types")),
        "possession_team_id": possession_team.get("id"),
        "possession_team_name": possession_team.get("name"),
        "possession_team_formation": possession_team.get("formation"),
        "possession_attack_flank": possession_attack.get("flank"),
        "possession_attack_with_goal": possession_attack.get("withGoal"),
        "possession_attack_with_shot": possession_attack.get("withShot"),
        "possession_attack_with_shot_on_goal": possession_attack.get("withShotOnGoal"),
        "possession_attack_xg": possession_attack.get("xg"),
        "wy_competition_id": match_context.get("wy_competition_id"),
        "wy_round_id": match_context.get("wy_round_id"),
        "date": match_context.get("date"),
        "match_datetime": match_context.get("match_datetime"),
        "duration": match_context.get("duration"),
        "game_week": match_context.get("game_week"),
        "has_data_available": match_context.get("has_data_available"),
        "label": match_context.get("label"),
        "home_team_id": match_context.get("home_team_id"),
        "away_team_id": match_context.get("away_team_id"),
        "home_score": match_context.get("home_score"),
        "away_score": match_context.get("away_score"),
    }
