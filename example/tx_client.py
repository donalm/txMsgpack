#!/usr/bin/env python
# coding: utf-8

from sys import platform as _platform
if _platform in ("linux", "linux2"):
    try:
        from twisted.internet import epollreactor
        epollreactor.install()
    except Exception, e:
        pass
elif _platform == "darwin":
    try:
        import twisted_kqueue
        twisted_kqueue.install()
    except Exception, e:
        pass
elif _platform == "win32":
    try:
        from twisted.internet import iocpreactor
        iocpreactor.install()
    except Exception, e:
        pass

import string
import random
import time

from twisted.python import failure
from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet import endpoints
from txmsgpack.protocol import MsgpackClientFactory

ITERATIONS=3000


def create_client():
    point = endpoints.TCP4ClientEndpoint(reactor, "localhost", 8007)
    d = point.connect(MsgpackClientFactory())
    d.addCallback(test_client)

def compare(result, item):
    assert result == item

def done(res, start_time):
    duration = time.time() - start_time
    print "Completed %s iterations in : %ss" % (ITERATIONS, duration)
    print "Average requests/s: %s" % (ITERATIONS / duration,)
    reactor.stop()

def word(l):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(l))

def bounce(proto):
    items = [("TXM_" + word(25), word(16), word(128)) for i in range(ITERATIONS)]
    return send(proto, 'bounce', items)

def echo(proto):
    items = [("TXM_" + word(25),) for i in range(ITERATIONS)]
    return send(proto, 'echo', items)

def send(proto, method, items):
    dfs = []
    start_time = time.time()
    for item in items:
        dfs.append(proto.createRequest(method, *item))
    dfl = defer.DeferredList(dfs)
    return dfl, start_time

def test_client(proto):
    dfl, start_time = echo(proto)
    """
    To test 'bounce' instead of echo, uncomment the line below and comment the
    line above
    WARNING: 'bounce' will add data to your local memcached, if one is running
    """
    #dfl, start_time = bounce(proto)
    dfl.addBoth(done, start_time)


if __name__ == '__main__':
    reactor.callWhenRunning(create_client)
    reactor.run()
