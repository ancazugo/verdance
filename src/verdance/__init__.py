"""
verdance — 3-30-300 urban greening metrics, powered by Apache Sedona.

Public API:
    verdance.load_config(path) -> VerdanceConfig
    verdance.run(config, process, **options)   # mirrors the `verdance run` CLI

These are imported lazily so `import verdance` (e.g. to read `__version__`)
does not pull in Spark and the rest of the stack.
"""

__version__ = "0.3.0"

__all__ = ["__version__", "run", "load_config", "VerdanceConfig"]


def __getattr__(name: str):
    if name == "run":
        from .api import run

        return run
    if name == "load_config":
        from .config.loader import load_config

        return load_config
    if name == "VerdanceConfig":
        from .config.schema import VerdanceConfig

        return VerdanceConfig
    raise AttributeError(f"module 'verdance' has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
