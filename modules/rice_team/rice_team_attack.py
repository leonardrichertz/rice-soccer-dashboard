from shiny import ui, render
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from .. import plot_style as ps

def parse_timestamp(t):
    parts = str(t).split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

def get_key_passes(df):
    df = df.copy()
    df["timestamp"] = df["timestamp"].apply(parse_timestamp)

    passes = df[df["type_primary"] == "pass"]
    shots = df[df["type_primary"] == "shot"]

    key_passes = []

    for pass_index, pass_row in passes.iterrows():
        same_shots = shots[
            (shots["possession_id"] == pass_row["possession_id"]) &
            (shots["wy_team_id"] == pass_row["wy_team_id"])
        ]

        for shot_index, shot_row in same_shots.iterrows():
            if 0 < (shot_row["timestamp"] - pass_row["timestamp"]) <= 5:
                row = pass_row.copy()
                row["shot_is_goal"] = shot_row["shot_is_goal"]
                key_passes.append(row)
                break

    return pd.DataFrame(key_passes)

def get_possessions_with_shot(df):
    shots = df[df["type_primary"] == "shot"]

    possession_ids_with_shot = set(shots["possession_id"].unique())

    return df[df["possession_id"].isin(possession_ids_with_shot)]

def get_shots_by_15_min(df):
    shots = df[df["type_primary"] == "shot"].copy()

    bins   = [0, 15, 30, 45, 60, 75, 90]
    labels = ["0-15", "16-30", "31-45", "46-60", "61-75", "76-90"]

    shots["period_15"] = pd.cut(shots["minute"], bins=bins, labels=labels, right=True)

    result = shots.groupby(["wy_match_id", "opponent_team_name", "period_15"], observed=True).size().reset_index(name="shots")
    result["period_15"] = pd.Categorical(result["period_15"], categories=labels, ordered=True)
    return result.sort_values(["wy_match_id", "period_15"]).reset_index(drop=True)

def shots_ui():
    return ui.card(
        ui.card_header("Shot Map"),
        ui.output_plot("shot_map_plot"),
    )

def shots_server(input, output, session, filtered_events):
    @render.plot
    def shot_map_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        shots_df = df[df["type_primary"] == "shot"].copy()

        pitch, fig, ax = ps.new_pitch(vertical=True, half=True, figsize=(5, 7))

        if shots_df.empty:
            return fig

        goals      = shots_df[shots_df["type_secondary"].str.contains("goal", case=False, na=False)]
        on_target  = shots_df[
            (shots_df["shot_on_target"].astype(str).str.upper() == "TRUE") &
            ~shots_df["type_secondary"].str.contains("goal", case=False, na=False)
        ]
        off_target = shots_df[
            (shots_df["shot_on_target"].astype(str).str.upper() != "TRUE") &
            ~shots_df["type_secondary"].str.contains("goal", case=False, na=False)
        ]

        for subset, color, label in [
            (off_target, ps.OFF_TARGET_COLOR, "Off Target"),
            (on_target,  ps.ON_TARGET_COLOR,  "On Target"),
            (goals,      ps.GOAL_COLOR,       "Goal"),
        ]:
            if not subset.empty:
                pitch.scatter(
                    subset["location_x"], subset["location_y"],
                    s=150, ax=ax,
                    color=color, edgecolors="black", linewidths=1.2,
                    label=label
                )

        ax.legend(loc="upper right", fontsize=ps.LEGEND_FONTSIZE)
        return fig

def attack_heatmap_ui():
    return ui.card(
        ui.card_header("Attacking Activity Heatmap"),
        ui.output_plot("attack_heatmap_plot"),
    )

def attack_heatmap_server(input, output, session, filtered_events):
    @render.plot
    def attack_heatmap_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if df.empty:
            return fig

        pitch.kdeplot(
            df["location_x"], df["location_y"],
            ax=ax,
            cmap="RdYlGn_r",
            fill=True,
            levels=100,
            alpha=0.85,
            bw_adjust=0.8,
            thresh=0.10,
        )

        return fig

