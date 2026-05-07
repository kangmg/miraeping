import miraeping
from miraeping._version import __version__


def test_package_version_is_exported() -> None:
    assert miraeping.__version__ == __version__
