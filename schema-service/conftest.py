"""Root pytest configuration."""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: marks tests as requiring live services (deselect with '-m not live')"
    )


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.live tests unless -m live is explicitly passed."""
    if config.getoption("-m", default="") != "live":
        skip_live = pytest.mark.skip(reason="Requires live services. Run with -m live to enable.")
        for item in items:
            if item.get_closest_marker("live"):
                item.add_marker(skip_live)
