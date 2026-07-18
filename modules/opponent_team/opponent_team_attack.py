from shiny import ui, render
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mplsoccer import Radar, FontManager, grid
from .. import plot_style as ps


def goal_scatter_ui():
    return ui.card(
        ui.card_header("Goals Scored"),
        ui.output_plot("goal_scatter_plot"),
    )


def radar_ui():
    return ui.card(
        ui.card_header("Team Stat Analysis"),
        ui.output_plot("radar_plot"),
    )


def key_passes_ui():
    return ui.card(
        ui.card_header("Key Passes — Shot Within 10s"),
        ui.output_plot("key_passes_plot_opp"),
    )


def crosses_ui():
    return ui.card(
        ui.card_header("Cross Map"),
        ui.output_plot("crosses_plot"),
    )


def momentum_ui():
    return ui.card(
        ui.card_header("Match Momentum"),
        ui.output_plot("momentum_plot"),
    )


def attack_ui():
    """Provides the UI container for the attacking charts."""
    return ui.div(
        ui.div("Attacking Overview", class_="section-heading"),
        ui.layout_column_wrap(
            goal_scatter_ui(),
            radar_ui(),
            momentum_ui(),
            width="480px",
        ),
        ui.div("Passing & Delivery", class_="section-heading"),
        ui.layout_column_wrap(
            key_passes_ui(),
            crosses_ui(),
            width="480px",
        ),
    )
