import pandas as pd
from pathlib import Path
from shiny import ui, render, reactive
from . import comparison_tool_general as general

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

def load_team_data():
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_team_data.csv"
    return pd.read_csv(data_path)

def load_player_data():
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_player_data.csv"
    return pd.read_csv(data_path)

def load_team_player_duels_data():
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_team_player_match_duels.csv"
    return pd.read_csv(data_path)

def load_player_match_map():
    data_path = Path(__file__).parent.parent.parent / "data" / "american_athletic_womens_soccer_fall_2025_player_match_mapping.csv"
    return pd.read_csv(data_path)

def get_match_choices_for_team(df, team_id):
    if team_id is None:
        return {}
    team_id = int(float(team_id))
    team_matches = df[(df["home_team_id"].astype(float) == team_id) | (df["away_team_id"].astype(float) == team_id)]
    return dict(zip(team_matches["wy_match_id"].astype(str), team_matches["label_date"]))

def get_match_choices_for_player(map_df, match_df, player_id):
    if player_id is None:
        return {}
    player_id = int(float(player_id))
    player_matches = map_df[map_df["wy_player_id"].astype(float) == player_id]
    player_matches_joined = player_matches.merge(match_df, on="wy_match_id", how="left")
    return dict(zip(player_matches_joined["wy_match_id"].astype(str), player_matches_joined["label_date"]))

def _parse_match_ids(raw_matches):
    if isinstance(raw_matches, (tuple, list)):
        return [int(float(m)) for m in raw_matches if m]
    if raw_matches:
        return [int(float(raw_matches))]
    return []

def _empty_comparison_result(comp_type):
    return {
        "data": pd.DataFrame(),
        "name_col": "wy_team_name" if comp_type == "team" else "wy_player_name"
    }

def ui_content():
    return ui.nav_panel(
        "Comparison Tool",
        ui.div(
            ui.div("Comparison Tool", class_="sidebar-title"),
            ui.div(
                ui.layout_columns(
                    ui.div(
                        ui.input_radio_buttons(
                            "comparison_type",
                            "Comparison Type:",
                            choices={"team": "Team", "player": "Player"},
                            selected="team",
                            inline=True
                        ),
                        style="padding-top: 5px;"
                    ),
                    ui.output_ui("comparison_controls_ui"),
                    col_widths=[2, 10]
                ),
                style="padding: 1.25rem 0;"
            ),
            ui.div(
                ui.output_ui("dynamic_comparison_ui"),
                style="padding: 1.25rem 0;"
            )
        ),
        value="tab_5_val"
    )

