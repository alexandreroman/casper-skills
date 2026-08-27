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

    def test_a_cancelled_step_is_counted_as_passed_not_pending(self):
        # The bar will never advance to a cancelled step, so it sits behind
        # the current one. Counting it as live work would report "2 of 3"
        # while the third and last step is the one actually running.
        tasks = [{"label": "a", "status": "completed"},
                 {"label": "b", "status": "cancelled"},
                 {"label": "c", "status": "in_progress"}]
        self.assertEqual(progress.actions_for(tasks), [[
            "progress", "set", "--total", "3", "--current", "3", "--label", "c"]])


class TestNothingInFlight(unittest.TestCase):
    def test_empty_list(self):
        self.assertTrue(progress.nothing_in_flight([]))

    def test_all_completed(self):
        self.assertTrue(progress.nothing_in_flight(
            [{"status": "completed"}, {"status": "completed"}]))

    def test_one_unfinished_is_enough(self):
        self.assertFalse(progress.nothing_in_flight(
            [{"status": "completed"}, {"status": "pending"}]))

    def test_cancelled_counts_as_finished(self):
        # opencode's todo tool can cancel a step. Before this, a run that
        # ended with its remaining steps cancelled had nothing in progress to
        # relabel the bar with and nothing "finished" enough to clear it, so
        # the last label stood over work that had stopped — across turns.
        self.assertTrue(progress.nothing_in_flight(
            [{"status": "completed"}, {"status": "cancelled"}]))
        self.assertTrue(progress.nothing_in_flight([{"status": "cancelled"}]))

    def test_a_wholly_cancelled_list_clears_the_bar_rather_than_stranding_it(self):
        tasks = [{"label": "a", "status": "completed"},
                 {"label": "b", "status": "cancelled"}]
        self.assertEqual(progress.actions_for(tasks), progress.CLEAR)
        self.assertEqual(progress.reconcile(tasks), progress.CLEAR)


class TestReconcile(unittest.TestCase):
    """The turn-end mapping: drop a bar the task list says the work is over."""

    def test_no_tasks_at_all_leaves_the_bar_alone(self):
        # No task tool ever reported anything, so this is the agent that has
        # none and drove `casper progress set` by hand. Its bar is meant to
        # survive the turn — background work outlives a turn boundary — and
        # session end is what clears it if the agent never does.
        self.assertEqual(progress.reconcile([]), [])

    def test_all_completed_clears(self):
        self.assertEqual(
            progress.reconcile([{"label": "a", "status": "completed"}]),
            progress.CLEAR)

    def test_in_flight_task_keeps_its_bar(self):
        self.assertEqual(
            progress.reconcile([{"label": "a", "status": "in_progress"}]), [])

    def test_clears_only_where_a_task_list_says_the_work_is_over(self):
        # The two mappings share `nothing_in_flight`, so they agree about what
        # "done" means — for every list that has tasks in it. They part on the
        # empty one: `actions_for` only ever runs where a task tool reported
        # something, so an empty list there is a list that emptied out, while
        # at the turn boundary it is a task tool that never spoke at all.
        for tasks in ([{"label": "a", "status": "completed"}],
                      [{"label": "a", "status": "in_progress"}],
                      [{"label": "", "status": "in_progress"}],
                      [{"label": "a", "status": "pending"}],
                      [{"label": "a", "status": "cancelled"}],
                      [{"label": "a", "status": "cancelled"},
                       {"label": "b", "status": "completed"}],
                      [{"label": "a", "status": "cancelled"},
                       {"label": "b", "status": "in_progress"}]):
            cleared = progress.actions_for(tasks) == progress.CLEAR
            self.assertEqual(cleared, progress.reconcile(tasks) == progress.CLEAR,
                             f"disagreement on {tasks}")
            self.assertEqual(cleared, progress.nothing_in_flight(tasks),
                             f"disagreement with the predicate on {tasks}")

        # And the empty list is the deliberate exception, in one place.
        self.assertTrue(progress.nothing_in_flight([]))
        self.assertEqual(progress.actions_for([]), progress.CLEAR)
        self.assertEqual(progress.reconcile([]), [])


class TestTurnEndActions(unittest.TestCase):
    """What a turn ending emits. One rule: it ends `working` when a bar is
    still up once the hook is done with it, `done` otherwise — and it reports
    nothing at all over a state the agent asserted for itself."""

    DONE = ["status", "set", "done"]
    WORKING = ["status", "set", "working"]
    IN_FLIGHT = [{"label": "a", "status": "completed"},
                 {"label": "b", "status": "in_progress"}]
    FINISHED = [{"label": "a", "status": "completed"}]

    def test_a_hand_driven_bar_holds_the_turn_at_working(self):
        # The reported bug: no task tool, so no task state, and a bar the agent
        # set by hand before ending its turn to let background subagents run.
        self.assertEqual(progress.turn_end_actions([], "working", True),
                         [self.WORKING])

    def test_no_bar_ends_the_turn_done(self):
        self.assertEqual(progress.turn_end_actions([], "working", False),
                         [self.DONE])

    def test_a_task_still_in_flight_keeps_its_bar_and_reports_working(self):
        self.assertEqual(progress.turn_end_actions(self.IN_FLIGHT, "working", True),
                         [self.WORKING])

    def test_a_finished_task_list_clears_its_bar_and_reports_done(self):
        # The bar is up right now, but this hook is about to clear it, so the
        # turn is over: `done` is judged on what will be left, not what is.
        self.assertEqual(progress.turn_end_actions(self.FINISHED, "working", True),
                         [self.DONE, progress.CLEAR[0]])

    def test_a_bar_that_never_existed_cannot_hold_an_in_flight_task(self):
        # actions_for leaves the bar alone when no in-progress task carries a
        # label, so there may be nothing on screen: no bar, nothing to show.
        self.assertEqual(progress.turn_end_actions(self.IN_FLIGHT, "working", False),
                         [self.DONE])

    def test_an_asserted_state_is_never_reported_over(self):
        # `blocked` and `error` are verdicts about something outside the turn.
        # The bar is still reconciled — that surface is independent.
        for state in ("blocked", "error"):
            self.assertEqual(progress.turn_end_actions([], state, True), [])
            self.assertEqual(progress.turn_end_actions([], state, False), [])
            self.assertEqual(progress.turn_end_actions(self.FINISHED, state, True),
                             progress.CLEAR)

    def test_states_a_hook_set_are_reported_over(self):
        # Everything turn end is there to decide between, including the state
        # its own turn-start hook set.
        for state in ("working", "idle", "done", "unknown", None):
            self.assertEqual(progress.turn_end_actions([], state, True),
                             [self.WORKING], f"state {state!r}")

    def test_an_unreadable_workspace_falls_back_to_done(self):
        # Both reads failed: the behaviour this had before they existed.
        self.assertEqual(progress.turn_end_actions([], None, False), [self.DONE])


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
