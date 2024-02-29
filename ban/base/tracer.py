import math

from ban.base.packet import Packet


class Tracer:
    def __init__(self):
        self.env = None
        self.tx_packet = list()
        self.total_tx_packet = 0
        self.success_tx_packet = list()
        self.total_success_tx_packet = 0
        self.success_tx_bit = 0
        self.total_success_tx_bit = 0
        self.consume_energy = 0  # watt
        self.initial_energy = None
        self.reset_time = None
        self.transaction_count = 0

    def set_env(self, env):
        self.env = env
        self.reset_time = self.env.now

    def set_initial_energy(self, energy):
        self.initial_energy = energy

    def reset(self):
        self.tx_packet.clear()
        self.success_tx_packet.clear()
        self.success_tx_bit = 0
        self.consume_energy: float = 0.0
        self.reset_time = self.env.now

    def add_tx_packet(self, packet: Packet):
        self.transaction_count += 1
        self.total_tx_packet += 1
        self.tx_packet.append(packet)
        tx_power = packet.get_spectrum_tx_params().tx_power
        self.add_consumed_energy(tx_power)

    def add_success_tx_packet(self, packet: Packet):
        self.success_tx_packet.append(packet)
        self.total_success_tx_packet += 1
        self.total_success_tx_bit += packet.get_size() * 8
        self.success_tx_bit += packet.get_size() * 8

    def get_throughput(self, total=False):
        if self.env is None:
            print('simpy.env was not initialized')
            return -1

        if self.env.now - self.reset_time == 0:
            return -1

        if total:
            return self.total_success_tx_bit / self.env.now

        return self.success_tx_bit / (self.env.now - self.reset_time)


    def add_consumed_energy(self, dbm: float):
        # convert dBm to watt
        if dbm == 0:
            w = 0.001
        else:
            mw = math.pow(10.0, dbm / 10.0)
            w = mw / 1000.0

        self.consume_energy += w


    def get_energy_consumption_ratio(self):
        if self.initial_energy is None:
            print('Initial energy was not initialized')
        else:
            return self.consume_energy / self.initial_energy


    def get_pkt_delivery_ratio(self, total=False):
        if total:
            return self.total_success_tx_packet / self.total_tx_packet

        if len(self.success_tx_packet) == 0:
            return 0


        return len(self.success_tx_packet) / len(self.tx_packet)


    def get_transaction_count(self):
        return self.transaction_count
