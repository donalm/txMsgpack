txMsgpack
=========


*For the latest source code, see <http://github.com/donalm/txMsgpack>*


``txMsgpack`` is a Twisted Protocol to support msgpack-rpc with a more tx
idiom than the Tornado implementation that's already available.
It uses [Twisted](http://twistedmatrix.com) for asynchronous network
communication.

### So Far ###

- Msgpack
- MsgpackServerFactory
- MsgpackClientFactory


Dependencies
------------
- You'll need msgpack    <https://pypi.python.org/pypi/msgpack-python/>
- And Twisted            <http://twistedmatrix.com/trac/>
- And one file from Zope <https://pypi.python.org/pypi/zope.interface#download>


Install
-------
Everything is in lib/python/txmsgpack/ so just make sure <LOCATION>lib/python is in PYTHONPATH.
```
import txmsgpack
txmsgpack.Msgpack
txmsgpack.MsgpackError
txmsgpack.MsgpackServerFactory
txmsgpack.MsgpackClientFactory
txmsgpack.MSGTYPE\_REQUEST
txmsgpack.MSGTYPE\_RESPONSE
txmsgpack.MSGTYPE\_NOTIFICATION
```

Usage
-----

See the example directory for:
- tx\_client.py
- tx\_server.py
- client.py
