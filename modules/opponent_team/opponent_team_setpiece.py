from shiny import ui, render
import matplotlib.pyplot as plt
import pandas as pd
from .. import plot_style as ps


def free_kicks_ui():
    return ui.card(
        ui.card_header("Free Kick Trajectories"),
        ui.output_plot("set_pieces_plot"),
    )


def corner_kick_endpoints_ui():
    return ui.card(
        ui.card_header("Corner Kick Outcomes"),
        ui.output_plot("corner_kick_endpoints_plot"),
    )


def set_pieces_ui():
    return ui.div(
        ui.div("Set-Piece Delivery", class_="section-heading"),
        ui.layout_column_wrap(
            free_kicks_ui(),
            corner_kick_endpoints_ui(),
            width="480px",
        ),
    )

def set_pieces_server(input, output, session, filtered_events):
    # Your server logic here
    
    @render.plot
    def set_pieces_plot():
        df = filtered_events()

        if df is None or df.empty:
            return None

        # Filter for free kicks and make a copy to avoid warnings
        set_piece_df = df[df["type_primary"] == "free_kick"].copy()
        
        # Drop rows that don't have an end location so the arrows don't crash
        set_piece_df = set_piece_df.dropna(subset=['location_x', 'location_y', 'pass_end_location_x', 'pass_end_location_y'])

        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if not set_piece_df.empty:
            # Draw the arrows to show the trajectory
            pitch.arrows(
                set_piece_df["location_x"],
                set_piece_df["location_y"],
                set_piece_df["pass_end_location_x"],
                set_piece_df["pass_end_location_y"],
                ax=ax,
                width=2,
                headwidth=5,
                headlength=6,
                color=ps.RICE_BLUE,
                alpha=0.5, # Slightly transparent so overlapping arrows are visible
                zorder=1
            )

            # Keep the scatter plot to emphasize the start location
            pitch.scatter(
                set_piece_df["location_x"],
                set_piece_df["location_y"],
                ax=ax,
                color=ps.RICE_BLUE,
                edgecolors="black",
                zorder=2,
                label="Free Kicks"
            )

            ax.legend(loc='upper right', fontsize=ps.LEGEND_FONTSIZE)

        return fig
        
    # FIXED: Un-indented to align with set_pieces_plot
    @render.plot
    def corner_kick_endpoints_plot():
        df = filtered_events()

        if df is None or df.empty:
            return None
            
        df_copy = df.copy()
        
        # 1. Isolate Corner Kicks using the correct primary type
        corners = df_copy[df_copy['type_primary'] == 'corner']
        
        # 2. Draw Pitch with the shared house style
        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if not corners.empty:
            # Drop rows where end location is missing
            corners = corners.dropna(subset=['pass_end_location_x', 'pass_end_location_y'])
            
            # 3. Find possession IDs that ultimately led to a goal
            goals = df_copy[(df_copy['type_primary'] == 'shot') & (df_copy['shot_is_goal'] == True)]
            possession_goals = goals['possession_id'].unique()
            
            # 4. Categorize the corners based on outcomes
            goal_corners = corners[corners['possession_id'].isin(possession_goals)]
            
            # Filter out the goal corners so we don't double plot them
            non_goal_corners = corners[~corners['possession_id'].isin(possession_goals)]
            
            # Accurate pass = Attacking team won the ball
            attacking_won = non_goal_corners[non_goal_corners['pass_accurate'] == True]
            # Inaccurate pass = Defending team cleared/intercepted it
            defending_won = non_goal_corners[non_goal_corners['pass_accurate'] == False]
            
            # Plot locations where the DEFENDING team got first contact
            if not defending_won.empty:
                pitch.scatter(
                    defending_won['pass_end_location_x'],
                    defending_won['pass_end_location_y'],
                    ax=ax,
                    color=ps.OFF_TARGET_COLOR,
                    edgecolors='black',
                    s=80,
                    zorder=3,
                    marker='o',
                    label='Defending Team Intercepted'
                )

            # Plot locations where the ATTACKING team got first contact
            if not attacking_won.empty:
                pitch.scatter(
                    attacking_won['pass_end_location_x'],
                    attacking_won['pass_end_location_y'],
                    ax=ax,
                    color=ps.ON_TARGET_COLOR,
                    edgecolors='black',
                    s=80,
                    zorder=4,
                    marker='o',
                    label='Attacking Team Intercepted'
                )

            # Plot locations that led to a GOAL
            if not goal_corners.empty:
                pitch.scatter(
                    goal_corners['pass_end_location_x'],
                    goal_corners['pass_end_location_y'],
                    ax=ax,
                    color=ps.GOAL_COLOR,
                    edgecolors='black',
                    s=180, # Make the goal-creating corners larger
                    zorder=5,
                    marker='*', # Use a star to easily distinguish
                    label='Corner Led to Goal'
                )

            # Add legend
            ax.legend(loc='lower left', frameon=False, labelcolor='black', fontsize=ps.LEGEND_FONTSIZE)

        return fig