# Copyright 2013 University of Chicago

import os
import uuid
import tempfile
import unittest

from epuagent.supervisor import Supervisor, SupervisorError

class SupervisorTests(unittest.TestCase):
    def test_error_nofile(self):
        noexist = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        noexist = "unix://%s" % noexist
        soup = Supervisor(noexist)
        self.assertRaises(SupervisorError, soup.query)