def attack_server(input, output, session, filtered_events, events_df, team_names_dict):
    @render.plot
    def goal_scatter_plot():
        df = filtered_events()

        if df is None or df.empty:
            return None

        goal_df = df[(df["type_primary"] == "shot") & (df["shot_is_goal"] == True)]
        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if not goal_df.empty:
            pitch.scatter(
                goal_df["location_x"],
                goal_df["location_y"],
                ax=ax,
                color=ps.GOAL_COLOR,
                edgecolors="black",
                label="Goals"
            )
            ax.legend(loc='upper right', fontsize=ps.LEGEND_FONTSIZE)
        return fig
    @render.plot
    def radar_plot():
        df = filtered_events()

        if df is None or df.empty:
            return None

        params = ['Goals', "Assists", 'Shots', 'Shots on Target', 'Passes', 'Fouls']
        team_name = input.selected_opp_team()
        
        values = [
            df[df["type_primary"] == "shot"]["shot_is_goal"].sum(),
            df[(df["type_primary"] == "pass") & (df["type_secondary"].str.contains("shot_assist", na=False))].shape[0],
            df[df["type_primary"] == "shot"].shape[0],
            df[(df["type_primary"] == "shot") & (df["shot_on_target"] == True)].shape[0],
            df[df["type_primary"] == "pass"].shape[0],
            df[df["type_secondary"] == "[foul]"].shape[0]
        ]

        max_values = [5, 5, 25, 10, 800, 25] 
        lower_bounds = [0] * len(params)

        # Initialize radar with the true min and max boundaries
        radar = Radar(params, lower_bounds, max_values)

        fig, ax = radar.setup_axis(facecolor=ps.CHART_FACECOLOR)
        fig.subplots_adjust(top=0.75)
        ax.set_position([0.1, 0.05, 0.8, 0.75])

        rings_inner = radar.draw_circles(ax=ax, facecolor=ps.RICE_LIGHT_GRAY, edgecolor=ps.RICE_GRAY)

        # Draw the radar using the raw values
        radar_output = radar.draw_radar(values, ax=ax,
                                        kwargs_radar={'facecolor': ps.RICE_BLUE, 'alpha': 0.5, 'edgecolor': ps.RICE_BLUE, 'lw': 2},
                                        kwargs_rings={'facecolor': ps.RICE_LIGHT_GRAY})

        radar_poly, rings_outer, vertices = radar_output

        # Draw labels
        range_labels = radar.draw_range_labels(ax=ax, fontsize=15, zorder=2.5)
        param_labels = radar.draw_param_labels(ax=ax, fontsize=15)

        lines = radar.spoke(ax=ax, color=ps.RICE_GRAY, linestyle='--', zorder=2)
        
        return fig
    @render.plot
    def key_passes_plot_opp():
        df = filtered_events()

        if df is None or df.empty:
            return None
            
        # Create a copy so we don't modify the reactive dataframe directly
        df_copy = df.copy()
        
        # Ensure video_timestamp is numeric for our time window calculations
        df_copy['video_timestamp'] = pd.to_numeric(df_copy['video_timestamp'], errors='coerce')
        
        # 1. Isolate shots and accurate passes entirely before the loop
        shots = df_copy[df_copy['type_primary'] == 'shot']
        accurate_passes = df_copy[(df_copy['type_primary'] == 'pass') & (df_copy['pass_accurate'] == True)]
        
        # 2. Pre-group passes by match, period, and team for instant O(1) lookups
        grouped_passes = dict(tuple(accurate_passes.groupby(['wy_match_id', 'period', 'wy_team_id'])))
        
        key_passes = []

        # Find all passes within 10 seconds before a shot by the same team
        for idx, shot in shots.iterrows():
            group_key = (shot['wy_match_id'], shot['period'], shot['wy_team_id'])
            
            # Check if there are any accurate passes for this specific match/period/team
            if group_key in grouped_passes:
                match_passes = grouped_passes[group_key]
                shot_time = shot['video_timestamp']
                
                # Filter ONLY by time on this tiny subset of passes
                mask = (
                    (match_passes['video_timestamp'] >= shot_time - 10) & 
                    (match_passes['video_timestamp'] < shot_time)
                )
                
                recent_passes = match_passes[mask]
                
                if not recent_passes.empty:
                    key_passes.append(recent_passes)

        if key_passes:
            key_passes_df = pd.concat(key_passes).drop_duplicates(subset=['wy_event_id'])
            key_passes_df = key_passes_df.dropna(subset=['location_x', 'location_y', 'pass_end_location_x', 'pass_end_location_y'])
        else:
            key_passes_df = pd.DataFrame(columns=df_copy.columns)

        # Draw Pitch with the shared house style
        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if not key_passes_df.empty:
            # Plot arrows for the passes with much smaller pointers and slightly thinner lines
            pitch.arrows(key_passes_df['location_x'], key_passes_df['location_y'],
                         key_passes_df['pass_end_location_x'], key_passes_df['pass_end_location_y'],
                         width=1.5, headwidth=3, headlength=4, color=ps.RICE_BLUE, ax=ax, alpha=0.7,
                         label='Passes within 10s of Shot')

            # Add a scatter plot for the start of the pass
            pitch.scatter(key_passes_df['location_x'], key_passes_df['location_y'],
                          color=ps.RICE_BLUE, s=40, ax=ax, zorder=2)

            # Label color set to black for the white background
            ax.legend(loc='lower left', frameon=False, labelcolor='black', fontsize=ps.LEGEND_FONTSIZE)

        return fig
    @render.plot
    def crosses_plot():
        df = filtered_events()

        if df is None or df.empty:
            return None
            
        df_copy = df.copy()
        
        # 1. Isolate Crosses
        crosses = df_copy[df_copy['type_secondary'].astype(str).str.contains('cross', case=False, na=False)]
        
        # Draw Pitch with the shared house style
        pitch, fig, ax = ps.new_pitch(figsize=(10, 7))

        if not crosses.empty:
            # --- CLEANING STEP: Remove missing or "zeroed out" data ---
            # 1. Drop NaNs
            crosses = crosses.dropna(subset=['location_x', 'location_y', 'pass_end_location_x', 'pass_end_location_y'])
            
            # 2. Filter out crosses ending at exactly (0,0) which is usually a data error
            crosses = crosses[~((crosses['pass_end_location_x'] == 0) & (crosses['pass_end_location_y'] == 0))]
            # ---------------------------------------------------------
            
            # 2. Find possessions that resulted in a goal
            goals = df_copy[(df_copy['type_primary'] == 'shot') & (df_copy['shot_is_goal'] == True)]
            goal_possessions = goals['possession_id'].unique()
            
            # 3. Categorize crosses
            goal_crosses = crosses[crosses['possession_id'].isin(goal_possessions)]
            non_goal_crosses = crosses[~crosses['possession_id'].isin(goal_possessions)]
            
            accurate_crosses = non_goal_crosses[non_goal_crosses['pass_accurate'] == True]
            inaccurate_crosses = non_goal_crosses[non_goal_crosses['pass_accurate'] == False]

            # Plot Inaccurate Crosses
            if not inaccurate_crosses.empty:
                pitch.arrows(inaccurate_crosses['location_x'], inaccurate_crosses['location_y'],
                            inaccurate_crosses['pass_end_location_x'], inaccurate_crosses['pass_end_location_y'],
                            width=1.5, headwidth=3, headlength=4, color=ps.OFF_TARGET_COLOR, ax=ax, alpha=0.4,
                            label='Inaccurate Cross')

                pitch.scatter(inaccurate_crosses['location_x'], inaccurate_crosses['location_y'],
                            color=ps.OFF_TARGET_COLOR, s=20, ax=ax, zorder=2)

            # Plot Accurate Crosses
            if not accurate_crosses.empty:
                pitch.arrows(accurate_crosses['location_x'], accurate_crosses['location_y'],
                            accurate_crosses['pass_end_location_x'], accurate_crosses['pass_end_location_y'],
                            width=1.5, headwidth=3, headlength=4, color=ps.ON_TARGET_COLOR, ax=ax, alpha=0.6,
                            label='Accurate Cross')

                pitch.scatter(accurate_crosses['location_x'], accurate_crosses['location_y'],
                            color=ps.ON_TARGET_COLOR, edgecolors='black', linewidths=0.6, s=30, ax=ax, zorder=3)

            # Plot Goal-Creating Crosses (Star Markers)
            if not goal_crosses.empty:
                pitch.arrows(goal_crosses['location_x'], goal_crosses['location_y'],
                            goal_crosses['pass_end_location_x'], goal_crosses['pass_end_location_y'],
                            width=2.5, headwidth=5, headlength=6, color=ps.GOAL_COLOR, ax=ax, alpha=1.0,
                            label='Cross Led to Goal')

                pitch.scatter(goal_crosses['location_x'], goal_crosses['location_y'],
                            color=ps.GOAL_COLOR, edgecolors='black', s=80, marker='*', ax=ax, zorder=4)

            ax.legend(loc='lower left', frameon=False, labelcolor='black', fontsize=ps.LEGEND_FONTSIZE)

        return fig
    @render.plot
    def momentum_plot():
        df = filtered_events()

        if df is None or df.empty:
            return None
            
        # 1. Get the match_id from the filtered events
        match_id = df['wy_match_id'].iloc[0]
        
        # 2. To plot BOTH teams, we need the full match data, not just the filtered team's data.
        try:
            match_events = events_df[events_df['wy_match_id'] == match_id].copy()
        except NameError:
            # Fallback if events_df isn't defined globally, just use df so the app doesn't crash
            match_events = df.copy() 
        
        # Ensure timestamp is numeric
        match_events['video_timestamp'] = pd.to_numeric(match_events['video_timestamp'], errors='coerce')
        
        # Convert seconds to match minutes
        match_events['minute'] = (match_events['video_timestamp'] // 60).astype(int)
        
        # Filter down to events that show "Attacking Intent" (shots and passes)
        attack_events = match_events[match_events['type_primary'].isin(['shot', 'pass'])].copy()
        
        if attack_events.empty:
            return None
            
        # 3. Use actual team names for the legend instead of wy_team_id
        # If your event data doesn't have a 'team_name' column, you can map it here.
        # Example: attack_events['team_name'] = attack_events['wy_team_id'].map({123: "Arsenal", 456: "Chelsea"})
        
        team_col = 'team_name' if 'team_name' in attack_events.columns else 'wy_team_id'
            
        # Group by minute and team to get volume of actions per minute
        momentum_data = attack_events.groupby(['minute', team_col]).size().reset_index(name='intensity')
        
        # Pivot so teams are columns and minutes are rows
        pivot_df = momentum_data.pivot(index='minute', columns=team_col, values='intensity').fillna(0)
        
        # Ensure the x-axis extends to at least 90 minutes
        max_min = min(90, pivot_df.index.max()) if not pivot_df.empty else 90
        max_min = max(90, max_min) 
        all_minutes = pd.Index(range(int(max_min) + 1), name='minute')
        pivot_df = pivot_df.reindex(all_minutes, fill_value=0)
        
        teams = list(pivot_df.columns)

        fig, ax = ps.new_chart(figsize=(10, 4))

        # If the dataframe contains data for both teams
        if len(teams) >= 2:
            team1, team2 = teams[0], teams[1]
            
            # Calculate momentum (Difference in event volume)
            momentum = pivot_df[team1] - pivot_df[team2]
            
            # Smooth using a rolling average
            smoothed = momentum.rolling(window=5, min_periods=1).mean()
            
            # Note: casting team names to string to ensure they display properly in the legend
            ax.fill_between(smoothed.index, smoothed.values, 0, where=(smoothed.values > 0),
                            color=ps.ACCENT_COLORS[0], alpha=0.8, interpolate=True, label=str(team1))
            ax.fill_between(smoothed.index, smoothed.values, 0, where=(smoothed.values < 0),
                            color=ps.ACCENT_COLORS[1], alpha=0.8, interpolate=True, label=str(team2))

        # Fallback if only one team is present
        elif len(teams) == 1:
            team1 = teams[0]
            momentum = pivot_df[team1]
            smoothed = momentum.rolling(window=5, min_periods=1).mean()

            ax.fill_between(smoothed.index, smoothed.values, 0, where=(smoothed.values > 0),
                            color=ps.ACCENT_COLORS[0], alpha=0.8, interpolate=True, label=str(team1))
                            
        ax.axhline(0, color='black', linewidth=1.5)
        ax.set_xlim(0, max_min)
        ax.set_xticks(np.arange(0, max_min + 1, 15))
        ax.set_xlabel("Match Minute", fontsize=ps.AXIS_LABEL_FONTSIZE, fontweight='bold')
        ax.set_ylabel("Attacking Pressure", fontsize=ps.AXIS_LABEL_FONTSIZE, fontweight='bold')

        # Clean up borders
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.grid(False)
        ax.get_yaxis().set_ticks([])

        # Display the legend cleanly
        ax.legend(loc='upper right', frameon=False, fontsize=ps.LEGEND_FONTSIZE)
        plt.tight_layout()

        return fig
  