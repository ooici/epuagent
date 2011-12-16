import time
import logging

from epuagent.supervisor import RUNNING_STATES, SupervisorError

log = logging.getLogger(__name__)

class EPUAgentCore(object):
    """Core state detection of EPU Agent
    """
    def __init__(self, node_id, supervisor=None):
        self.node_id = node_id
        self.supervisor = supervisor

        # We only want to send log information at first sign of failure.
        # After that we just send basic information declaring that the
        # process is still dead. Cache it here.
        self.fail_cache = {}

    def get_state(self):
        state = self._base_state()

        if not self.supervisor:
            return state

        sup_errors = self._supervisor_errors()
        if sup_errors:
            state.update(sup_errors)
        else:
            state['state'] = 'OK'
        return state

    def _base_state(self):
        return {'node_id' : self.node_id,
                'timestamp' : time.time(),
        }

    def _supervisor_errors(self):
        try:
            failed = self._failed_processes()

            if failed:
                ret = {'state' : 'PROCESS_ERROR', 'failed_processes' : failed}
            else:
                ret = None
            return ret

        except SupervisorError, e:
            log.error("Error querying supervisord: %s", e)
            ret = {'state' : 'MONITOR_ERROR', 'error' : str(e)}
            return ret

    def _failed_processes(self):
        procs = self.supervisor.query()

        failed = None
        for proc in procs:
            state = proc['state']
            if state not in RUNNING_STATES:
                proc_fail = self._one_process_failure(proc)
                if failed is None:
                    failed = [proc_fail]
                else:
                    failed.append(proc_fail)

            else:
                # remove from failure list if present
                self.fail_cache.pop(proc['name'], None)

        nprocs = len(procs)
        log.debug("%d of %d supervised process(es) OK",
                  nprocs if not failed else nprocs-len(failed), nprocs)

        return failed

    def _one_process_failure(self, proc):
        name = proc['name']
        prev = self.fail_cache.get(name)

        if (prev and prev.get('state') == proc.get('state') and
            prev.get('exitcode') == proc.get('exitstatus') and
            prev.get('stop_timestamp') == proc.get('stop')):
            return dict(prev)

        failure = {'name': proc.get('name'), 'state': proc.get('state'),
                   'statename': proc.get('statename'),
                   'exitcode': proc.get('exitstatus'),
                   'stop_timestamp': proc.get('stop') or None,
                   'error': proc.get('spawnerr'),
                   'error_time' : time.time()}

        # store in cache then make a copy and add detailed error info
        # only want that the first time

        self.fail_cache[name] = failure
        failure = dict(failure)

        stderr_path = proc.get('stderr_logfile')
        if stderr_path:
            failure['stderr'] = _get_file(stderr_path)

        return failure


def _get_file(path):
    if not path:
        return None
    f = None
    try:
        f = open(path)
        return f.read()
    except IOError, e:
        log.warn('Failed to read file: %s: %s', path, e)
        return None
    finally:
        if f:
            f.close()
