import signal
import uuid
import tempfile
from ion.core.process.process import Process
import os

import twisted.internet.utils
from twisted.internet import defer
from twisted.trial import unittest

from ion.test.iontest import IonTestCase
from ion.util import procutils

from epuagent.agent import EPUAgent
from epuagent.supervisor import Supervisor

import ion.util.ionlog
log = ion.util.ionlog.getLogger(__name__)

NODE_ID = "the_node_id"


SUPERVISORD_CONF = """
[program:proc1]
command=/bin/cat
autorestart=false
startsecs=0
stdout_logfile=NONE
stderr_logfile=NONE

[program:proc2]
command=/bin/cat
autorestart=false
startsecs=0
stdout_logfile=NONE
stderr_logfile=NONE

[unix_http_server]
file=%(here)s/supervisor.sock

[supervisord]
logfile=%(here)s/supervisord.log
pidfile=%(here)s/supervisord.pid

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix://%(here)s/supervisor.sock
"""

class EPUAgentIntegrationTests(IonTestCase):
    """Integration tests for EPU Agent

    Uses real ION messaging, real supervisord, and real child processes.
    Requires supervisord command to be available in $PATH.
    (easy_install supervisor)
    """

    @defer.inlineCallbacks
    def setUp(self):
        yield self._start_container()
        self.subscriber = TestSubscriber()
        self.subscriber_id = yield self._spawn_process(self.subscriber)

        self.tmpdir = None
        self.supervisor = None

    @defer.inlineCallbacks
    def tearDown(self):
        yield self._shutdown_processes()
        yield self._stop_container()

        if self.supervisor:
            try:
                yield self.supervisor.shutdown()
            except:
                pass

            # shutting down takes awhile..
            sock = os.path.join(self.tmpdir, "supervisor.sock")
            i = 0
            while os.path.exists(sock) and i < 100:
                yield procutils.asleep(0.1)
                i += 1

        if self.tmpdir and os.path.exists(self.tmpdir):
            try:
                os.remove(os.path.join(self.tmpdir, "supervisord.conf"))
            except IOError:
                pass
            try:
                os.remove(os.path.join(self.tmpdir, "supervisord.log"))
            except IOError:
                pass
            try:
                os.rmdir(self.tmpdir)
            except OSError, e:
                log.warn("Failed to remove test temp dir %s: %s", self.tmpdir, e)

    @defer.inlineCallbacks
    def test_no_supervisor(self):

        # make up a nonexistent path
        sock = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        agent = yield self._setup_agent(sock)

        yield agent.heartbeat()
        yield self.subscriber.deferred

        self.assertEqual(1, self.subscriber.beat_count)

        self.assertBasics(self.subscriber.last_beat, "MONITOR_ERROR")
        log.debug(self.subscriber.last_beat)
    
    @defer.inlineCallbacks
    def test_everything(self):

        yield self._setup_supervisord()
        log.debug("supervisord started")

        sock = os.path.join(self.tmpdir, "supervisor.sock")
        self.supervisor = Supervisor(sock)

        agent = yield self._setup_agent(sock)

        for i in range(3):
            # automatic heartbeat is turned off so we don't deal with time
            yield agent.heartbeat()
            yield self.subscriber.deferred

            self.assertEqual(i+1, self.subscriber.beat_count)
            self.assertBasics(self.subscriber.last_beat)

        # now kill a process and see that it is reflected in heartbeat

        # use backdoor supervisor client to find PID
        procs = yield self.supervisor.query()
        self.assertEqual(2, len(procs))
        if procs[0]['name'] == 'proc1':
            proc1 = procs[0]
        elif procs[1]['name'] == 'proc1':
            proc1 = procs[1]
        else:
            proc1 = None #stifle pycharm warning
            self.fail("process proc1 not found")

        pid = proc1['pid']
        if not pid:
            self.fail('No PID for proc1')

        log.debug("Killing process %s", pid)
        os.kill(pid, signal.SIGTERM)
        dead = False
        tries = 100
        while not dead and tries:
            yield procutils.asleep(0.05)
            try:
                os.kill(pid, 0)
            except OSError:
                dead = True
            tries -= 1
        self.assertTrue(dead, "process didn't die!")

        yield agent.heartbeat()
        yield self.subscriber.deferred
        self.assertBasics(self.subscriber.last_beat, "PROCESS_ERROR")

        failed_processes = self.subscriber.last_beat['failed_processes']
        self.assertEqual(1, len(failed_processes))
        failed = failed_processes[0]
        self.assertEqual("proc1", failed['name'])

    @defer.inlineCallbacks
    def _setup_supervisord(self):
        supd_exe = which('supervisord')
        if not supd_exe:
            raise unittest.SkipTest("Skipping: supervisord executable not found in path")

        self.tmpdir = tempfile.mkdtemp()

        conf = os.path.join(self.tmpdir, "supervisord.conf")

        f = None
        try:
            f = open(conf, 'w')
            f.write(SUPERVISORD_CONF)
        finally:
            if f:
                f.close()

        rc = yield twisted.internet.utils.getProcessValue(supd_exe,
                                                          args=('-c', conf))
        self.assertEqual(0, rc, "supervisord didn't start ok!")

    @defer.inlineCallbacks
    def _setup_agent(self, socket_path):
        spawnargs = {
            'heartbeat_dest': self.subscriber_id,
            'heartbeat_op': 'beat',
            'node_id': NODE_ID,
            'period_seconds': 2.0,
            'start_heartbeat': False,
            'supervisor_socket': socket_path}
        agent = EPUAgent(spawnargs=spawnargs)
        yield self._spawn_process(agent)
        defer.returnValue(agent)

    def assertBasics(self, state, expected="OK"):
        self.assertEqual(NODE_ID, state['node_id'])
        self.assertTrue(state['timestamp'])
        self.assertEqual(expected, state['state'])


class TestSubscriber(Process):
    def __init__(self, *args, **kwargs):
        Process.__init__(self, *args, **kwargs)
        self.last_beat = None
        self.beat_count = 0
        self.deferred = defer.Deferred()

    def op_beat(self, content, headers, msg):
        log.info('Got heartbeat: %s', content)
        self.last_beat = content
        self.beat_count += 1
        self.deferred.callback(content)
        self.deferred = defer.Deferred()


def _one_process(state, exitstatus=0, spawnerr=''):
    return {'name' : str(uuid.uuid4()), 'state' : state,
            'exitstatus' :exitstatus, 'spawnerr' : spawnerr}

def which(program):
    import os
    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None
