from shiny import ui, render
from .. import plot_style as ps

def _no_plot_data(player_id, df):
    return not player_id or df is None or df.empty

def loss_scatter_ui():
    return ui.card(
        ui.card_header("End Locations of Failed Passes"),
        ui.output_plot("loss_scatter_plot"),
    )

def pass_map_ui():
    return ui.card(
        ui.card_header("Passes"),
        ui.output_plot("pass_map_plot"),
    )

def pass_reception_ui():
    return ui.card(
        ui.card_header("Locations of Passes Received"),
        ui.output_plot("pass_reception_plot"),
    )

def attack_ui():
    return ui.div(
        ui.div("Passing", class_="section-heading"),
        ui.layout_column_wrap(
            loss_scatter_ui(),
            pass_map_ui(),
            pass_reception_ui(),
            width="480px",
        ),
    )

def attack_server(input, output, session, filtered_events):
    @render.plot
    def loss_scatter_plot():
        player_id = input.selected_rice_player()
        df = filtered_events()
        if _no_plot_data(player_id, df):
            return None
        df_filtered = df[df['wy_player_id'] == int(float(player_id))]
        if df_filtered.empty:
            return None

        loss_df = df_filtered[
            (df_filtered["type_primary"] == "pass") &
            (df_filtered["type_secondary"].str.contains("loss", case=False, na=False))
        ]

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if not loss_df.empty:
            pitch.scatter(
                loss_df["pass_end_location_x"],
                loss_df["pass_end_location_y"],
                ax=ax,
                color=ps.OFF_TARGET_COLOR,
                edgecolors="black",
                label="Pass Losses"
            )
            ax.legend(loc='upper right', fontsize=ps.LEGEND_FONTSIZE)

        return fig

    @render.plot
    def pass_map_plot():
        player_id = input.selected_rice_player()
        df = filtered_events()
        if _no_plot_data(player_id, df):
            return None
        df_filtered = df[df['wy_player_id'] == int(float(player_id))]
        if df_filtered.empty:
            return None
        #all passes made by the selcted player
        key_pass_df = df_filtered[
            (df_filtered["type_primary"] == "pass")
            # &
            # (df["type_secondary"].str.contains("key", case=False, na=False))
        ]
        #creating the pitch
        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))
        #creating the arrows
        if not key_pass_df.empty:
            pitch.arrows(
                key_pass_df["location_x"],
                key_pass_df["location_y"],
                key_pass_df["pass_end_location_x"],
                key_pass_df["pass_end_location_y"],
                ax=ax,
                width=2,
                headwidth=3,
                headlength=5,
                color=ps.RICE_BLUE,
                label="Key Passes"
            )
            ax.legend(loc='upper right', fontsize=ps.LEGEND_FONTSIZE)
        return fig

    @render.plot
    def pass_reception_plot():
        player_id = input.selected_rice_player()
        df = filtered_events()
        if _no_plot_data(player_id, df):
            return None
        df_filtered = df[df['pass_recipient_id'] == int(float(player_id))]
        if df_filtered.empty:
            return None
        pass_received_df = df_filtered[df_filtered["type_primary"] == "pass"]

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))
        if not pass_received_df.empty:
            pitch.scatter(
                pass_received_df["pass_end_location_x"],
                pass_received_df["pass_end_location_y"],
                ax=ax,
                color=ps.OFF_TARGET_COLOR,
                edgecolors="black",
                label="Pass received"
            )
            ax.legend(loc='upper right', fontsize=ps.LEGEND_FONTSIZE)

        return fig
