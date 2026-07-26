from shiny import ui, render
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from .. import plot_style as ps


def parse_timestamp(t):
    parts = str(t).split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

def get_shots_against_by_15_min(df):
    shots = df[df["type_primary"] == "shot_against"].copy()
    bins   = [0, 15, 30, 45, 60, 75, 90]
    labels = ["0-15", "16-30", "31-45", "46-60", "61-75", "76-90"]
    shots["period_15"] = pd.cut(shots["minute"], bins=bins, labels=labels, right=True)
    result = shots.groupby(["wy_match_id", "opponent_team_name", "period_15"], observed=True).size().reset_index(name="shots")
    result["period_15"] = pd.Categorical(result["period_15"], categories=labels, ordered=True)
    return result.sort_values(["wy_match_id", "period_15"]).reset_index(drop=True)


def defensive_events_ui():
    return ui.card(
        ui.card_header("Defensive Activity Heatmap"),
        ui.output_plot("defensive_events_plot"),
    )

def defensive_events_server(input, output, session, filtered_events):
    @render.plot
    def defensive_events_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        defensive_df = df[
            df["type_primary"].str.contains("interception", case=False, na=False) |
            df["type_secondary"].str.contains("defensive_duel|sliding_tackle|shot_block", case=False, na=False)
        ].copy()

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if not defensive_df.empty:
            pitch.kdeplot(
                defensive_df["location_x"],
                defensive_df["location_y"],
                ax=ax,
                cmap="RdYlGn_r",
                fill=True,
                levels=100,
                alpha=0.85,
                bw_adjust=0.8,
                thresh=0.10,
            )

        return fig


def shots_against_ui():
    return ui.card(
        ui.card_header("Shots Against"),
        ui.output_plot("shots_against_plot"),
    )

def shots_against_server(input, output, session, filtered_events):
    @render.plot
    def shots_against_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        shots_df = df[df["type_primary"] == "shot_against"].copy()

        pitch, fig, ax = ps.new_pitch(vertical=True, half=False, figsize=(5, 7))

        if shots_df.empty:
            return fig

        goals_against = shots_df[
            shots_df["type_secondary"].str.contains("conceded_goal", case=False, na=False)
        ]
        non_goal_shots = shots_df[
            ~shots_df["type_secondary"].str.contains("conceded_goal", case=False, na=False)
        ]

        for subset, color, label in [
            (non_goal_shots, ps.ON_TARGET_COLOR, "Shot Against"),
            (goals_against, ps.OFF_TARGET_COLOR, "Goal Against"),
        ]:
            if not subset.empty:
                pitch.scatter(
                    subset["location_x"],
                    subset["location_y"],
                    s=150,
                    ax=ax,
                    color=color,
                    edgecolors="black",
                    linewidths=1.2,
                    label=label
                )

        ax.set_xlim(14, 86)
        ax.set_ylim(-2, 20)
        ax.legend(loc="upper right", fontsize=ps.LEGEND_FONTSIZE)
        return fig


def shots_against_by_15_ui():
    return ui.card(
        ui.card_header("Shots Conceded by 15-Minute Interval"),
        ui.output_plot("shots_against_by_15_plot"),
    )

def shots_against_by_15_server(input, output, session, filtered_events):
    @render.plot
    def shots_against_by_15_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        data = get_shots_against_by_15_min(df)

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
        ax.set_ylabel("Shots Conceded", fontsize=ps.AXIS_LABEL_FONTSIZE)
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
        return fig


def duel_map_ui():
    return ui.card(
        ui.card_header("Duel Win % by Zone"),
        ui.output_plot("duel_map_plot"),
    )

