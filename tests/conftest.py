"""Root test configuration."""


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden", action="store_true",
        help="Regenerate golden trace files from current pipeline output",
    )