def progressive_passes_own_ui():
    return ui.card(
        ui.card_header("Progressive Passes — Own Third"),
        ui.output_plot("progressive_passes_plot_own_third"),
    )

def progressive_passes_middle_ui():
    return ui.card(
        ui.card_header("Progressive Passes — Middle Third"),
        ui.output_plot("progressive_passes_plot_middle_third"),
    )

def progressive_passes_final_ui():
    return ui.card(
        ui.card_header("Progressive Passes — Final Third"),
        ui.output_plot("progressive_passes_plot_final_third"),
    )

def progressive_passes_server(input, output, session, filtered_events):

    def get_progressive_passes():
        events = filtered_events()
        if events is None or events.empty:
            return None
        return events[
            events["type_secondary"].str.contains("progressive_pass", case=False, na=False)
            & (events["pass_accurate"].astype(str).str.upper() == "TRUE")
        ].copy()

    def draw_progressive_passes_for_third(third_x_start, third_x_end, legend_position):
        other_player_color = ps.OTHER_COLOR

        progressive_passes = get_progressive_passes()
        if progressive_passes is None:
            return None

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        ax.axvline(33.33, color=ps.PITCH_LINE_COLOR, linestyle="--", linewidth=1.2, alpha=0.7)
        ax.axvline(66.67, color=ps.PITCH_LINE_COLOR, linestyle="--", linewidth=1.2, alpha=0.7)

        passes_in_third = progressive_passes[
            (progressive_passes["location_x"] >= third_x_start) &
            (progressive_passes["location_x"] <  third_x_end)
        ]

        unique_players_in_third = (
            passes_in_third["player_name"].value_counts()
            if not passes_in_third.empty and "player_name" in passes_in_third.columns
            else []
        )

        if len(unique_players_in_third) <= 4:
            top_players_in_third_by_pass_count = unique_players_in_third.index.tolist()
            show_other_category = False
        else:
            top_players_in_third_by_pass_count = unique_players_in_third.head(3).index.tolist()
            show_other_category = True

        for _, pass_row in passes_in_third.iterrows():
            arrow_color = (
                ps.ACCENT_COLORS[top_players_in_third_by_pass_count.index(pass_row["player_name"])]
                if pass_row["player_name"] in top_players_in_third_by_pass_count
                else other_player_color
            )
            pitch.arrows(
                pass_row["location_x"],          pass_row["location_y"],
                pass_row["pass_end_location_x"], pass_row["pass_end_location_y"],
                width=1, headwidth=5, headlength=5,
                color=arrow_color, alpha=0.6, ax=ax,
            )

        for rank, player_name in enumerate(top_players_in_third_by_pass_count):
            ax.scatter([], [], color=ps.ACCENT_COLORS[rank], label=player_name)
        if show_other_category:
            ax.scatter([], [], color=other_player_color, label="Other")
        ax.legend(loc=legend_position, fontsize=ps.LEGEND_FONTSIZE)

        ax.set_title(f"n = {len(passes_in_third)}", fontsize=10, color=ps.RICE_GRAY, loc="right")

        return fig

    @render.plot
    def progressive_passes_plot_own_third():
        return draw_progressive_passes_for_third(0, 33.33, "upper right")

    @render.plot
    def progressive_passes_plot_middle_third():
        return draw_progressive_passes_for_third(33.33, 66.67, "upper left")

    @render.plot
    def progressive_passes_plot_final_third():
        return draw_progressive_passes_for_third(66.67, 100, "upper left")


def final_third_passes_ui():
    return ui.card(
        ui.card_header("Passes to Final Third"),
        ui.output_plot("final_third_passes_plot"),
    )


def final_third_passes_server(input, output, session, filtered_events):
    @render.plot
    def final_third_passes_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        pass_df = df[
            df["type_secondary"].str.contains("pass_to_final_third", case=False, na=False) &
            (df["pass_accurate"].astype(str).str.upper() == "TRUE")
        ].copy()

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if pass_df.empty:
            return fig

        pitch.arrows(
            pass_df["location_x"], pass_df["location_y"],
            pass_df["pass_end_location_x"], pass_df["pass_end_location_y"],
            width=1, headwidth=5, headlength=5,
            color=ps.RICE_BLUE, alpha=0.7, ax=ax
        )

        ax.set_title(f"n = {len(pass_df)}", fontsize=10, color=ps.RICE_GRAY, loc="right")
        return fig

