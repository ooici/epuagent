import gevent
import gevent.monkey ; gevent.monkey.patch_all()

import signal
import uuid
import logging
import tempfile
import unittest
import threading
import subprocess
import os

from time import sleep

import dashi.bootstrap as bootstrap

from epuagent.agent import EPUAgent
from epuagent.supervisor import Supervisor

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


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

class EPUAgentIntegrationTests(unittest.TestCase):
    """Integration tests for EPU Agent

    Uses real ION messaging, real supervisord, and real child processes.
    Requires supervisord command to be available in $PATH.
    (easy_install supervisor)
    """

    def setUp(self):
        self.amqp_uri = "memory://test"
        self.subscriber = TestSubscriber(amqp_uri=self.amqp_uri)
        self.subscriber_glet = gevent.spawn(self.subscriber.start)

        self.tmpdir = None
        self.supervisor = None

    def tearDown(self):
        if self.subscriber_glet:
           self.subscriber_glet.kill()

        if self.supervisor:
            try:
                self.supervisor.shutdown()
            except:
                pass

            # shutting down takes awhile..
            sock = os.path.join(self.tmpdir, "supervisor.sock")
            i = 0
            while os.path.exists(sock) and i < 100:
                sleep(0.1)
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

    def test_no_supervisor(self):

        # make up a nonexistent path
        sock = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        sock = "unix://%s" % sock
        agent = self._setup_agent(sock)

        self.subscriber.started.wait()
        agent.heartbeat()
        self.subscriber.did_beat.wait()
        self.subscriber.did_beat.clear()

        self.assertEqual(1, self.subscriber.beat_count)

        self.assertBasics(self.subscriber.last_beat, "MONITOR_ERROR")
        log.debug(self.subscriber.last_beat)

    def test_send_error(self):
        # just ensure exception doesn't bubble up where it would
        # terminate the LoopingCall

        sock = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        sock = "unix://%s" % sock
        agent = self._setup_agent(sock)

        def fake_send(*args, **kwargs):
            raise Exception("world exploded")
        agent.send = fake_send

        agent.heartbeat()
    
    def test_everything(self):

        self._setup_supervisord()
        log.debug("supervisord started")

        sock = os.path.join(self.tmpdir, "supervisor.sock")
        sock = "unix://%s" % sock
        self.supervisor = Supervisor(sock)

        agent = self._setup_agent(sock)

        for i in range(3):
            # automatic heartbeat is turned off so we don't deal with time
            agent.heartbeat()
            sleep(0.1)
            self.subscriber.did_beat.wait()
            self.subscriber.did_beat.clear()

            self.assertEqual(i+1, self.subscriber.beat_count)
            self.assertBasics(self.subscriber.last_beat)

        # now kill a process and see that it is reflected in heartbeat

        # use backdoor supervisor client to find PID
        procs = self.supervisor.query()
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
            sleep(0.05)
            try:
                os.kill(pid, 0)
            except OSError:
                dead = True
            tries -= 1
        self.assertTrue(dead, "process didn't die!")

        agent.heartbeat()
        self.subscriber.did_beat.wait()
        self.subscriber.did_beat.clear()
        self.assertBasics(self.subscriber.last_beat, "PROCESS_ERROR")

        failed_processes = self.subscriber.last_beat['failed_processes']
        self.assertEqual(1, len(failed_processes))
        failed = failed_processes[0]
        self.assertEqual("proc1", failed['name'])

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

        rc = subprocess.call([supd_exe, '-c', conf])
        self.assertEqual(0, rc, "supervisord didn't start ok!")

    def _setup_agent(self, socket_path):
        spawnargs = {
            'heartbeat_dest': self.subscriber.id,
            'heartbeat_op': 'beat',
            'node_id': NODE_ID,
            'period_seconds': 2.0,
            'start_heartbeat': False,
            'supervisor_socket': socket_path,
            'amqp_uri': self.amqp_uri}
        agent = EPUAgent(**spawnargs)
        agent_glet = gevent.spawn(agent.start)
        return agent

    def assertBasics(self, state, expected="OK"):
        self.assertEqual(NODE_ID, state['node_id'])
        self.assertTrue(state['timestamp'])
        self.assertEqual(expected, state['state'])


class TestSubscriber(object):
    def __init__(self, *args, **kwargs):
        amqp_uri = kwargs.get('amqp_uri')
        self.id = "subscriber-%s" % uuid.uuid4()
        self.last_beat = None
        self.beat_count = 0
        self.started = threading.Event()
        self.did_beat = threading.Event()
        self.dashi = bootstrap.dashi_connect(self.id, amqp_uri=amqp_uri)

    def start(self):

        self.dashi.handle(self.beat)
        self.started.set()
        try:
            self.dashi.consume()
        except gevent.GreenletExit:
            log.info("Exiting '%s'" % self.id)

    def beat(self, state=None):
        log.info('Got heartbeat: %s', state)
        self.last_beat = state
        self.beat_count += 1
        self.did_beat.set()

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
