from django.apps import AppConfig


class PyLadiesVancouverConfig(AppConfig):
    """PyLadies Vancouver's own app, loaded ahead of the core through
    ``EXTRA_APPS``: its static files (the logo and the share image) today,
    its own pages, models and commands when PyLadies Vancouver needs them."""

    name = "flashlights_vancouver"
    verbose_name = "PyLadies Vancouver"
