-- Rice Soccer Dashboard schema
-- Matches the real Wyscout export columns (american_athletic_womens_soccer_fall_2025_*.csv),
-- not just the subset the app currently reads. Applied by scripts/seed_db.py.
--
-- FK constraints are only added for the relationships the app's code actually joins on
-- (wy_match_id/wy_team_id/wy_player_id/pass_recipient_id). Other event_data reference
-- columns (opponent_team_id, shot_goalkeeper_id, ground_duel_opponent_id, etc.) are kept
-- as plain columns to avoid fragile insert-order/orphan-reference failures on a table
-- this wide.

CREATE TABLE IF NOT EXISTS team_data (
    wy_team_id   INTEGER PRIMARY KEY,
    wy_team_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_data (
    wy_match_id     INTEGER PRIMARY KEY,
    wy_season_id    INTEGER,
    wy_competition_id INTEGER,
    wy_round_id     INTEGER,
    home_team_id    INTEGER NOT NULL REFERENCES team_data(wy_team_id),
    away_team_id    INTEGER NOT NULL REFERENCES team_data(wy_team_id),
    status          TEXT,
    duration        TEXT,
    game_week       INTEGER,
    has_data_available BOOLEAN,
    home_score      INTEGER,
    away_score      INTEGER,
    date            TEXT,
    match_datetime  TIMESTAMP,
    label           TEXT,
    label_date      TEXT
);

CREATE TABLE IF NOT EXISTS player_data (
    wy_player_id   INTEGER PRIMARY KEY,
    wy_player_name TEXT NOT NULL,
    wy_team_id     INTEGER NOT NULL REFERENCES team_data(wy_team_id)
);

CREATE TABLE IF NOT EXISTS player_match_mapping (
    wy_player_id   INTEGER NOT NULL REFERENCES player_data(wy_player_id),
    wy_match_id    INTEGER NOT NULL REFERENCES match_data(wy_match_id),
    wy_player_name TEXT,
    wy_team_id     INTEGER REFERENCES team_data(wy_team_id),
    PRIMARY KEY (wy_player_id, wy_match_id)
);

-- Mirrors Wyscout's own /matches/{id}/advancedstats/players counts directly
-- (snake_case of duels/duelsWon/offensiveDuels/offensiveDuelsWon/etc.) rather
-- than a bespoke derivation from raw event flags -- every *_won_count here is
-- guaranteed <= its corresponding *_count, unlike the old event-derived
-- columns this replaces, which caused a real >100% bug (see duel_stats.py).
CREATE TABLE IF NOT EXISTS team_player_match_duels (
    wy_team_id   INTEGER NOT NULL REFERENCES team_data(wy_team_id),
    wy_match_id  INTEGER NOT NULL REFERENCES match_data(wy_match_id),
    wy_player_id INTEGER NOT NULL REFERENCES player_data(wy_player_id),
    duels_count INTEGER,
    duels_won_count INTEGER,
    offensive_duels_count INTEGER,
    offensive_duels_won_count INTEGER,
    defensive_duels_count INTEGER,
    defensive_duels_won_count INTEGER,
    aerial_duels_count INTEGER,
    aerial_duels_won_count INTEGER,
    loose_ball_duels_count INTEGER,
    loose_ball_duels_won_count INTEGER,
    pressing_duels_count INTEGER,
    pressing_duels_won_count INTEGER,
    PRIMARY KEY (wy_team_id, wy_match_id, wy_player_id)
);

-- Tracks the last successful incremental sync per Wyscout resource type, so
-- scripts/wyscout_incremental.py knows what "updated_since" to pass to
-- /updatedobjects. Not the full etl_status/freshness-banner feature discussed
-- earlier -- just enough state for the sync job itself to resume correctly.
CREATE TABLE IF NOT EXISTS etl_sync_state (
    resource_type   TEXT PRIMARY KEY,
    last_synced_at  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS event_data (
    wy_event_id                   BIGINT PRIMARY KEY,
    wy_season_id                  INTEGER,
    wy_match_id                   INTEGER NOT NULL REFERENCES match_data(wy_match_id),
    period                        INTEGER,
    timestamp                     TEXT,
    minute                        INTEGER,
    second                        INTEGER,
    video_timestamp               NUMERIC,
    type_primary                  TEXT,
    type_secondary                TEXT,
    related_event_id              BIGINT,
    location_x                    FLOAT,
    location_y                    FLOAT,
    wy_team_id                    INTEGER NOT NULL REFERENCES team_data(wy_team_id),
    team_name                     TEXT,
    team_formation                TEXT,
    opponent_team_id              INTEGER,
    opponent_team_name            TEXT,
    opponent_team_formation       TEXT,
    wy_player_id                  INTEGER REFERENCES player_data(wy_player_id),
    player_name                   TEXT,
    player_position               TEXT,
    pass_accurate                 BOOLEAN,
    pass_angle                    FLOAT,
    pass_length                   FLOAT,
    pass_height                   TEXT,
    pass_end_location_x           FLOAT,
    pass_end_location_y           FLOAT,
    pass_recipient_id             INTEGER REFERENCES player_data(wy_player_id),
    pass_recipient_name           TEXT,
    pass_recipient_position       TEXT,
    shot_body_part                TEXT,
    shot_is_goal                  BOOLEAN,
    shot_on_target                BOOLEAN,
    shot_goal_zone                TEXT,
    shot_end_location_x           FLOAT,
    shot_end_location_y           FLOAT,
    shot_end_location_z           FLOAT,
    shot_goalkeeper_id            INTEGER,
    shot_goalkeeper_name          TEXT,
    shot_goalkeeper_action_id     BIGINT,
    shot_xg                       FLOAT,
    shot_post_shot_xg             FLOAT,
    ground_duel_type              TEXT,
    ground_duel_kept_possession   BOOLEAN,
    ground_duel_opponent_id       INTEGER,
    ground_duel_opponent_name     TEXT,
    ground_duel_opponent_position TEXT,
    ground_duel_progressed_with_ball BOOLEAN,
    ground_duel_recovered_possession BOOLEAN,
    ground_duel_related_duel_id   BIGINT,
    ground_duel_side              TEXT,
    ground_duel_stopped_progress  BOOLEAN,
    ground_duel_take_on           BOOLEAN,
    aerial_duel_opponent_id       INTEGER,
    aerial_duel_opponent_name     TEXT,
    aerial_duel_opponent_position TEXT,
    aerial_duel_opponent_height   FLOAT,
    aerial_duel_first_touch       BOOLEAN,
    aerial_duel_height            FLOAT,
    aerial_duel_related_duel_id   BIGINT,
    infraction_yellow_card        BOOLEAN,
    infraction_red_card           BOOLEAN,
    infraction_type               TEXT,
    infraction_opponent_id        INTEGER,
    infraction_opponent_name      TEXT,
    infraction_opponent_position  TEXT,
    carry_progression             FLOAT,
    carry_end_location_x          FLOAT,
    carry_end_location_y          FLOAT,
    possession_id                 BIGINT,
    possession_duration            FLOAT,
    possession_event_index        INTEGER,
    possession_events_number      INTEGER,
    possession_start_location_x   FLOAT,
    possession_start_location_y   FLOAT,
    possession_end_location_x     FLOAT,
    possession_end_location_y     FLOAT,
    possession_types              TEXT,
    possession_team_id            INTEGER,
    possession_team_name          TEXT,
    possession_team_formation     TEXT,
    possession_attack_flank       TEXT,
    possession_attack_with_goal   BOOLEAN,
    possession_attack_with_shot   BOOLEAN,
    possession_attack_with_shot_on_goal BOOLEAN,
    possession_attack_xg          FLOAT,
    wy_competition_id              INTEGER,
    wy_round_id                    INTEGER,
    date                          TEXT,
    match_datetime                TIMESTAMP,
    duration                      TEXT,
    game_week                     INTEGER,
    has_data_available             BOOLEAN,
    label                         TEXT,
    home_team_id                  INTEGER,
    away_team_id                  INTEGER,
    home_score                    INTEGER,
    away_score                    INTEGER
);
