import pandas as pd
from pathlib import Path
from shiny import ui, render, reactive
from . import rice_player_attack as attack

def get_player_name():
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_player_data.csv"
    df = pd.read_csv(data_path)
    df_player = df[df["wy_team_id"] == 61585]
    return dict(zip(df_player["wy_player_id"].astype(str), df_player["wy_player_name"]))

def load_event_data():
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_event_data_selected_cols.csv"
    return pd.read_csv(data_path)

def load_match_data():
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_match_data.csv"
    return pd.read_csv(data_path)

def load_player_match_map():
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_player_match_mapping.csv"
    return pd.read_csv(data_path)

def get_match_choices_for_player(map_df, match_df, player_id):
    if player_id is None:
        return {}
    player_id = int(float(player_id))
    player_matches = map_df[map_df["wy_player_id"] == player_id]
    player_matches_joined = player_matches.merge(match_df, on="wy_match_id", how="left")
    return dict(zip(player_matches_joined["wy_match_id"].astype(str), player_matches_joined["label_date"]))

def ui_content():
    rice_player_choices = get_player_name()
    match_df = load_match_data()
    map_df = load_player_match_map()
    initial_player = list(rice_player_choices.keys())[0] if rice_player_choices else None
    initial_matches = get_match_choices_for_player(map_df, match_df, initial_player) if initial_player else {}
    
    return ui.nav_panel(
        "Rice Player",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div("Rice Player", class_="sidebar-title"),
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
    @reactive.event(input.selected_rice_player)
    def update_match_choices():
        player_id = input.selected_rice_player()
        if player_id:
            new_choices = get_match_choices_for_player(map_df, match_df, player_id)
            ui.update_selectize(
                "selected_rice_player_matches",
                choices=new_choices,
                selected=None  
            )
    
    @render.text
    def debug_selection_rice_player():
        player_id = input.selected_rice_player()
        match_ids = input.selected_rice_player_matches()
        return f"Selected Player: {player_id}\nSelected Match IDs: {match_ids}"

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
            return attack.attack_ui()
        return ui.div("Defense and set-piece analytics coming soon.", class_="empty-state")

    attack.attack_server(input, output, session, filtered_player_events)