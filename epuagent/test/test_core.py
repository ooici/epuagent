import os
import uuid
import logging
import tempfile
import unittest

#from ion.core import ioninit

from epuagent.core import EPUAgentCore
from epuagent.supervisor import SupervisorError, ProcessStates

#CONF = ioninit.config(__name__)

log = logging.getLogger(__name__)

NODE_ID = "the_node_id"

class EPUAgentCoreTests(unittest.TestCase):
    def setUp(self):
        self.sup = FakeSupervisor()
        self.core = EPUAgentCore(NODE_ID, supervisor=self.sup)

    def assertBasics(self, state, expected="OK"):
        self.assertEqual(NODE_ID, state['node_id'])
        self.assertTrue(state['timestamp'])
        self.assertEqual(expected, state['state'])

    def test_supervisor_error(self):
        self.sup.error = SupervisorError('faaaaaaaail')
        state = self.core.get_state()
        self.assertBasics(state, "MONITOR_ERROR")
        self.assertTrue('faaaaaaaail' in state['error'])

    def test_series(self):
        self.sup.processes = [_one_process(ProcessStates.RUNNING),
                              _one_process(ProcessStates.RUNNING)]
        state = self.core.get_state()
        self.assertBasics(state)

        # mark one of the processes as failed and give it a fake logfile
        # to read and send back
        fail = self.sup.processes[1]
        fail['state'] = ProcessStates.FATAL
        fail['exitstatus'] = -1

        stderr = "this is the errros!"
        err_path = _write_tempfile(stderr)
        fail['stderr_logfile'] = err_path
        try:
            state = self.core.get_state()
        finally:
            os.unlink(err_path)
            
        self.assertBasics(state, "PROCESS_ERROR")

        failed_processes = state['failed_processes']
        self.assertEqual(1, len(failed_processes))
        failed = failed_processes[0]
        self.assertEqual(stderr, failed['stderr'])

        # next time around process should still be failed but no stderr
        state = self.core.get_state()
        self.assertBasics(state, "PROCESS_ERROR")
        failed_processes = state['failed_processes']
        self.assertEqual(1, len(failed_processes))
        failed = failed_processes[0]
        self.assertFalse(failed.get('stderr'))

        # make it all ok again
        fail['state'] = ProcessStates.RUNNING
        state = self.core.get_state()
        self.assertBasics(state)

def _one_process(state, exitstatus=0, spawnerr=''):
    return {'name' : str(uuid.uuid4()), 'state' : state,
            'exitstatus' :exitstatus, 'spawnerr' : spawnerr}

def _write_tempfile(text):
    fd,path = tempfile.mkstemp()
    f = None
    try:
        f = os.fdopen(fd, 'w')
        f.write(text)
    finally:
        if f:
            f.close()
    return path

class FakeSupervisor(object):
    def __init__(self):
        self.error = None
        self.processes = None

    def query(self):
        if self.error:
            raise self.error
        return self.processes