def progressive_runs_ui():
    return ui.card(
        ui.card_header("Progressive Run Map"),
        ui.output_plot("progressive_runs_plot"),
    )

def progressive_runs_server(input, output, session, filtered_events):
    @render.plot
    def progressive_runs_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        prog_df = df[
            df["type_secondary"].str.contains("progressive_run", case=False, na=False)
        ].copy()

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if prog_df.empty:
            return fig

        pitch.arrows(
            prog_df["location_x"], prog_df["location_y"],
            prog_df["carry_end_location_x"], prog_df["carry_end_location_y"],
            width=1, headwidth=5, headlength=5,
            color=ps.RICE_BLUE, alpha=0.7, ax=ax
        )

        ax.set_title(f"n = {len(prog_df)}", fontsize=10, color=ps.RICE_GRAY, loc="right")
        return fig

def xg_accumulator_ui():
    return ui.card(
        ui.card_header("xG Accumulator"),
        ui.output_plot("xg_accumulator_plot"),
    )


def xg_accumulator_server(input, output, session, filtered_events):
    @render.plot
    def xg_accumulator_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        shots_df = df[
            (df["type_primary"] == "shot") &
            (df["shot_post_shot_xg"].notna())
        ].copy()

        shots_df["minute_decimal"] = shots_df["minute"] + shots_df["second"] / 60
        shots_df["shot_post_shot_xg"] = pd.to_numeric(shots_df["shot_post_shot_xg"], errors="coerce")

        fig, ax = ps.new_chart(figsize=(10, 5))

        for i, (match_id, match_df) in enumerate(shots_df.groupby("wy_match_id")):
            match_df = match_df.sort_values("minute_decimal")
            match_df["cumulative_xg"] = match_df["shot_post_shot_xg"].cumsum()

            label = f"Rice vs. {match_df['opponent_team_name'].iloc[0]}"

            minutes = [0] + list(match_df["minute_decimal"]) + [90]
            cumxg   = [0] + list(match_df["cumulative_xg"]) + [match_df["cumulative_xg"].iloc[-1]]

            color = ps.ACCENT_COLORS[i % len(ps.ACCENT_COLORS)]
            ax.step(minutes, cumxg, where="post", linewidth=2, label=label, color=color)

            goals = match_df[match_df["shot_is_goal"].astype(str).str.upper() == "TRUE"]
            for _, goal in goals.iterrows():
                ax.axvline(
                    x=goal["minute_decimal"],
                    color=color,
                    linestyle="--",
                    linewidth=1.2,
                    alpha=0.7
                )

        ax.set_xlabel("Minute", fontsize=ps.AXIS_LABEL_FONTSIZE)
        ax.set_ylabel("Cumulative xG", fontsize=ps.AXIS_LABEL_FONTSIZE)
        ax.legend(loc="upper left", fontsize=ps.LEGEND_FONTSIZE)
        ax.set_xlim(0, 90)

        return fig

def key_passes_ui():
    return ui.card(
        ui.card_header("Key Passes"),
        ui.output_plot("key_passes_plot"),
    )

def key_passes_server(input, output, session, filtered_events):
    @render.plot
    def key_passes_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        kp = get_key_passes(df)

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if kp.empty:
            return fig

        pitch.arrows(
            kp["location_x"],          kp["location_y"],
            kp["pass_end_location_x"], kp["pass_end_location_y"],
            width=1, headwidth=5, headlength=5,
            color=ps.RICE_BLUE, alpha=0.7, ax=ax,
        )

        ax.set_title(f"n = {len(kp)}", fontsize=10, color=ps.RICE_GRAY, loc="right")
        return fig


def possession_with_shot_ui():
    return ui.card(
        ui.card_header("Possession Starts — Shot Within 10s"),
        ui.output_plot("possession_with_shot_plot"),
    )

