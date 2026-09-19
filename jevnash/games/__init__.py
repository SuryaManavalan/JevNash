from .grid3 import Grid3Env
from .piles import PilesEnv


def _browser(name):
    def make(**kw):
        from . import browser  # imported lazily: Playwright is only needed for browser tasks
        return getattr(browser, name)(**kw)
    return make


# Keys are opaque ids: they name run directories and are never shown to a model.
# Ordered from confined games to open-web tasks.
ENVS = {
    "env_a": Grid3Env,
    "env_b": PilesEnv,
    "web_form": _browser("OrderFormEnv"),
    "web_canvas": _browser("CanvasGameEnv"),  # pixel-only board, read via LlamaParse
    "web_race": _browser("WikiRaceEnv"),
    "web_open": _browser("OpenWebEnv"),  # any site: --task "..." --url ... [--inputs a,b]
}
