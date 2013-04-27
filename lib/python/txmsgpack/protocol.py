
import errno
import msgpack
from twisted.python import failure
from twisted.internet import protocol
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.protocols import policies

MSGTYPE_REQUEST=0
MSGTYPE_RESPONSE=1
MSGTYPE_NOTIFICATION=2

class MsgpackError(Exception):
    def __init__(self, message, errno=0, result=None):
        """
        msgpack rpc errors include a 'result' field
        """
        self.message = message
        self.errno   = errno
        self.result  = result

    def __str__(self):
        return "[Errno %s] %s" % (self.errno, self.message)

class Msgpack(protocol.Protocol, policies.TimeoutMixin):
    """
    msgpack rpc client/server protocol

    @ivar factory: The L{MsgpackClientFactory} or L{MsgpackServerFactory}  which created this L{Msgpack}.
    """
    def __init__(self, factory, sendErrors=False, timeOut=None, packerEncoding="utf-8", unpackerEncoding=None, default=None):
        """
        @param factory: factory which created this protocol.
        @type factory: C{protocol.Factory}.
        @param sendErrors: forward any uncaught Exception details to remote peer.
        @type sendErrors: C{bool}.
        @param timeOut: idle timeout in seconds before connection will be closed.
        @type timeOut: C{int}
        @param packerEncoding: encoding used to encode Python str and unicode. Default is 'utf-8'.
        @type packerEncoding: C{str}
        @param unpackerEncoding: encoding used for decoding msgpack bytes. If None (default), msgpack bytes are deserialized to Python bytes.
        @type unpackerEncoding: C{str}.
        @param default: if msgpack fails to serialize an object it will pass the object into this method, and try to serialize the result.
        @type default: C{callable}.
        """
        self.factory = factory
        self._sendErrors = sendErrors
        self._incoming_requests = {}
        self._outgoing_requests = {}
        self._next_msgid = 0
        self._packer = msgpack.Packer(encoding=packerEncoding)
        self._unpacker = msgpack.Unpacker(encoding=unpackerEncoding, unicode_errors='strict')

    def createRequest(self, method, *params):
        msgid = self.getNextMsgid()
        message = (MSGTYPE_REQUEST, msgid, method, params)
        self.writeMessage(message)

        df = defer.Deferred()
        self._outgoing_requests[msgid] = df
        return df

    def createNotification(self, method, params):
        if not type(params) in (list, tuple):
            params = (params,)
        message = (MSGTYPE_NOTIFICATION, method, params)
        self.writeMessage(message)

    def getNextMsgid(self):
        self._next_msgid += 1
        return self._next_msgid

    def dataReceived(self, data):
        self.resetTimeout()

        self._unpacker.feed(data)
        for message in self._unpacker:
            self.messageReceived(message)

    def messageReceived(self, message):
        if message[0] == MSGTYPE_REQUEST:
            return self.requestReceived(message)
        if message[0] == MSGTYPE_RESPONSE:
            return self.responseReceived(message)
        if message[0] == MSGTYPE_NOTIFICATION:
            return self.notificationReceived(message)

        return self.undefinedMessageReceived(message)

    def requestReceived(self, message):
        try:
            (msgType, msgid, methodName, params) = message
        except ValueError, e:
            if self._sendErrors:
                raise
            if not len(message) == 4:
                raise MsgpackError("Incorrect message length. Expected 4; received %s" % (len(message),), errno.EINVAL)
            raise MsgpackError("Failed to unpack request.", errno.EINVAL)
        except Exception, e:
            if self._sendErrors:
                raise
            raise MsgpackError("Unexpected error. Failed to unpack request.", errno.EINVAL)

        if msgid in self._incoming_requests:
            raise MsgpackError("Request with msgid '%s' already exists" % (msgid,), errno.EALREADY)

        try:
            df  = self.getDeferredForMethod(msgid, methodName, params)
        except Exception, e:
            if self._sendErrors:
                f = failure.Failure()
            else:
                ex = MsgpackError("Failed to find method: %s" % (methodName,), errno.ENOSYS)
                f  = failure.Failure(exc_value=ex)
            return self.respondErrback(f, msgid)

        self._incoming_requests[msgid] = df
        df.addCallback(self.respondCallback, msgid)
        df.addErrback(self.respondErrback, msgid)
        df.addBoth(self.endRequest, msgid)
        return df

    def getCallableForMethodName(self, methodName):
        try:
            return getattr(self, "remote_" + methodName)
        except Exception, e:
            if self._sendErrors:
                raise
            raise MsgpackError("Client attempted to call unimplemented method: remote_%" % (methodName,), errno.ENOSYS)

    def getDeferredForMethod(self, msgid, methodName, params):
        try:
            method = self.getCallableForMethodName(methodName)
        except Exception, e:
            if self._sendErrors:
                raise
            raise MsgpackError("Client attempted to call unimplemented method: %s" % (methodName,), errno.ENOSYS)

        send_msgid = False
        try:
            """
            If the remote_method has a keyword argment called msgid, then pass
            it the msgid as a keyword argument. 'params' is always a list.
            """
            method_arguments = method.func_code.co_varnames
            if 'msgid' in method_arguments:
                send_msgid = True
        except Exception, e:
            pass


        try:
            if send_msgid:
                df = method(*params, msgid=msgid)
            else:
                df = method(*params)
        except TypeError, e:
            if self._sendErrors:
                raise
            raise MsgpackError("Wrong number of arguments for %s" % (methodName,), errno.EINVAL)
        except Exception, e:
            if self._sendErrors:
                raise
            raise MsgpackError("Unexpected error calling %s" % (methodName), 0)

        return df

    def endRequest(self, result, msgid):
        if msgid in self._incoming_requests:
            del self._incoming_requests[msgid]
        return result

    def responseReceived(self, message):
        try:
            (msgType, msgid, error, result) = message
        except Exception, e:
            if self._sendErrors:
                raise
            raise MsgpackError("Failed to unpack response: %s" % (e,), errno.EINVAL)

        try:
            df = self._outgoing_requests.pop(msgid)
        except KeyError, e:
            """
            There's nowhere to send this error, except the log
            if self._sendErrors:
                raise
            raise MsgpackError("Failed to find dispatched request with msgid %s to match incoming repsonse" % (msgid,), errno.ENOSYS)
            """
            pass

        if error is not None:
            """
            The remote host returned an error, so we need to create a Failure
            object to pass into the errback chain. The Failure object in turn
            requires an Exception
            """
            ex = MsgpackError(error, 0, result=result)
            df.errback(failure.Failure(exc_value=ex))
        else:
            df.callback(result)

    def respondCallback(self, result, msgid):
        error = None
        response = (MSGTYPE_RESPONSE, msgid, error, result)
        return self.writeMessage(response)

    def respondErrback(self, f, msgid):
        """
        """
        result = None
        if self._sendErrors:
            error = f.getBriefTraceback()
        else:
            error = f.getErrorMessage()
        self.respondError(msgid, error, result)

    def respondError(self, msgid, error, result=None):
        response = (MSGTYPE_RESPONSE, msgid, error, result)
        self.writeMessage(response)

    def writeMessage(self, message):
        try:
            message = self._packer.pack(message)
        except Exception, e:
            if self._sendErrors:
                raise
            raise MsgpackError("ERROR: Failed to write message: %s" % (message[0], message[1],))

        # transport.write returns None
        self.transport.write(message)

    def notificationReceived(self, message):
        # Notifications don't expect a return value, so they don't supply a msgid
        msgid = None

        try:
            (msgType, methodName, params) = message
        except Exception, e:
            # Log the error - there's no way to return it for a notification
            print e
            return

        try:
            df  = self.getDeferredForMethod(msgid, methodName, params)
        except Exception, e:
            # Log the error - there's no way to return it for a notification
            print e
            return

        df.addBoth(self.notificationCallback)
        return df

    def notificationCallback(self, result):
        # Log the result if required
        pass

    def undefinedMessageReceived(self, message):
        raise NotImplementedError("Msgpack received a message of type '%s', " \
                                  "and no method has been specified to " \
                                  "handle this." % (message[0],))


    def connectionMade(self):
        #print "connectionMade"
        self.factory.numProtocols = self.factory.numProtocols+1 
        """
        self.transport.write(
            "Welcome! There are currently %d open connections.\n" %
            (self.factory.numProtocols,))
        """

    def connectionLost(self, reason):
        #print "connectionLost"
        self.factory.numProtocols = self.factory.numProtocols-1

    def closeConnection(self):
        self.transport.loseConnection()


class MsgpackServerFactory(protocol.Factory):
    protocol = Msgpack
    numProtocols = 0

    def buildProtocol(self, addr):
        p = self.protocol(self, sendErrors=True)
        return p


class MsgpackClientFactory(protocol.ReconnectingClientFactory):
    maxDelay = 12
    protocol = Msgpack
    numProtocols = 0

    def buildProtocol(self, addr):
        self.resetDelay()
        p = self.protocol(self)
        return p