def duel_map_server(input, output, session, filtered_events):
    @render.plot
    def duel_map_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        ground_duels = df[df["type_secondary"].str.contains("ground_duel", case=False, na=False)]
        aerial_duels = df[df["type_secondary"].str.contains("aerial_duel", case=False, na=False)]

        ground_won = ground_duels[
            (ground_duels["ground_duel_kept_possession"] == True) |
            (ground_duels["ground_duel_recovered_possession"] == True)
        ]
        ground_lost = ground_duels[
            (ground_duels["ground_duel_kept_possession"] != True) &
            (ground_duels["ground_duel_recovered_possession"] != True)
        ]
        aerial_won = aerial_duels[
            aerial_duels["aerial_duel_first_touch"] == True
        ]
        aerial_lost = aerial_duels[
            aerial_duels["aerial_duel_first_touch"] != True
        ]

        won_df = pd.concat([ground_won, aerial_won]).copy()
        lost_df = pd.concat([ground_lost, aerial_lost]).copy()
        won_df["won"] = 1
        lost_df["won"] = 0
        all_duels = pd.concat([won_df, lost_df])

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        cmap = plt.cm.RdYlGn
        norm = plt.Normalize(vmin=0, vmax=1)

        x_edges = [0, 33.3, 66.6, 100]
        y_edges = [0, 33.3, 66.6, 100]

        for row in range(3):
            for col in range(3):
                x_min, x_max = x_edges[col], x_edges[col + 1]
                y_min, y_max = y_edges[row], y_edges[row + 1]

                zone = all_duels[
                    (all_duels["location_x"] >= x_min) & (all_duels["location_x"] < x_max) &
                    (all_duels["location_y"] >= y_min) & (all_duels["location_y"] < y_max)
                ]

                total = len(zone)
                if total == 0:
                    continue

                win_pct = zone["won"].sum() / total
                color = cmap(norm(win_pct))

                rect = plt.Rectangle(
                    (x_min, y_min), x_max - x_min, y_max - y_min,
                    linewidth=1.5, edgecolor=ps.PITCH_LINE_COLOR,
                    facecolor=color, alpha=0.9, zorder=2
                )
                ax.add_patch(rect)

                ax.text(
                    (x_min + x_max) / 2, (y_min + y_max) / 2,
                    f"{win_pct * 100:.0f}%\n({total})",
                    ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color="black", zorder=3
                )

        return fig


def turnover_map_ui():
    return ui.card(
        ui.card_header("Turnover Map"),
        ui.output_plot("turnover_map_plot"),
    )

def turnover_map_server(input, output, session, filtered_events):
    @render.plot
    def turnover_map_plot():
        df = filtered_events()
        if df is None or df.empty:
            return None

        df = df.copy()
        df["timestamp"] = df["timestamp"].apply(parse_timestamp)

        turnover_df = df[df["type_secondary"].str.contains("loss", case=False, na=False)].copy()

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if turnover_df.empty:
            return fig

        colors = []
        valid_indices = []
        for idx, row in turnover_df.iterrows():
            window = df[
                (df["timestamp"] > row["timestamp"]) &
                (df["timestamp"] <= row["timestamp"] + 10)
            ]
            if window["type_secondary"].str.contains("conceded_goal", case=False, na=False).any():
                colors.append(ps.OFF_TARGET_COLOR)
                valid_indices.append(idx)
            elif window["type_primary"].str.contains("shot", case=False, na=False).any():
                colors.append(ps.ON_TARGET_COLOR)
                valid_indices.append(idx)

        turnover_df = turnover_df.loc[valid_indices]

        plot_x = turnover_df.apply(
            lambda row: row["pass_end_location_x"] if row["type_primary"] == "pass" else row["location_x"], axis=1
        )
        plot_y = turnover_df.apply(
            lambda row: row["pass_end_location_y"] if row["type_primary"] == "pass" else row["location_y"], axis=1
        )

        pitch.scatter(
            plot_x, plot_y,
            s=150, ax=ax, color=colors, edgecolors="black", linewidths=1.2,
        )

        if ps.OFF_TARGET_COLOR in colors:
            ax.scatter([], [], color=ps.OFF_TARGET_COLOR, edgecolors="black", label="Goal Conceded")
        if ps.ON_TARGET_COLOR in colors:
            ax.scatter([], [], color=ps.ON_TARGET_COLOR, edgecolors="black", label="Shot Conceded")
        ax.legend(loc="upper right", fontsize=ps.LEGEND_FONTSIZE)

        ax.set_title(f"n = {len(turnover_df)}", fontsize=10, color=ps.RICE_GRAY, loc="right")
        return fig


def defense_ui():
    return ui.div(
        ui.div("Defensive Overview", class_="section-heading"),
        ui.layout_column_wrap(
            defensive_events_ui(),
            duel_map_ui(),
            width="480px",
        ),
        ui.layout_column_wrap(
            shots_against_ui(),
            shots_against_by_15_ui(),
            turnover_map_ui(),
            width="480px",
        ),
    )

def defense_server(input, output, session, filtered_events):
    defensive_events_server(input, output, session, filtered_events)
    shots_against_server(input, output, session, filtered_events)
    shots_against_by_15_server(input, output, session, filtered_events)
    duel_map_server(input, output, session, filtered_events)
    turnover_map_server(input, output, session, filtered_events)
