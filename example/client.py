#!/usr/bin/env python
# coding: utf-8

import string
import random
import time
import msgpackrpc

ITERATIONS = 3000

def test_client():

    N = 12
    r = []
    for i in range(ITERATIONS):
        r.append(''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(N)))

    client = msgpackrpc.Client(msgpackrpc.Address('127.0.0.1', 8007), unpack_encoding = 'utf-8')

    start = time.time()
    for i in r:
        if i:
            res = client.call("echo", i)
            assert res == i

    duration = time.time() - start
    rqs_per_sec = ITERATIONS / duration

    print "Completed %s iterations in : %s" % (ITERATIONS, duration)
    print "Average requests/s: %s" % (rqs_per_sec,)

if __name__ == '__main__':
    test_client()
