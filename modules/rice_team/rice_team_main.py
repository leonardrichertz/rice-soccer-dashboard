import pandas as pd
from shiny import ui, render, reactive
from .. import data_access
from .. import team_defense as defense
from . import rice_team_attack as attack
from . import rice_team_setpiece as setpiece

def get_match_choices():
    df = data_access.load_match_data()
    team_id = 61585
    team_matches = df[(df["home_team_id"] == team_id) | (df["away_team_id"] == team_id)]
    return dict(zip(team_matches["wy_match_id"].astype(str), team_matches["label_date"]))

def ui_content():
    match_choices = get_match_choices()
    return ui.nav_panel(
        "Rice Team",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div("Rice Team", class_="sidebar-title"),
                ui.input_selectize(
                    "selected_rice_matches",
                    "Select Matches:",
                    choices=match_choices,
                    multiple=True
                ),
                ui.input_action_link("select_all_rice_matches", "Select all games"),
                ui.input_select(
                    "selected_rice_team_area",
                    "Area:",
                    choices={
                        "Attack": "Attack",
                        "Defense": "Defense",
                        "Set-Pieces": "Set-Pieces"
                    }
                ),
                open="always",
                width="340px",
            ),
            ui.output_ui("dynamic_content_rice_team"),
            padding="1.25rem",
        ),
        value="tab_1_val"
    )

def server_logic(input, output, session):
    event_df = data_access.load_event_data()

    @reactive.effect
    @reactive.event(input.select_all_rice_matches)
    def _select_all_rice_matches():
        ui.update_selectize(
            "selected_rice_matches",
            selected=list(get_match_choices().keys())
        )

    @reactive.calc
    def filtered_events():
        selected = input.selected_rice_matches()
        if not selected:
            return pd.DataFrame()
        df = event_df[event_df["wy_match_id"].astype(str).isin(selected)]
        return df[df["wy_team_id"] == 61585]
    
    @output
    @render.ui
    def dynamic_content_rice_team():
        area = input.selected_rice_team_area()
        if area == "Attack":
            return attack.attack_ui()
        elif area == "Defense":
            return defense.defense_ui("rice_team")
        elif area == "Set-Pieces":
            return setpiece.setpiece_ui()

    attack.attack_server(input, output, session, filtered_events)
    defense.defense_server(input, output, session, filtered_events, "rice_team")
    setpiece.setpiece_server(input, output, session, filtered_events)