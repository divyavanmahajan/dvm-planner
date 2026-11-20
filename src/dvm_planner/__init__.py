"""Extract Microsoft Planner plans and tasks through an Edge browser using CDP."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dvm-planner")
except PackageNotFoundError:  # running from a source checkout
    __version__ = "0.0.0"
