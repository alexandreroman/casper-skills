import os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from hooks.lib import progress

class TestActionsFor(unittest.TestCase):
    def test_empty_list_clears(self):
        self.assertEqual(progress.actions_for([]), [["progress", "clear"]])

    def test_all_completed_clears(self):
        tasks = [{"label": "a", "status": "completed"},
                 {"label": "b", "status": "completed"}]
        self.assertEqual(progress.actions_for(tasks), [["progress", "clear"]])

    def test_reports_current_position_and_label(self):
        tasks = [{"label": "a", "status": "completed"},
                 {"label": "b", "status": "in_progress"},
                 {"label": "c", "status": "pending"}]
        self.assertEqual(progress.actions_for(tasks), [[
            "progress", "set", "--total", "3", "--current", "2", "--label", "b"]])

    def test_no_labelled_in_progress_task_is_a_noop(self):
        tasks = [{"label": "", "status": "in_progress"},
                 {"label": "b", "status": "pending"}]
        self.assertIsNone(progress.actions_for(tasks))

    def test_no_in_progress_task_at_all_is_a_noop(self):
        tasks = [{"label": "a", "status": "pending"},
                 {"label": "b", "status": "pending"}]
        self.assertIsNone(progress.actions_for(tasks))

    def test_current_is_one_based_index_after_completed(self):
        tasks = [{"label": "a", "status": "completed"},
                 {"label": "b", "status": "completed"},
                 {"label": "c", "status": "in_progress"}]
        self.assertEqual(progress.actions_for(tasks)[0][5], "3")

class TestNothingInFlight(unittest.TestCase):
    def test_empty_list(self):
        self.assertTrue(progress.nothing_in_flight([]))

    def test_all_completed(self):
        self.assertTrue(progress.nothing_in_flight(
            [{"status": "completed"}, {"status": "completed"}]))

    def test_one_unfinished_is_enough(self):
        self.assertFalse(progress.nothing_in_flight(
            [{"status": "completed"}, {"status": "pending"}]))


class TestReconcile(unittest.TestCase):
    """The turn-end mapping: drop a bar that no longer describes live work."""

    def test_no_tasks_clears(self):
        # An agent with no task tool drove `casper progress set` by hand, so
        # there is no task state and nothing else would ever clear the bar.
        self.assertEqual(progress.reconcile([]), progress.CLEAR)

    def test_all_completed_clears(self):
        self.assertEqual(
            progress.reconcile([{"label": "a", "status": "completed"}]),
            progress.CLEAR)

    def test_in_flight_task_keeps_its_bar(self):
        self.assertEqual(
            progress.reconcile([{"label": "a", "status": "in_progress"}]), [])

    def test_agrees_with_actions_for_on_when_there_is_nothing_to_show(self):
        # The two mappings share one predicate precisely so they cannot
        # disagree about what "nothing to show" means.
        for tasks in ([],
                      [{"label": "a", "status": "completed"}],
                      [{"label": "a", "status": "in_progress"}],
                      [{"label": "", "status": "in_progress"}],
                      [{"label": "a", "status": "pending"}]):
            cleared = progress.actions_for(tasks) == progress.CLEAR
            self.assertEqual(cleared, progress.reconcile(tasks) == progress.CLEAR,
                             f"disagreement on {tasks}")


class TestState(unittest.TestCase):
    def test_missing_file_loads_empty(self):
        self.assertEqual(progress.load("/nonexistent/path.json"), {})

    def test_corrupt_file_loads_empty(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
            path = f.name
        try:
            self.assertEqual(progress.load(path), {})
        finally:
            os.unlink(path)

    def test_save_then_load_roundtrips(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "s.json")
        progress.save(path, {"1": {"label": "x", "status": "pending"}})
        self.assertEqual(progress.load(path), {"1": {"label": "x", "status": "pending"}})

if __name__ == "__main__":
    unittest.main()
