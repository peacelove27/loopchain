#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import logging
import multiprocessing
import getopt
import gunicorn.app.base
from gunicorn.six import iteritems

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.rest_server.rest_server import ServerComponents


def number_of_workers():
    return (multiprocessing.cpu_count() * 2) + 1


class StandaloneApplication(gunicorn.app.base.BaseApplication):
    """Web server runner by gunicorn.
    """

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super(StandaloneApplication, self).__init__()

    def load_config(self):
        config = dict([(key, value) for key, value in iteritems(self.options)
                       if key in self.cfg.settings and value is not None])
        for key, value in iteritems(config):
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def usage():
    print("USAGE: RESTful proxy")
    print("python3 rest_proxy.py [option] [value] ...")
    print("-------------------------------")
    print("option list")
    print("-------------------------------")
    print("-h or --help : print this usage")
    print("-p or --port : port of Peer Service itself")
    print("-d : Display colored log.")


def main(argv):
    util.logger.spam("RESTful proxy main got argv(list): " + str(argv))

    try:
        opts, args = getopt.getopt(argv, "dhp:",
                                   ["help",
                                    "port=",
                                    ])
    except getopt.GetoptError as e:
        logging.error(e)
        usage()
        sys.exit(1)

    # Port and host values.
    port = conf.PORT_PEER
    host = '0.0.0.0'

    # Parse command line arguments.
    for opt, arg in opts:
        if opt == "-p":
            port = int(arg)
        elif opt == "-d":
            util.set_log_level_debug()
        elif opt == "-h":
            usage()
            return


    # Connect gRPC stub.
    ServerComponents().set_stub_port(port, conf.IP_LOCAL)
    ServerComponents().set_argument()
    ServerComponents().set_resource()


    api_port = port + conf.PORT_DIFF_REST_SERVICE_CONTAINER
    logging.debug("Run gunicorn webserver for HA. Port = %s", str(api_port))

    certfile = ""
    keyfile = ""

    if ServerComponents().ssl_context is not None:
        certfile = ServerComponents().ssl_context(0)
        keyfile = ServerComponents().ssl_context(1)

    options = {
        'bind': '%s:%s' % (host, api_port),
        'workers': number_of_workers(),
        'certfile': certfile,
        'keyfile': keyfile
    }

    StandaloneApplication(ServerComponents().app, options).run()


# Run as gunicorn web server.
if __name__ == "__main__":
    main(sys.argv[1:])