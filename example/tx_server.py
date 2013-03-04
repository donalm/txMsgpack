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


from txmsgpack.protocol import Msgpack
from twisted.internet import endpoints
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet import protocol
from twisted.protocols import memcache

from random import random

class Echo(Msgpack):
    memcacheClient = None

    def remote_echo(self, value, msgid=None):
        df = defer.Deferred()
        df.callback(value)
        return df

    def remote_bounce(self, one, two, three):
        if Echo.memcacheClient is None:
            return self.remote_echo((one, two, three))
        df = Echo.memcacheClient.set(one, "%s:%s" % (two, three))
        df.addCallback(lambda x:(one, two, three))
        return df


class EchoServerFactory(protocol.Factory):
    numProtocols = 0
    protocol = Echo
    sendErrors = True

    def __init__(self, sendErrors=False, memcacheClient=None):
        EchoServerFactory.sendErrors = sendErrors
        EchoServerFactory.protocol.memcacheClient = memcacheClient

    def buildProtocol(self, addr):
        return EchoServerFactory.protocol(self, sendErrors=EchoServerFactory.sendErrors)


def main():
    client = protocol.ClientCreator(reactor, memcache.MemCacheProtocol)
    df     = client.connectTCP("localhost", memcache.DEFAULT_PORT)
    df.addCallback(_main)
    df.addErrback(lambda x:_main(None))

def _main(memcache_client):
    if memcache_client is None:
        print "Memcache is not avaiable"
    else:
        print "WARNING: THIS SERVER WILL ADD DATA TO YOUR MEMCACHED SERVICE"
        print "memcache_client: %s" % (memcache_client,)
    endpoint = endpoints.TCP4ServerEndpoint(reactor, 8007)
    esf = EchoServerFactory(sendErrors=True, memcacheClient=memcache_client)
    endpoint.listen(esf)
    print "LISTENING"


if __name__ == '__main__':
    reactor.callWhenRunning(main)
    reactor.run()
