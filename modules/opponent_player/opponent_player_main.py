import pandas as pd
from pathlib import Path
from shiny import ui, render, reactive

def get_team_id():
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_team_data.csv"
    df = pd.read_csv(data_path)
    return dict(zip(df["wy_team_id"].astype(str), df["wy_team_name"]))

def get_player_name(team_id):
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_player_data.csv"
    df = pd.read_csv(data_path)
    if team_id is None:
        return {}
    team_id = int(float(team_id))
    df_player = df[df["wy_team_id"].astype(float) == team_id]
    return dict(zip(df_player["wy_player_id"].astype(str), df_player["wy_player_name"]))

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
    player_matches = map_df[map_df["wy_player_id"].astype(float) == player_id]
    player_matches_joined = player_matches.merge(match_df, on="wy_match_id", how="left")
    return dict(zip(player_matches_joined["wy_match_id"].astype(str), player_matches_joined["label_date"]))

def ui_content():
    team_choices = get_team_id()
    initial_team = list(team_choices.keys())[0] if team_choices else None
    initial_player_choices = get_player_name(initial_team) if initial_team else {}
    initial_player = list(initial_player_choices.keys())[0] if initial_player_choices else None
    
    match_df = load_match_data()
    map_df = load_player_match_map()
    initial_matches = get_match_choices_for_player(map_df, match_df, initial_player) if initial_player else {}
    
    return ui.nav_panel(
        "Opponent Player",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div("Opponent Player", class_="sidebar-title"),
                ui.input_selectize(
                    "selected_opp_team_2",
                    "Select Team:",
                    choices=team_choices,
                    selected=initial_team
                ),
                ui.input_selectize(
                    "selected_opp_player",
                    "Select Player:",
                    choices=initial_player_choices,
                    selected=initial_player
                ),
                ui.input_selectize(
                    "selected_opp_player_matches",
                    "Select Matches:",
                    choices=initial_matches,
                    multiple=True
                ),
                ui.input_select(
                    "selected_opp_player_area",
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
            ui.output_text_verbatim("debug_selection_opp_player"),
            padding="1.25rem",
        ),
        value="tab_4_val"
    )

def server_logic(input, output, session):
    match_df = load_match_data()
    map_df = load_player_match_map(    )
    
    @reactive.Effect
    @reactive.event(input.selected_opp_team_2)
    def update_player_choices():
        team_id = input.selected_opp_team_2()
        if team_id:
            new_player_choices = get_player_name(team_id)
            ui.update_selectize(
                "selected_opp_player",
                choices=new_player_choices,
                selected=None
            )
            ui.update_selectize(
                "selected_opp_player_matches",
                choices={},
                selected=None
            )
    
    @reactive.Effect
    @reactive.event(input.selected_opp_player)
    def update_match_choices():
        player_id = input.selected_opp_player()
        if player_id:
            new_choices = get_match_choices_for_player(map_df, match_df, player_id)
            ui.update_selectize(
                "selected_opp_player_matches",
                choices=new_choices,
                selected=None  
            )
    
    @render.text
    def debug_selection_opp_player():
        team_id = input.selected_opp_team_2()
        player_id = input.selected_opp_player()
        match_ids = input.selected_opp_player_matches()
        return f"Selected Team: {team_id}\nSelected Player: {player_id}\nSelected Match IDs: {match_ids}"