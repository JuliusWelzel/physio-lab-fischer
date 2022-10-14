from contextlib import ExitStack
import sys
import os
from sys import exit
from pylsl import StreamInfo, StreamOutlet, local_clock

main_path = os.path.dirname(__file__)
sys.path.append(main_path)

from bbt import Signal, Device, SensorType, ImpedanceLevel

def try_to(condition, action, tries, message=None):
    t = 0
    while not condition() and t < tries:
        t += 1
        if message:
            print("{} ({}/{})".format(message, t, tries))
        action()
    return condition()


def config_signals(device):
    signals = device.get_signals()
    for s in signals:
        s.set_mode(1)


def record_one(device, signals, lsl_outlet):
    sequence, battery, flags, data = device.read()
    ts = local_clock()
    lsl_outlet.push_sample(data, ts)


def record_data(device, length, lsl_outlet):
    # create the csv files
    with ExitStack() as stack:
        active_signals = [s for s in device.get_signals() if s.mode() != 0]

        # record data
        device.start()
        f = int(device.get_frequency())
        for i in range(length * f):
            record_one(device, active_signals, lsl_outlet)
        device.stop()
    print("Stopped: ", not device.is_running())


def create_lsl_outlet(device, dev_name, dev_type, n_channels=None):
    srate = device.get_frequency()

    channel_names = []
    active_signals = [s for s in device.get_signals() if s.mode() != 0]
    for s in active_signals:
        signal_type = s.type()
        tmp_chn_nms = [f"{signal_type}-{i}" for i in range(s.channels() + 1)]
        channel_names.extend(tmp_chn_nms)

    print(channel_names)

    if not n_channels:
        n_channels = len(channel_names)

    info = StreamInfo(dev_name, dev_type, n_channels, srate, "float32")

    info.desc().append_child_value("manufacturer", "LSLBbtAmp")
    chns = info.desc().append_child("channels")
    for chan_ix, label in enumerate(channel_names):
        ch = chns.append_child("channel")
        ch.append_child_value("label", label)
        ch.append_child_value("unit", "au")
        ch.append_child_value("type", "Misc")

    # make an outlet
    lsl_outlet = StreamOutlet(info)

    return lsl_outlet


if __name__ == "__main__":

    name = "BBT-FBR-AAB071"
    length = 3  # specify number of seconds to record data
    with Device.create_bluetooth_device(name) as device:

        if not try_to(
            device.is_connected, device.connect, 10, "Connecting to {}".format(name)
        ):
            print("unable to connect")
            exit(1)
        print("Connected")

        print(f"Recording {length} seconds of data into csv files from device {name}")

        # create lsl outlets for all signals types
        ring_outlet = create_lsl_outlet(device, name, "ring", 10)

        config_signals(device)
        record_data(device, length, ring_outlet)

        del ring_outlet
        print("Lsl outlet for the ring deleted")

        if not try_to(lambda: not device.is_connected(), device.disconnect, 10):
            print("unable to disconnect")
            exit(1)
        print("Connected")
        print(device.is_connected())
