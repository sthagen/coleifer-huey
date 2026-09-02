import logging
import os

from django.apps import AppConfig
from django.conf import settings

import peewee


logger = logging.getLogger('huey')


def stats_database():
    """
    Stats are recorded to huey's own sqlite database. Point
    HUEY_STATS['database'] at a peewee Database or db-url to store them
    elsewhere, e.g. the database Django uses.
    """
    options = getattr(settings, 'HUEY_STATS', None) or {}
    db = options.get('database')
    if isinstance(db, peewee.Database):
        return db
    elif isinstance(db, str):
        from playhouse.db_url import connect
        return connect(db)

    filename = options.get('filename') or 'huey-stats.db'
    base = getattr(settings, 'BASE_DIR', None)
    if base and not os.path.isabs(filename):
        filename = os.path.join(str(base), filename)
    # The consumer and every web process write to this file.
    return peewee.SqliteDatabase(filename, timeout=5, pragmas={
        'journal_mode': 'wal', 'synchronous': 1})


def stats_options():
    options = dict(getattr(settings, 'HUEY_STATS', None) or {})
    options.pop('database', None)
    options.pop('filename', None)
    return options


class HueyStatsConfig(AppConfig):
    name = 'huey.contrib.djhuey.stats'
    label = 'hueystats'
    verbose_name = 'Huey'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        from huey.contrib.djhuey import HUEY
        from huey.contrib.stats import enable_stats
        try:
            enable_stats(HUEY, stats_database(), **stats_options())
        except Exception:
            logger.exception('huey stats recorder failed to start.')
