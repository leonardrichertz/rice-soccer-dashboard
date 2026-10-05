import os
from pathlib import Path

from dotenv import load_dotenv
from shiny import App, ui
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Mount

import modules.rice_team.rice_team_main as rice_team
import modules.rice_player.rice_player_main as rice_player
import modules.opponent_team.opponent_team_main as opponent_team
import modules.opponent_player.opponent_player_main as opponent_player
import modules.comparison_tool.comparison_tool_main as comparison_tool
from modules.auth.saml_routes import AuthGateMiddleware, routes as saml_routes

load_dotenv()

navbar_title = ui.TagList(
    ui.tags.span("RICE OWLS", class_="navbar-title-main"),
    ui.tags.span("Soccer Analytics", class_="navbar-title-sub"),
)

app_ui = ui.page_fluid(
    ui.head_content(
        ui.tags.link(rel="icon", type="image/x-icon", href="favicon.ico"),
    ),
    ui.include_css(Path(__file__).parent / "www" / "styles.css"),
    ui.page_navbar(
        rice_team.ui_content(),
        rice_player.ui_content(),
        opponent_team.ui_content(),
        opponent_player.ui_content(),
        comparison_tool.ui_content(),
        title=navbar_title,
        id="main_navbar",
        window_title="Rice Owls Soccer Analytics",
    )
)

def server(input, output, session):
    rice_team.server_logic(input, output, session)
    rice_player.server_logic(input, output, session)
    opponent_team.server_logic(input, output, session)
    opponent_player.server_logic(input, output, session)
    comparison_tool.server_logic(input, output, session)

shiny_app = App(
    app_ui,
    server,
    static_assets={"/": Path(__file__).parent / "www"},
)

# Rice IAM is SAML2-only (no OAuth), so access to the whole dashboard -- the
# page load and the websocket Shiny uses for reactivity -- is gated behind a
# SAML2 session via AuthGateMiddleware. See modules/auth/saml_routes.py.
app = Starlette(
    routes=[
        *saml_routes,
        Mount("/", app=shiny_app),
    ],
    middleware=[
        Middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET_KEY"]),
        Middleware(AuthGateMiddleware),
    ],
)