import os
import time
import unittest
import warnings

try:
    import peewee
except ImportError:
    peewee = None

from huey import signals as S
from huey.tests.base import BaseTestCase

if peewee is not None:
    from huey.contrib import stats as stats_mod
    from huey.contrib.stats import HueyEvent
    from huey.contrib.stats import HueyInflight
    from huey.contrib.stats import HueyStats


@unittest.skipIf(peewee is None, 'requires peewee')
class StatsTestCase(BaseTestCase):
    db_file = '/tmp/huey-stats.db'

    def setUp(self):
        super(StatsTestCase, self).setUp()
        if os.path.exists(self.db_file):
            os.unlink(self.db_file)
        self.db = peewee.SqliteDatabase(self.db_file)
        stats_mod.database.initialize(self.db)
        self.stats = None

        @self.huey.task()
        def task_a():
            pass
        self.task_a = task_a

    def tearDown(self):
        if self.stats is not None:
            self.stats.close()
        if os.path.exists(self.db_file):
            os.unlink(self.db_file)
        super(StatsTestCase, self).tearDown()

    def get_stats(self, **kwargs):
        self.stats = HueyStats(self.huey, self.db, **kwargs)
        self.stats.connect()
        return self.stats


class TestStatsInit(StatsTestCase):
    def test_init_closes_own_connection(self):
        HueyStats(self.huey, self.db)
        self.assertTrue(self.db.is_closed())

    def test_init_preserves_open_connection(self):
        self.db.connect()
        HueyStats(self.huey, self.db)
        self.assertFalse(self.db.is_closed())
        self.db.close()


class TestStatsFlush(StatsTestCase):
    def test_inflight_collapse(self):
        stats = self.get_stats(flush_interval=60)
        t1, t2 = self.task_a.s(), self.task_a.s()
        self.huey._emit(S.SIGNAL_EXECUTING, t1)
        self.huey._emit(S.SIGNAL_EXECUTING, t2)
        self.huey._emit(S.SIGNAL_COMPLETE, t1)
        stats._flush()

        # All three events recorded, only the still-running task inflight.
        self.assertEqual(HueyEvent.select().count(), 3)
        self.assertEqual([r.task_id for r in HueyInflight.select()],
                         [str(t2.id)])


@unittest.skipIf(not hasattr(os, 'register_at_fork'), 'requires fork()')
class TestStatsFork(StatsTestCase):
    def fork_child(self, child_fn):
        with warnings.catch_warnings():
            # Forking with the writer thread running is the scenario under
            # test. Silence the 3.12+ fork-in-threaded-process warning.
            warnings.simplefilter('ignore', DeprecationWarning)
            pid = os.fork()
        if pid == 0:
            # The child must exit here. Returning would resume the test
            # runner inside the fork. Exit code 3 means child_fn raised.
            try:
                code = child_fn()
            except BaseException:
                code = 3
            os._exit(code)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFEXITED(status))
        return os.WEXITSTATUS(status)

    def test_writer_restarted_in_child(self):
        stats = self.get_stats(flush_interval=0.05)
        parent_writer = stats._writer
        task = self.task_a.s()

        def child():
            if stats._writer is parent_writer or not stats._writer.is_alive():
                return 1
            self.huey._emit(S.SIGNAL_EXECUTING, task)
            self.huey._emit(S.SIGNAL_COMPLETE, task)
            deadline = time.time() + 5
            while time.time() < deadline:
                query = HueyEvent.select().where(
                    HueyEvent.signal == S.SIGNAL_COMPLETE)
                if query.count() == 1:
                    return 0
                time.sleep(0.02)
            return 2

        self.assertEqual(self.fork_child(child), 0)
        self.assertTrue(parent_writer.is_alive())
        self.assertEqual(
            sorted(e.signal for e in HueyEvent.select()),
            [S.SIGNAL_COMPLETE, S.SIGNAL_EXECUTING])

    def test_buffered_rows_written_by_parent_alone(self):
        stats = self.get_stats(flush_interval=60)
        self.huey._emit(S.SIGNAL_ENQUEUED, self.task_a.s())
        self.assertEqual(len(stats._buf), 1)

        def child():
            if stats._buf:
                return 1
            return 0

        self.assertEqual(self.fork_child(child), 0)

        stats._flush()
        query = HueyEvent.select().where(HueyEvent.signal == S.SIGNAL_ENQUEUED)
        self.assertEqual(query.count(), 1)

    def test_shutdown_hook_flushes_in_child(self):
        # flush_interval=60 so only the shutdown hook can have written it.
        self.get_stats(flush_interval=60)

        def child():
            self.huey._emit(S.SIGNAL_EXECUTING, self.task_a.s())
            for hook in self.huey._shutdown.values():
                hook()
            return 0 if HueyEvent.select().count() == 1 else 1

        self.assertEqual(self.fork_child(child), 0)

    def test_closed_recorder_not_revived(self):
        stats = self.get_stats()
        stats.close()
        parent_writer = stats._writer
        def child():
            if stats._writer is parent_writer:
                return 0
            return 1

        self.assertEqual(self.fork_child(child), 0)
