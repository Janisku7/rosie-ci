# The MIT License (MIT)
#
# Copyright (c) 2017 Scott Shawcroft for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import os
import redis
import serial
from serial.tools import list_ports
import sh
import shutil
import time
import storage

redis = redis.Redis()

def redis_log(key, message):
    redis.append(key, message)

def run_tests(board, binary, tests, log_key=None):
    serial_device_name = None
    for port in list_ports.comports():
        if port.location and port.location[2:] == board["path"]:
            serial_device_name = port.name
    if not serial_device_name:
        raise RuntimeError("Board not found at path: " + board["path"])

    bootloader = board["bootloader"]

    with redis.lock("lock:device@" + board["path"], timeout=60*20) as lock:
        # Trigger the bootloader.
        if bootloader in ("uf2", "samba"):
            s = serial.Serial("/dev/" + serial_device_name, 1200)
            s.close()

        time.sleep(5)

        if bootloader == "uf2":
            # Mount the filesystem.
            disk_path = None
            for disk in os.listdir("/dev/disk/by-path"):
                if board["path"] in disk:
                    disk_path = disk
            if not disk_path:
                raise RuntimeError("Disk not found for board: " + board["path"])
            
            disk_path = "/dev/disk/by-path/" + disk_path
            if os.path.isfile(disk_path + "-part1"):
                raise RuntimeError("MCU not in bootloader because part1 exists.")

            sh.pmount(disk_path, "fs-" + board["path"])
            mountpoint = "/media/fs-" + board["path"]
            redis_log(log_key, "Successfully mounted UF2 bootloader at {0}\n".format(mountpoint))
            with open(mountpoint + "/INFO_UF2.TXT", "r") as f:
                redis_log(log_key, f.read() + "\n")
            shutil.copy(binary, mountpoint)
            # Unmount the mountpoint in case the device has disappeared already after the UF2
            # was flashed.
            sh.pumount(mountpoint)

        time.sleep(5)

        if "circuitpython_tests" in tests:
            # First find our CircuitPython disk.
            disk_path = None
            for disk in os.listdir("/dev/disk/by-path"):
                if board["path"] in disk and disk.endswith("part1"):
                    disk_path = disk
            if not disk_path:
                raise RuntimeError("Cannot find CIRCUITPY disk for device: " + board["path"])

            disk_path = "/dev/disk/by-path/" + disk_path

            with storage.mount(storage.NativeFileSystem(disk_path), "/media/cpy-" + board["path"]):
                mountpoint = "/media/cpy-" + board["path"]
                redis_log(log_key, "Successfully mounted CIRCUITPY disk at {0}\n".format(mountpoint))

                # Now find the serial.
                serial_device_name = None
                for port in list_ports.comports():
                    if port.location and port.location[2:] == board["path"]:
                        serial_device_name = port.name
                if not serial_device_name:
                    raise RuntimeError("No CircuitPython serial connection found at path: " + board["path"])
                with serial.Serial("/dev/" + serial_device_name) as conn:
                    pass


    return True

if __name__ == "__main__":
    pass
