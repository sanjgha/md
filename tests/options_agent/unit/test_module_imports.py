def test_module_version():
    from src.options_agent import __version__

    assert __version__ == "0.1.0"


def test_submodules_importable():
    import src.options_agent.data  # noqa: F401
    import src.options_agent.signals  # noqa: F401
    import src.options_agent.chain  # noqa: F401
    import src.options_agent.targets  # noqa: F401
    import src.options_agent.candidates  # noqa: F401
