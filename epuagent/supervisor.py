from __future__ import absolute_import
import logging
import xmlrpclib
import supervisor.xmlrpc

log = logging.getLogger(__name__)

# this state information is copied from supervisord source, to avoid
# otherwise needless dependency
class ProcessStates:
    STOPPED = 0
    STARTING = 10
    RUNNING = 20
    BACKOFF = 30
    STOPPING = 40
    EXITED = 100
    FATAL = 200
    UNKNOWN = 1000

STOPPED_STATES = (ProcessStates.STOPPED,
                  ProcessStates.EXITED,
                  ProcessStates.FATAL,
                  ProcessStates.UNKNOWN)

RUNNING_STATES = (ProcessStates.RUNNING,
                  ProcessStates.BACKOFF,
                  ProcessStates.STARTING)


class Supervisor(object):
    """Interface to supervisord process via XML-RPC

    @note There are many other operations available than what is being used.
    See http://supervisord.org/api.html for a list. It should also be possible
    to run the "listMethods" and "methodHelp" operations to get information
    directly from the service.
    """

    def __init__(self, url, username=None, password=None):
        self.url = url
        self.username = username
        self.password = password

    def _proxy(self):
        transport = supervisor.xmlrpc.SupervisorTransport(self.username,
                self.password, self.url)
        return xmlrpclib.ServerProxy('http://127.0.0.1',
                transport=transport)

    def query(self):
        """Checks supervisord for process information
        """
        return self._safe_call(self._proxy().supervisor.getAllProcessInfo)

    def shutdown(self):
        """Gracefully terminates all processes and the supervisor itself
        """
        return self._safe_call(self._proxy().supervisor.shutdown)

    def _safe_call(self, method, *args, **kwargs):
        try:
            return method(*args, **kwargs)


        except xmlrpclib.Fault, e:
            raise SupervisorError("Remote fault: %s" % e)

        except xmlrpclib.Error, e:
            raise SupervisorError("XMLRPC error: %s" % e)

        except Exception, e:
            raise SupervisorError("UNIX socket (%s) connection error: %s"
                                  % (self.url, e))

class SupervisorError(Exception):
    def __str__(self):
        s = self.__doc__ or self.__class__.__name__
        if self[0]:
            s = '%s: %s' % (s, self[0])
        return s


__all__ = ['ProcessStates', 'STOPPED_STATES', 'RUNNING_STATES', 'Supervisor',
           'SupervisorError']
