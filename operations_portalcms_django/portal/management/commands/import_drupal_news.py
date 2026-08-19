"""Compatibility entry point for the canonical Drupal news importer.

``portal`` appears before ``infrastructure_news`` in ``INSTALLED_APPS``, so Django
resolves this command module first. Import the canonical command instead of keeping
two implementations that can drift.
"""

from infrastructure_news.management.commands.import_drupal_news import Command


__all__ = ["Command"]
