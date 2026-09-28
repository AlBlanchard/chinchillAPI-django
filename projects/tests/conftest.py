import pytest


@pytest.fixture(autouse=True)
def use_test_staticfiles_storage(settings):
    settings.STORAGES["staticfiles"] = {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    }