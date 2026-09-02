from django.db import models


# Nothing here is ever queried. The stats tables are owned, written and read
# by peewee, and both admin pages render from it. These exist only to give the
# admin a model to hang its index entry and URLs on.
class HueyEvent(models.Model):
    ts = models.FloatField(db_index=True)
    queue = models.CharField(max_length=255, db_index=True)
    task_id = models.CharField(max_length=255)
    task = models.CharField(max_length=255, db_index=True)
    signal = models.CharField(max_length=64)
    duration = models.FloatField(null=True)
    error = models.TextField(null=True)
    args = models.TextField(null=True)

    class Meta:
        managed = False
        db_table = 'huey_event'
        verbose_name = 'event'

    def __str__(self):
        return '%s %s' % (self.task, self.signal)


class HueyDashboard(HueyEvent):
    class Meta:
        proxy = True
        verbose_name = 'dashboard'
        verbose_name_plural = 'dashboard'
