from shiny import ui, render
from .. import plot_style as ps
import pandas as pd

def parse_timestamp(t):
    parts = str(t).split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

def get_free_kicks_leading_to_shot(df):
    df = df.copy()
    df["timestamp"] = df["timestamp"].apply(parse_timestamp)

    fk_df  = df[df["type_primary"] == "free_kick"]
    shots  = df[df["type_primary"] == "shot"]

    fk_with_shot = []

    for _, fk_row in fk_df.iterrows():
        same_shots = shots[
            (shots["possession_id"] == fk_row["possession_id"]) &
            (shots["wy_team_id"]    == fk_row["wy_team_id"])
        ]
        for _, shot_row in same_shots.iterrows():
            if 0 < (shot_row["timestamp"] - fk_row["timestamp"]) <= 10:
                fk_with_shot.append(fk_row)
                break

    return pd.DataFrame(fk_with_shot)

def get_corners_leading_to_shot(df):
    df = df.copy()
    df["timestamp"] = df["timestamp"].apply(parse_timestamp)

    corner_df = df[df["type_primary"] == "corner"]
    shots     = df[df["type_primary"] == "shot"]

    corner_with_shot = []

    for _, corner_row in corner_df.iterrows():
        same_shots = shots[
            (shots["possession_id"] == corner_row["possession_id"]) &
            (shots["wy_team_id"]    == corner_row["wy_team_id"])
        ]
        for _, shot_row in same_shots.iterrows():
            if 0 < (shot_row["timestamp"] - corner_row["timestamp"]) <= 5:
                corner_with_shot.append(corner_row)
                break

    return pd.DataFrame(corner_with_shot)

def free_kicks_ui():
    return ui.card(
        ui.card_header("Free Kick Locations"),
        ui.output_plot("free_kicks_plot"),
    )

def free_kicks_server(input, output, session, filtered_events):
    @render.plot
    def free_kicks_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        fk_df = df[df["type_primary"] == "free_kick"].copy()

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if fk_df.empty:
            return fig

        fk_led_to_shot = get_free_kicks_leading_to_shot(df)
        fk_led_to_shot_index = set(fk_led_to_shot.index) if not fk_led_to_shot.empty else set()

        fk_shots  = fk_df[
            fk_df["type_secondary"].str.contains("free_kick_shot", case=False, na=False)
        ]
        fk_passes = fk_df[
            ~fk_df["type_secondary"].str.contains("free_kick_shot", case=False, na=False)
        ]

        fk_passes_shot    = fk_passes[fk_passes.index.isin(fk_led_to_shot_index)]
        fk_passes_no_shot = fk_passes[~fk_passes.index.isin(fk_led_to_shot_index)]

        for subset, color, label in [
            (fk_passes_no_shot, ps.ON_TARGET_COLOR,  "Pass / Cross"),
            (fk_passes_shot,    ps.GOAL_COLOR,       "Pass / Cross → Shot (10s)"),
            (fk_shots,          ps.OFF_TARGET_COLOR, "Shot"),
        ]:
            if not subset.empty:
                pitch.scatter(
                    subset["location_x"], subset["location_y"],
                    s=150, ax=ax,
                    color=color, edgecolors="black", linewidths=1.2,
                    label=label
                )

        ax.legend(loc="upper left", fontsize=ps.LEGEND_FONTSIZE)
        return fig

def corner_map_ui():
    return ui.card(
        ui.card_header("Corner Deliveries"),
        ui.output_plot("corner_map_plot"),
    )


def corner_map_server(input, output, session, filtered_events):
    @render.plot
    def corner_map_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        corner_df = df[df["type_primary"] == "corner"].copy()

        pitch, fig, ax = ps.new_pitch(vertical=True, half=True, figsize=(5, 7))

        if corner_df.empty:
            return fig

        corners_with_shot = get_corners_leading_to_shot(df)
        shot_index = set(corners_with_shot.index) if not corners_with_shot.empty else set()

        other_player_color = ps.OTHER_COLOR

        player_counts = corner_df["player_name"].value_counts()
        if len(player_counts) <= 4:
            top_players = player_counts.index.tolist()
            show_other  = False
        else:
            top_players = player_counts.head(4).index.tolist()
            show_other  = True

        def player_color(name):
            if name in top_players:
                return ps.ACCENT_COLORS[top_players.index(name)]
            return other_player_color

        for _, row in corner_df.iterrows():
            color  = player_color(row["player_name"])
            marker = "s" if row.name in shot_index else "o"
            pitch.scatter(
                row["pass_end_location_x"], row["pass_end_location_y"],
                s=150, color=color, edgecolors="black",
                linewidths=1.2, marker=marker, zorder=4, ax=ax
            )

        for rank, name in enumerate(top_players):
            ax.scatter([], [], color=ps.ACCENT_COLORS[rank], edgecolors="black",
                       linewidths=1.2, marker="o", label=name)
        if show_other:
            ax.scatter([], [], color=other_player_color, edgecolors="black",
                       linewidths=1.2, marker="o", label="Other")

        ax.scatter([], [], color="none", edgecolors="black", linewidths=1.2,
                   marker="o", label="No Shot")
        ax.scatter([], [], color="none", edgecolors="black", linewidths=1.2,
                   marker="s", label="Shot Within 5s")

        ax.legend(loc="lower left", fontsize=8)
        ax.set_title(f"n = {len(corner_df)}", fontsize=10, color=ps.RICE_GRAY, loc="right")
        return fig

def free_kick_cross_map_ui():
    return ui.card(
        ui.card_header("Free Kick Cross Deliveries"),
        ui.output_plot("free_kick_cross_map_plot"),
    )

def free_kick_cross_map_server(input, output, session, filtered_events):
    @render.plot
    def free_kick_cross_map_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        fk_cross_df = df[
            df["type_secondary"].str.contains("free_kick_cross", case=False, na=False)
        ].copy()

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if fk_cross_df.empty:
            return fig

        other_player_color = ps.OTHER_COLOR

        player_counts = fk_cross_df["player_name"].value_counts()
        if len(player_counts) <= 4:
            top_players = player_counts.index.tolist()
            show_other  = False
        else:
            top_players = player_counts.head(4).index.tolist()
            show_other  = True

        def player_color(name):
            if name in top_players:
                return ps.ACCENT_COLORS[top_players.index(name)]
            return other_player_color

        for _, row in fk_cross_df.iterrows():
            pitch.arrows(
                row["location_x"], row["location_y"],
                row["pass_end_location_x"], row["pass_end_location_y"],
                width=1, headwidth=5, headlength=5,
                color=player_color(row["player_name"]), alpha=0.7, ax=ax
            )

        for rank, name in enumerate(top_players):
            ax.plot([], [], color=ps.ACCENT_COLORS[rank], label=name, linewidth=2)
        if show_other:
            ax.plot([], [], color=other_player_color, label="Other", linewidth=2)

        ax.legend(loc="upper left", fontsize=8)
        ax.set_title(f"n = {len(fk_cross_df)}", fontsize=10, color=ps.RICE_GRAY, loc="right")
        return fig

def setpiece_ui():
    return ui.div(
        ui.div("Set-Piece Delivery", class_="section-heading"),
        ui.layout_column_wrap(
            free_kicks_ui(),
            corner_map_ui(),
            free_kick_cross_map_ui(),
            width="420px",
        ),
    )

def setpiece_server(input, output, session, filtered_events):
    free_kicks_server(input, output, session, filtered_events)
    corner_map_server(input, output, session, filtered_events)
    free_kick_cross_map_server(input, output, session, filtered_events)