def possession_with_shot_server(input, output, session, filtered_events):
    @render.plot
    def possession_with_shot_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        df = df.copy()
        df["timestamp"] = df["timestamp"].apply(parse_timestamp)

        shots = df[df["type_primary"] == "shot"]

        quick_shot_starts = []
        for poss_id, poss_df in df.groupby("possession_id"):
            poss_df = poss_df.sort_values("timestamp")
            poss_start_row = poss_df.iloc[0]

            poss_shots = shots[shots["possession_id"] == poss_id]
            for _, shot_row in poss_shots.iterrows():
                if 0 < (shot_row["timestamp"] - poss_start_row["timestamp"]) <= 10:
                    quick_shot_starts.append(poss_start_row)
                    break

        starts_df = pd.DataFrame(quick_shot_starts)

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if starts_df.empty:
            return fig

        pitch.scatter(
            starts_df["location_x"], starts_df["location_y"],
            s=120, color=ps.ON_TARGET_COLOR, edgecolors="black",
            linewidths=1.2, zorder=4, ax=ax,
        )

        ax.set_title(f"n = {len(starts_df)}", fontsize=10, color=ps.RICE_GRAY, loc="right")
        return fig

def shots_by_15_ui():
    return ui.card(
        ui.card_header("Shots by 15-Minute Interval"),
        ui.output_plot("shots_by_15_plot"),
    )

def shots_by_15_server(input, output, session, filtered_events):
    @render.plot
    def shots_by_15_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        data = get_shots_by_15_min(df)

        fig, ax = ps.new_chart(figsize=(10, 5))

        x_labels = ["0-15", "16-30", "31-45", "46-60", "61-75", "76-90"]
        x = np.arange(len(x_labels))

        match_ids = data["wy_match_id"].unique()
        n_matches = len(match_ids)
        bar_width = 0.8 / n_matches if n_matches else 0.8

        for i, match_id in enumerate(match_ids):
            match_df = data[data["wy_match_id"] == match_id]
            label = f"Rice vs. {match_df['opponent_team_name'].iloc[0]}"

            period_to_shots = dict(zip(match_df["period_15"].astype(str), match_df["shots"]))
            y = [period_to_shots.get(lbl, 0) for lbl in x_labels]

            offset = (i - (n_matches - 1) / 2) * bar_width
            ax.bar(
                x + offset, y, width=bar_width, label=label,
                color=ps.ACCENT_COLORS[i % len(ps.ACCENT_COLORS)],
                edgecolor="white", linewidth=0.5,
            )

        ax.set_xticks(x)
        ax.set_xticklabels(x_labels)
        ax.legend(loc="upper left", fontsize=ps.LEGEND_FONTSIZE)
        ax.set_xlabel("Minute Interval", fontsize=ps.AXIS_LABEL_FONTSIZE)
        ax.set_ylabel("Shots", fontsize=ps.AXIS_LABEL_FONTSIZE)
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

        return fig


def attack_ui():
    return ui.div(
        ui.div("Shot & Chance Creation", class_="section-heading"),
        ui.layout_column_wrap(
            xg_accumulator_ui(),
            shots_by_15_ui(),
            width="480px",
        ),
        ui.layout_column_wrap(
            shots_ui(),
            attack_heatmap_ui(),
            possession_with_shot_ui(),
            key_passes_ui(),
            final_third_passes_ui(),
            progressive_runs_ui(),
            width="480px",
        ),
        ui.div("Progressive Passes by Third", class_="section-heading"),
        ui.layout_column_wrap(
            progressive_passes_own_ui(),
            progressive_passes_middle_ui(),
            progressive_passes_final_ui(),
            width="380px",
        ),
    )

def attack_server(input, output, session, filtered_events):
    shots_server(input, output, session, filtered_events)
    progressive_passes_server(input, output, session, filtered_events)
    final_third_passes_server(input, output, session, filtered_events)
    progressive_runs_server(input, output, session, filtered_events)
    attack_heatmap_server(input, output, session, filtered_events)
    xg_accumulator_server(input, output, session, filtered_events)
    key_passes_server(input, output, session, filtered_events)
    possession_with_shot_server(input, output, session, filtered_events)
    shots_by_15_server(input, output, session, filtered_events)
