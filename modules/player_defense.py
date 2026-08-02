"""Player-level defense analytics (defensive activity, duel involvement), shared
across any tab that shows a single player's defensive output -- Rice Player and
Opponent Player. Each caller passes its own filtered_events, a selected-player
accessor, and a unique id_prefix so output IDs don't collide."""
from shiny import ui, render
from . import plot_style as ps
from . import duel_stats

def _no_plot_data(player_id, df):
    return not player_id or df is None or df.empty


def _duel_splits(df_filtered):
    """Ground/aerial duels won vs lost, drawn from the same event population
    for both the scatter plot and the summary card -- guarantees won <= total
    by construction, unlike dividing against the separately-aggregated
    offensive_duels_count/defensive_duels_count (which cover more than just
    ground duels and can produce nonsensical >100% rates)."""
    ground_duels, aerial_duels = duel_stats.get_ground_and_aerial_duels(df_filtered)

    ground_won = ground_duels[
        (ground_duels["ground_duel_kept_possession"] == True) |
        (ground_duels["ground_duel_recovered_possession"] == True)
    ]
    ground_lost = ground_duels[
        (ground_duels["ground_duel_kept_possession"] != True) &
        (ground_duels["ground_duel_recovered_possession"] != True)
    ]
    aerial_won = aerial_duels[aerial_duels["aerial_duel_first_touch"] == True]
    aerial_lost = aerial_duels[aerial_duels["aerial_duel_first_touch"] != True]

    return ground_duels, ground_won, ground_lost, aerial_duels, aerial_won, aerial_lost


def defensive_events_ui(id_prefix):
    return ui.card(
        ui.card_header("Defensive Activity Heatmap"),
        ui.output_plot(f"{id_prefix}_player_defensive_events_plot"),
    )

def duel_scatter_ui(id_prefix):
    return ui.card(
        ui.card_header("Duels Won / Lost"),
        ui.output_plot(f"{id_prefix}_player_duel_scatter_plot"),
    )

def duel_summary_ui(id_prefix):
    return ui.card(
        ui.card_header("Duel Summary"),
        ui.output_ui(f"{id_prefix}_player_duel_summary"),
    )

def defense_ui(id_prefix):
    return ui.div(
        ui.div("Defensive Overview", class_="section-heading"),
        ui.layout_column_wrap(
            defensive_events_ui(id_prefix),
            duel_scatter_ui(id_prefix),
            width="480px",
        ),
        ui.layout_column_wrap(
            duel_summary_ui(id_prefix),
            width="480px",
        ),
    )


def defense_server(input, output, session, filtered_events, selected_player_id, id_prefix):
    @output(id=f"{id_prefix}_player_defensive_events_plot")
    @render.plot
    def defensive_events_plot():
        player_id = selected_player_id()
        df = filtered_events()
        if _no_plot_data(player_id, df):
            return None
        df_filtered = df[df["wy_player_id"] == int(float(player_id))]
        if df_filtered.empty:
            return None

        defensive_df = df_filtered[
            df_filtered["type_primary"].str.contains("interception", case=False, na=False) |
            df_filtered["type_secondary"].str.contains("defensive_duel|sliding_tackle|shot_block", case=False, na=False)
        ]

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

    @output(id=f"{id_prefix}_player_duel_scatter_plot")
    @render.plot
    def duel_scatter_plot():
        player_id = selected_player_id()
        df = filtered_events()
        if _no_plot_data(player_id, df):
            return None
        df_filtered = df[df["wy_player_id"] == int(float(player_id))]
        if df_filtered.empty:
            return None

        _, ground_won, ground_lost, _, aerial_won, aerial_lost = _duel_splits(df_filtered)

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        any_data = False
        for subset, color, marker, label in [
            (ground_won, ps.ON_TARGET_COLOR, "o", "Ground Won"),
            (ground_lost, ps.OFF_TARGET_COLOR, "o", "Ground Lost"),
            (aerial_won, ps.ON_TARGET_COLOR, "^", "Aerial Won"),
            (aerial_lost, ps.OFF_TARGET_COLOR, "^", "Aerial Lost"),
        ]:
            if not subset.empty:
                any_data = True
                pitch.scatter(
                    subset["location_x"], subset["location_y"],
                    ax=ax, color=color, marker=marker,
                    edgecolors="black", s=100, label=label,
                )

        if any_data:
            ax.legend(loc="upper right", fontsize=ps.LEGEND_FONTSIZE)
        return fig

    @output(id=f"{id_prefix}_player_duel_summary")
    @render.ui
    def duel_summary():
        player_id = selected_player_id()
        df = filtered_events()
        if _no_plot_data(player_id, df):
            return ui.div("No duel data for this selection.", class_="empty-state")
        df_filtered = df[df["wy_player_id"] == int(float(player_id))]
        if df_filtered.empty:
            return ui.div("No duel data for this selection.", class_="empty-state")

        ground_duels, ground_won, _, aerial_duels, aerial_won, _ = _duel_splits(df_filtered)

        def pct(n, d):
            return f"{(n / d * 100):.0f}%" if d else "--"

        return ui.layout_column_wrap(
            ui.value_box(
                "Ground Duels", len(ground_duels),
                f"Won {pct(len(ground_won), len(ground_duels))}",
            ),
            ui.value_box(
                "Aerial Duels", len(aerial_duels),
                f"Won {pct(len(aerial_won), len(aerial_duels))}",
            ),
            width="280px",
        )
