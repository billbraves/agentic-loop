import re


def test_package_imports_with_version():
    import agentic_loop

    assert re.fullmatch(r"\d+\.\d+\.\d+", agentic_loop.__version__), (
        f"__version__ must be semver-formatted, got {agentic_loop.__version__!r}"
    )
