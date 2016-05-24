from mock import patch, mock
import os

os.environ['JUJU_UNIT_NAME'] = 'cinder'

from test_utils import RESTART_MAP

with patch('cinder_utils.register_configs') as register_configs:
    with patch('cinder_utils.restart_map') as restart_map:
        restart_map.return_value = RESTART_MAP
        register_configs.return_value = 'test-config'
        import actions

from test_utils import (
    CharmTestCase
)


class PauseTestCase(CharmTestCase):

    def setUp(self):
        super(PauseTestCase, self).setUp(
            actions, ["pause_unit_helper"])

    def test_pauses_services(self):
        actions.pause([])
        self.pause_unit_helper.assert_called_once_with('test-config')


class ResumeTestCase(CharmTestCase):

    def setUp(self):
        super(ResumeTestCase, self).setUp(
            actions, ["resume_unit_helper"])

    def test_pauses_services(self):
        actions.resume([])
        self.resume_unit_helper.assert_called_once_with('test-config')


class MainTestCase(CharmTestCase):

    def setUp(self):
        super(MainTestCase, self).setUp(actions, ["action_fail"])

    def test_invokes_action(self):
        dummy_calls = []

        def dummy_action(args):
            dummy_calls.append(True)

        with mock.patch.dict(actions.ACTIONS, {"foo": dummy_action}):
            actions.main(["foo"])
        self.assertEqual(dummy_calls, [True])

    def test_unknown_action(self):
        """Unknown actions aren't a traceback."""
        exit_string = actions.main(["foo"])
        self.assertEqual("Action foo undefined", exit_string)

    def test_failing_action(self):
        """Actions whose traceback trigger action_fail() calls."""
        dummy_calls = []

        self.action_fail.side_effect = dummy_calls.append

        def dummy_action(args):
            raise ValueError("uh oh")

        with mock.patch.dict(actions.ACTIONS, {"foo": dummy_action}):
            actions.main(["foo"])
        self.assertEqual(dummy_calls, ["uh oh"])
