import gevent.monkey ; gevent.monkey.patch_all()

import uuid
import logging

import dashi.bootstrap as bootstrap
from dashi.util import LoopingCall 

from epuagent.supervisor import Supervisor
from epuagent.core import EPUAgentCore
from epuagent.util import get_config_paths

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class EPUAgent(object):
    """Elastic Process Unit (EPU) Agent. Monitors vitals in running VMs.
    """

    def __init__(self, *args, **kwargs):

        configs = ["epuagent"]
        config_files = get_config_paths(configs)
        self.CFG = bootstrap.configure(config_files)

        topic = self.CFG.epuagent.get('service_name')
        self.topic = topic or "epu_agent_%s" % uuid.uuid4()

        heartbeat_dest = kwargs.get('heartbeat_dest')
        self.heartbeat_dest = heartbeat_dest or self.CFG.epuagent.heartbeat_dest

        node_id = kwargs.get('node_id')
        self.node_id = node_id or self.CFG.epuagent.node_id

        heartbeat_op = kwargs.get('heartbeat_op')
        self.heartbeat_op = heartbeat_op or self.CFG.epuagent.heartbeat_op

        period = kwargs.get('period_seconds')
        self.period = float(period or self.CFG.epuagent.period_seconds)

        # for testing, allow for not starting heartbeat automatically
        self.start_beat = kwargs.get('start_heartbeat', True)

        amqp_uri = kwargs.get('amqp_uri')

        sock = kwargs.get('supervisor_socket')
        sock = sock or self.CFG.epuagent.get('supervisor_socket')
        if sock:
            log.debug("monitoring a process supervisor at: %s", sock)
            self.supervisor = Supervisor(sock)
        else:
            log.debug("not monitoring process supervisor")
            self.supervisor = None

        self.core = EPUAgentCore(self.node_id, supervisor=self.supervisor)

        self.dashi = bootstrap.dashi_connect(self.topic, self.CFG, amqp_uri)

    def start(self):
        log.info('EPUAgent starting')

        self.dashi.handle(self.heartbeat)

        self.loop = LoopingCall(self._loop)
        if self.start_beat:
            log.debug('Starting heartbeat loop - %s second interval', self.period)
            self.loop.start(self.period)

        try:
            self.dashi.consume()
        except KeyboardInterrupt:
            log.warning("Caught terminate signal. Exiting")
        else:
            log.info("Exiting normally.")


    def _loop(self):
        return self.heartbeat()

    def heartbeat(self):
        try:
            state = self.core.get_state()
            self.dashi.fire(self.heartbeat_dest, self.heartbeat_op,
                    heartbeat=state)
        except Exception, e:
            # unhandled exceptions will terminate the LoopingCall
            log.error('Error heartbeating: %s', e, exc_info=True)

def main():
    epuagent = EPUAgent()
    epuagent.start()

if __name__ == "__main__":
    main()
