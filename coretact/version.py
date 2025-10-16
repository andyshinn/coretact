from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("coretact")
except PackageNotFoundError:
    # We don't know the version so I guess we'll say it's 0.0.0
    __version__ = "0.0.0"
