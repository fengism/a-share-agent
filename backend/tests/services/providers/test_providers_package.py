import pytest

from app.services import providers


def test_lazy_provider_class_export_resolves_on_demand():
    """providers package should lazily expose provider classes by name."""
    cls = providers.ThsDataProvider
    twitter_cls = providers.TwitterDataProvider

    assert cls.__name__ == "ThsDataProvider"
    assert twitter_cls.__name__ == "TwitterDataProvider"


def test_lazy_provider_class_export_raises_for_unknown_name():
    """providers package should raise AttributeError for unknown exports."""
    with pytest.raises(AttributeError):
        _ = providers.UnknownProvider


def test_get_provider_returns_singleton_instance():
    """providers.get_provider should resolve singleton exports by short name."""
    instance = providers.get_provider("ths")

    assert instance.name == "ths"
