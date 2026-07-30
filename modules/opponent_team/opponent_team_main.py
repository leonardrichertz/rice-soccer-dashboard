import pandas as pd
from shiny import ui, render, reactive
from .. import data_access
from .. import team_defense as defense
from . import opponent_team_attack as attack
from . import opponent_team_setpiece as set_pieces

def load_all_data():
    team_df = data_access.load_team_data()
    event_df = data_access.load_event_data()
    match_df = data_access.load_match_data()

    team_dict = dict(zip(team_df["wy_team_id"].astype(str), team_df["wy_team_name"]))
    return team_dict, event_df, match_df


opp_team_choices, event_df, match_df = load_all_data()

def get_match_choices_for_team(df, team_id):
   
    if not team_id: 
        return {}
    
    team_id = int(float(team_id))
    team_matches = df[(df["home_team_id"].astype(float) == team_id) | (df["away_team_id"].astype(float) == team_id)]
    return dict(zip(team_matches["wy_match_id"].astype(str), team_matches["label_date"]))

def ui_content():
    initial_team = list(opp_team_choices.keys())[0] if opp_team_choices else None
    initial_matches = get_match_choices_for_team(match_df, initial_team) if initial_team else {}
    
    return ui.nav_panel(
        "Opponent Team",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div("Opponent Team", class_="sidebar-title"),
                ui.input_selectize(
                    "selected_opp_team",
                    "Select Opponent:",
                    choices=opp_team_choices,
                    selected=initial_team
                ),
                ui.input_selectize(
                    "selected_opp_matches",
                    "Select Matches:",
                    choices=initial_matches,
                    multiple=True
                ),
                ui.input_action_link("select_all_opp_matches", "Select all games"),
                ui.input_select(
                    "selected_opp_team_area",
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
            ui.output_ui("dynamic_content_opp_team"),
            padding="1.25rem",
        ),
        value="tab_3_val"
    )

def server_logic(input, output, session):
    
    @reactive.Effect
    @reactive.event(input.selected_opp_team)
    def update_match_choices():
        team_id = input.selected_opp_team()
        if team_id:
            new_choices = get_match_choices_for_team(match_df, team_id)
            ui.update_selectize(
                "selected_opp_matches",
                choices=new_choices,
                selected=[] 
            )
            
    @reactive.effect
    @reactive.event(input.select_all_opp_matches)
    def _select_all_opp_matches():
        team_id = input.selected_opp_team()
        if team_id:
            choices = get_match_choices_for_team(match_df, team_id)
            ui.update_selectize(
                "selected_opp_matches",
                selected=list(choices.keys())
            )

    @reactive.calc
    def filtered_team_events():
        team_id = input.selected_opp_team()
        selected_matches = input.selected_opp_matches()
        
      
        if not team_id or not selected_matches:
            return pd.DataFrame()
           
        filtered_events = event_df[
            (event_df["wy_team_id"] == int(float(team_id))) & 
            (event_df["wy_match_id"].astype(str).isin(selected_matches))
        ]
        return filtered_events

    @render.ui
    def dynamic_content_opp_team():
        area = input.selected_opp_team_area()
        if area == "Attack":
            return attack.attack_ui()
        elif area == "Set-Pieces":
            return set_pieces.set_pieces_ui()
        elif area == "Defence":
            return defense.defense_ui("opp_team")

    attack.attack_server(input, output, session, filtered_team_events, event_df, opp_team_choices)
    set_pieces.set_pieces_server(input, output, session, filtered_team_events)
    defense.defense_server(input, output, session, filtered_team_events, "opp_team")