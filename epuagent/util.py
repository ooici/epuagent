# Copyright 2013 University of Chicago

import os

def disable_ion_busyloop_detect():
    if not "ION_NO_BUSYLOOP_DETECT" in os.environ:
        os.environ['ION_NO_BUSYLOOP_DETECT'] = "1"

def determine_path():
    """find path of current file,

    Borrowed from wxglade.py"""
    try:
        root = __file__
        if os.path.islink(root):
            root = os.path.realpath(root)
        return os.path.dirname(os.path.abspath(root))
    except:
        print "I'm sorry, but something is wrong."
        print "There is no __file__ variable. Please contact the author."
        sys.exit()

def get_config_paths(configs):
    """converts a list of config file names to a list of absolute paths
    to those config files, like so:

    get_config_files(["service", "provisioner"]

    returns:

    ["/path/to/epu/config/service.yml", "/path/to/epu/config/provisioner.yml"]
    """

    if not isinstance(configs, list):
        raise ArgumentError("get_config_files expects a list of configs")

    module_path = determine_path()
    config_dir = os.path.join(module_path, "config")

    paths = []
    for config in configs:
        if not config.endswith(".yml"):
            config = "%s.yml" % config
        path = os.path.join(config_dir, config)
        paths.append(path)

    return paths
