"""Shared visual constants so every chart in the dashboard reads as one system."""
import matplotlib
matplotlib.use("Agg")  # non-interactive backend; this app only ever renders to PNG bytes, never a GUI window
import matplotlib.pyplot as plt
from mplsoccer import Pitch, VerticalPitch

RICE_BLUE = "#00205B"
RICE_BLUE_LIGHT = "#0B3D91"
RICE_GRAY = "#8996A0"
RICE_LIGHT_GRAY = "#F4F5F7"

PITCH_COLOR = "#1E4A2E"
PITCH_LINE_COLOR = "#E8E8E8"

GOAL_COLOR = "#FFC72C"
ON_TARGET_COLOR = "#FFFFFF"
OFF_TARGET_COLOR = "#D64545"
OTHER_COLOR = "#9AA5B1"

CHART_FACECOLOR = "#FFFFFF"
CHART_GRID_COLOR = "#E3E6EA"

ACCENT_COLORS = ["#00205B", "#D64545", "#2E9E6B", "#FFC72C", "#5B7FDB"]

TITLE_FONTSIZE = 14
AXIS_LABEL_FONTSIZE = 11
LEGEND_FONTSIZE = 9


def new_pitch(vertical=False, half=False, figsize=(10, 7)):
    """Return (fig, ax) for a pitch drawn with the shared house style."""
    pitch_cls = VerticalPitch if vertical else Pitch
    pitch = pitch_cls(
        pitch_type="wyscout",
        pitch_color=PITCH_COLOR,
        line_color=PITCH_LINE_COLOR,
        half=half,
    )
    fig, ax = pitch.draw(figsize=figsize)
    fig.patch.set_facecolor(CHART_FACECOLOR)
    return pitch, fig, ax


def new_chart(figsize=(10, 5)):
    """Return (fig, ax) for a non-pitch chart (bar/line/etc.) with the shared house style."""
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_facecolor(CHART_FACECOLOR)
    fig.patch.set_facecolor(CHART_FACECOLOR)
    ax.grid(True, alpha=0.4, color=CHART_GRID_COLOR)
    ax.set_axisbelow(True)
    return fig, ax


def style_title(ax, title):
    ax.set_title(title, fontsize=TITLE_FONTSIZE, fontweight="bold", color=RICE_BLUE, pad=12)
