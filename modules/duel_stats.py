"""Shared duel-event filtering. Given an events DataFrame already filtered down
to one entity (a team or a player) for a set of matches, splits it into ground
and aerial duel events. Used anywhere a duel win/loss or duel percentage needs
computing -- player_defense.py and the comparison tool today.

Percentages should always be computed against len(ground_duels)/len(aerial_duels)
from this same filtered population, never against offensive_duels_count/
defensive_duels_count -- those broader counts also include aerial and loose-ball
duels, so dividing a ground-duel-only outcome by them is not a valid subset/
superset relationship and can exceed 100%."""

def get_ground_and_aerial_duels(df_filtered):
    ground_duels = df_filtered[df_filtered["type_secondary"].str.contains("ground_duel", case=False, na=False)]
    aerial_duels = df_filtered[df_filtered["type_secondary"].str.contains("aerial_duel", case=False, na=False)]
    return ground_duels, aerial_duels
