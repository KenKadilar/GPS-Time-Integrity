"""writes a deliberately wrong time into a gpsd shared memory unit, so chrony sees a lying receiver"""

import ctypes
import sys
import time

unit = int(sys.argv[1])
shiftSeconds = float(sys.argv[2])
runSeconds = float(sys.argv[3])

SHM_KEY_BASE = 0x4E545030


class ShmTime(ctypes.Structure):
    _fields_ = [
        ("mode", ctypes.c_int),
        ("count", ctypes.c_int),
        ("clockTimeStampSec", ctypes.c_long),
        ("clockTimeStampUSec", ctypes.c_int),
        ("pad1", ctypes.c_int),
        ("receiveTimeStampSec", ctypes.c_long),
        ("receiveTimeStampUSec", ctypes.c_int),
        ("leap", ctypes.c_int),
        ("precision", ctypes.c_int),
        ("nsamples", ctypes.c_int),
        ("valid", ctypes.c_int),
        ("clockTimeStampNSec", ctypes.c_uint),
        ("receiveTimeStampNSec", ctypes.c_uint),
        ("dummy", ctypes.c_int * 8),
    ]


libc = ctypes.CDLL("libc.so.6", use_errno=True)
libc.shmget.restype = ctypes.c_int
libc.shmat.restype = ctypes.c_void_p

shmid = libc.shmget(SHM_KEY_BASE + unit, ctypes.sizeof(ShmTime), 0o666)
if shmid < 0:
    print("cannot reach shared memory unit %d, errno %d" % (unit, ctypes.get_errno()))
    raise SystemExit(1)

address = libc.shmat(shmid, None, 0)
segment = ShmTime.from_address(address)

print("writing unit %d with a %+.1f second shift for %.0f seconds" % (unit, shiftSeconds, runSeconds))

deadline = time.time() + runSeconds
samples = 0
while time.time() < deadline:
    receive = time.time()
    claimed = receive + shiftSeconds

    segment.valid = 0
    segment.count = segment.count + 1
    segment.mode = 1
    segment.clockTimeStampSec = int(claimed)
    segment.clockTimeStampUSec = int((claimed % 1) * 1000000)
    segment.clockTimeStampNSec = int((claimed % 1) * 1000000000)
    segment.receiveTimeStampSec = int(receive)
    segment.receiveTimeStampUSec = int((receive % 1) * 1000000)
    segment.receiveTimeStampNSec = int((receive % 1) * 1000000000)
    segment.leap = 0
    segment.precision = -20
    segment.nsamples = 3
    segment.count = segment.count + 1
    segment.valid = 1

    samples += 1
    time.sleep(1.0)

print("wrote %d spoofed samples" % samples)