def server_logic(input, output, session):
    team_player_duels_df = load_team_player_duels_data()
    team_df = load_team_data()
    player_df = load_player_data()
    team_choices = get_team_id()
    initial_team = list(team_choices.keys())[0] if team_choices else None
    
    match_df = load_match_data()
    map_df = load_player_match_map()
    
    initial_matches_team = get_match_choices_for_team(match_df, initial_team) if initial_team else {}
    
    @render.ui
    def comparison_controls_ui():
        comp_type = input.comparison_type()

        initial_player_choices_1 = get_player_name(initial_team) if initial_team else {}
        initial_player_1 = list(initial_player_choices_1.keys())[0] if initial_player_choices_1 else None
        
        if comp_type == "team":
            m_choices_1 = initial_matches_team
        else:
            m_choices_1 = get_match_choices_for_player(map_df, match_df, initial_player_1) if initial_player_1 else {}

        team1_items = [
            ui.input_selectize(
                "comp_team_1" if comp_type == "team" else "comp_player_team_1",
                "Team 1:", 
                choices=team_choices, 
                selected=initial_team
            )
        ]
        if comp_type == "player":
            team1_items.append(
                ui.input_selectize(
                    "comp_player_1", 
                    "Player 1:", 
                    choices=initial_player_choices_1, 
                    selected=initial_player_1
                )
            )
        
        team2_items = [
            ui.input_selectize(
                "comp_team_2" if comp_type == "team" else "comp_player_team_2",
                "Team 2:", 
                choices=team_choices, 
                selected=initial_team
            )
        ]
        if comp_type == "player":
            team2_items.append(
                ui.input_selectize(
                    "comp_player_2", 
                    "Player 2:", 
                    choices=initial_player_choices_1, 
                    selected=initial_player_1
                )
            )
        
        return ui.layout_columns(
            ui.div(ui.TagList(*team1_items)),
            ui.input_selectize(
                "comp_team_1_matches" if comp_type == "team" else "comp_player_1_matches",
                "Matches 1:", 
                choices=m_choices_1, 
                multiple=True
            ),
            ui.div(ui.TagList(*team2_items)),
            ui.input_selectize(
                "comp_team_2_matches" if comp_type == "team" else "comp_player_2_matches",
                "Matches 2:", 
                choices=m_choices_1, 
                multiple=True
            ),
            col_widths=[3, 3, 3, 3]
        )
    
    @reactive.Effect
    @reactive.event(input.comp_team_1)
    def update_team_1_matches():
        if input.comparison_type() == "team":
            team_id = input.comp_team_1()
            if team_id:
                new_matches = get_match_choices_for_team(match_df, team_id)
                ui.update_selectize(
                    "comp_team_1_matches",
                    choices=new_matches,
                    selected=None
                )
    
    @reactive.Effect
    @reactive.event(input.comp_team_2)
    def update_team_2_matches():
        if input.comparison_type() == "team":
            team_id = input.comp_team_2()
            if team_id:
                new_matches = get_match_choices_for_team(match_df, team_id)
                ui.update_selectize(
                    "comp_team_2_matches",
                    choices=new_matches,
                    selected=None
                )
    
    @reactive.Effect
    @reactive.event(input.comp_player_team_1)
    def update_player_1_choices():
        if input.comparison_type() == "player":
            team_id = input.comp_player_team_1()
            if team_id:
                new_player_choices = get_player_name(team_id)
                ui.update_selectize(
                    "comp_player_1",
                    choices=new_player_choices,
                    selected=None
                )
                ui.update_selectize(
                    "comp_player_1_matches",
                    choices={},
                    selected=None
                )
    
    @reactive.Effect
    @reactive.event(input.comp_player_1)
    def update_player_1_matches():
        if input.comparison_type() == "player":
            player_id = input.comp_player_1()
            if player_id:
                new_matches = get_match_choices_for_player(map_df, match_df, player_id)
                ui.update_selectize(
                    "comp_player_1_matches",
                    choices=new_matches,
                    selected=None
                )
    
    @reactive.Effect
    @reactive.event(input.comp_player_team_2)
    def update_player_2_choices():
        if input.comparison_type() == "player":
            team_id = input.comp_player_team_2()
            if team_id:
                new_player_choices = get_player_name(team_id)
                ui.update_selectize(
                    "comp_player_2",
                    choices=new_player_choices,
                    selected=None
                )
                ui.update_selectize(
                    "comp_player_2_matches",
                    choices={},
                    selected=None
                )
    
    @reactive.Effect
    @reactive.event(input.comp_player_2)
    def update_player_2_matches():
        if input.comparison_type() == "player":
            player_id = input.comp_player_2()
            if player_id:
                new_matches = get_match_choices_for_player(map_df, match_df, player_id)
                ui.update_selectize(
                    "comp_player_2_matches",
                    choices=new_matches,
                    selected=None
                )
    
    @reactive.calc
    def filtered_comparison_data():
        comp_type = input.comparison_type()

        if comp_type == "team":
            group_col = "wy_team_id"
            entities = [
                {"id": input.comp_team_1(), "matches": input.comp_team_1_matches(), "label": "Entity_1"},
                {"id": input.comp_team_2(), "matches": input.comp_team_2_matches(), "label": "Entity_2"}
            ]
        else:
            group_col = "wy_player_id"
            entities = [
                {"id": input.comp_player_1(), "matches": input.comp_player_1_matches(), "label": "Entity_1"},
                {"id": input.comp_player_2(), "matches": input.comp_player_2_matches(), "label": "Entity_2"}
            ]

        processed_results = []

        for ent in entities:
            c_id = int(float(ent["id"])) if ent["id"] else None
            c_matches = _parse_match_ids(ent["matches"])

            if not c_id or not c_matches:
                return _empty_comparison_result(comp_type)

            temp_df = team_player_duels_df[
                (team_player_duels_df[group_col] == c_id) &
                (team_player_duels_df["wy_match_id"].isin(c_matches))
            ]

            agg_df = temp_df.groupby(group_col).agg(
                total_off_duels=("offensive_duels_count", "sum"),
                total_def_duels=("defensive_duels_count", "sum"),
                total_ground_kept=("ground_duel_kept_possession_count", "sum"),
                total_ground_prog=("ground_duel_progressed_with_ball_count", "sum"),
                total_ground_rec=("ground_duel_recovered_possession_count", "sum"),
                total_ground_stop=("ground_duel_stopped_progress_count", "sum"),
                total_aerial_touch=("aerial_duel_first_touch_count", "sum"),
                total_aerial_count=("aerial_duel_count", "sum")
            ).reset_index()

            agg_df["comparison_label"] = ent["label"]
            processed_results.append(agg_df)

        df_final = pd.concat(processed_results).fillna(0)

        if df_final.empty or len(df_final) < 2:
            return _empty_comparison_result(comp_type)

        df_final["ground_kept_pct"] = df_final["total_ground_kept"] / df_final["total_off_duels"]
        df_final["ground_prog_pct"] = df_final["total_ground_prog"] / df_final["total_off_duels"]
        df_final["ground_rec_pct"] = df_final["total_ground_rec"] / df_final["total_def_duels"]
        df_final["ground_stop_pct"] = df_final["total_ground_stop"] / df_final["total_def_duels"]
        df_final["aerial_win_pct"] = df_final["total_aerial_touch"] / df_final["total_aerial_count"]

        df_final = df_final.fillna(0)
        if input.comparison_type() == "team":
            df_final_joined = df_final.merge(team_df, on="wy_team_id", how="left")
        else:
            df_final_joined = df_final.merge(player_df, on="wy_player_id", how="left")

        return {
            "data": df_final_joined,
            "name_col": "wy_team_name" if input.comparison_type() == "team" else "wy_player_name"
        }

    @render.ui
    def dynamic_comparison_ui():
        return general.general_ui()

    general.general_server(input, output, session, filtered_comparison_data)