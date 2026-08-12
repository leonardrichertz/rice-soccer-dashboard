import pandas as pd
from shiny import ui, render, reactive
from .. import data_access
from .. import player_attack as attack
from .. import player_defense as defense

def get_player_name():
    df = data_access.load_player_data()
    df_player = df[df["wy_team_id"] == 61585]
    return dict(zip(df_player["wy_player_id"].astype(str), df_player["wy_player_name"]))

def load_event_data():
    return data_access.load_event_data()

def load_match_data():
    return data_access.load_match_data()

def load_player_match_map():
    return data_access.load_player_match_map()

def get_match_choices_for_player(map_df, match_df, player_id, season_id=None):
    if player_id is None:
        return {}
    player_id = int(float(player_id))
    player_matches = map_df[map_df["wy_player_id"] == player_id]
    player_matches_joined = player_matches.merge(match_df, on="wy_match_id", how="left")
    if season_id is not None:
        player_matches_joined = player_matches_joined[player_matches_joined["wy_season_id"] == int(season_id)]
    return dict(zip(player_matches_joined["wy_match_id"].astype(str), player_matches_joined["label_date"]))

def ui_content():
    rice_player_choices = get_player_name()
    match_df = load_match_data()
    map_df = load_player_match_map()
    season_choices = data_access.get_season_choices()
    initial_season = list(season_choices.keys())[0] if season_choices else None
    initial_player = list(rice_player_choices.keys())[0] if rice_player_choices else None
    initial_matches = get_match_choices_for_player(map_df, match_df, initial_player, initial_season) if initial_player else {}

    return ui.nav_panel(
        "Rice Player",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div("Rice Player", class_="sidebar-title"),
                ui.input_select(
                    "selected_rice_player_season",
                    "Season:",
                    choices=season_choices,
                    selected=initial_season
                ),
                ui.input_selectize(
                    "selected_rice_player",
                    "Select Player:",
                    choices=rice_player_choices,
                    selected=initial_player
                ),
                ui.input_selectize(
                    "selected_rice_player_matches",
                    "Select Matches:",
                    choices=initial_matches,
                    multiple=True
                ),
                ui.input_action_link("select_all_rice_player_matches", "Select all games"),
                ui.input_select(
                    "selected_rice_player_area",
                    "Area:",
                    choices={
                        "Attack": "Attack",
                        "Defence": "Defence",
                        "Set-Pieces": "Set-Pieces"
                    }
                ),
                open="always",
                width="340px",
            ),
            ui.output_ui("dynamic_content_player"),
            padding="1.25rem",
        ),
        value="tab_2_val"
    )

def server_logic(input, output, session):
    event_df = load_event_data()
    match_df = load_match_data()
    map_df = load_player_match_map()

    @reactive.Effect
    @reactive.event(input.selected_rice_player, input.selected_rice_player_season)
    def update_match_choices():
        player_id = input.selected_rice_player()
        if player_id:
            new_choices = get_match_choices_for_player(map_df, match_df, player_id, input.selected_rice_player_season())
            ui.update_selectize(
                "selected_rice_player_matches",
                choices=new_choices,
                selected=None
            )

    @reactive.effect
    @reactive.event(input.select_all_rice_player_matches)
    def _select_all_rice_player_matches():
        player_id = input.selected_rice_player()
        if player_id:
            choices = get_match_choices_for_player(map_df, match_df, player_id, input.selected_rice_player_season())
            ui.update_selectize(
                "selected_rice_player_matches",
                selected=list(choices.keys())
            )

    @reactive.calc
    def filtered_player_events():
        player_id = input.selected_rice_player()
        selected_matches = input.selected_rice_player_matches()
        
        if not player_id or not selected_matches:
            return pd.DataFrame()
            
        return event_df[
            (event_df["wy_match_id"].astype(str).isin(selected_matches))
        ]
    
    @render.ui
    def dynamic_content_player():
        area = input.selected_rice_player_area()
        if area == "Attack":
            return attack.attack_ui("rice_player")
        elif area == "Defence":
            return defense.defense_ui("rice_player")
        return ui.div("Set-piece analytics coming soon.", class_="empty-state")

    attack.attack_server(input, output, session, filtered_player_events, input.selected_rice_player, "rice_player")
    defense.defense_server(input, output, session, filtered_player_events, input.selected_rice_player, "rice_player")