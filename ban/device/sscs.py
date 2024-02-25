import logging
from enum import Enum

import simpy
import tqdm
from dataclasses import dataclass

from simpy.events import NORMAL

from ban.base.logging.log import SeoungSimLogger
from ban.base.packet import Packet
from ban.base.tracer import Tracer
from ban.base.utils import milliseconds
from ban.device.mac_header import BanFrameType, BanFrameSubType, AssignedLinkElement

import numpy as np


class BanTxOption(Enum):
    TX_OPTION_NONE = 0
    TX_OPTION_ACK = 1
    TX_OPTION_GTS = 2
    TX_OPTION_INDIRECT = 3


class BanDataConfirmStatus(Enum):
    IEEE_802_15_6_SUCCESS = 0
    IEEE_802_15_6_TRANSACTION_OVERFLOW = 1
    IEEE_802_15_6_TRANSACTION_EXPIRED = 2
    IEEE_802_15_6_CHANNEL_ACCESS_FAILURE = 3
    IEEE_802_15_6_INVALID_ADDRESS = 4
    IEEE_802_15_6_INVALID_GTS = 5
    IEEE_802_15_6_NO_ACK = 6
    IEEE_802_15_6_COUNTER_ERROR = 7
    IEEE_802_15_6_FRAME_TOO_LONG = 8
    IEEE_802_15_6_UNVAILABLE_KEY = 9
    IEEE_802_15_6_UNSUPPORTED_SECURITY = 10
    IEEE_802_15_6_INVALID_PARAMETER = 11
    IEEE_802_15_6_EXCEED_ALLOCATION_INTERVAL = 12


@dataclass
class DqnStatusInfo:
    node_id = None
    current_state = None
    current_action = None
    reward = None
    next_state = None
    done = None
    steps = None


@dataclass
class BanTxParams:
    ban_id: int | None = None
    node_id: int | None = None
    recipient_id: int | None = None
    seq_num: int | None = None
    tx_option: BanTxOption | None = None


# Service specific convergence sub-layer (SSCS)
class BanSSCS:
    logger = SeoungSimLogger(logger_name="BAN-SSCS", level=logging.DEBUG)

    def __init__(self):
        self.env: simpy.Environment | None = None
        self.packet_list: list = list()
        self.mac: None = None   # To interact with a MAC layer
        self.node_list: list = list()
        self.tx_params: BanTxParams = BanTxParams()
        self.beacon_interval: float = milliseconds(255)  # ms
        self.tx_power: float = 0   # dBm

        self.logger = logging.getLogger("BAN-SSCS")

        self.coordinator: bool = False


    def set_env(self, env):
        self.env = env

    def set_mac(self, mac):
        self.mac = mac

    def set_tx_params(self, tx_params):
        self.tx_params = tx_params


    def set_node_list(self, node_id):
        self.node_list.append(node_id)


    def data_confirm(self, status: BanDataConfirmStatus):
        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=f"{self.__class__.__name__}[{self.mac.get_mac_params().node_id}] "
                + f"MAC reported transaction result: {status.name}",
            level=logging.INFO,
        )
        print(status.name)


    def data_indication(self, rx_packet: Packet):
        # data received
        rx_power = rx_packet.get_spectrum_tx_params().tx_power
        sender_id = rx_packet.get_mac_header().sender_id

        '''update Q-table'''
        if self.coordinator:
            BanSSCS.logger.log(
                sim_time=self.env.now,
                msg=f"{self.__class__.__name__}[{self.mac.get_mac_params().node_id}] updating Q-table",
                level=logging.INFO
            )



        ##### added code #####
        sender_mobility = rx_packet.get_spectrum_tx_params().tx_phy.get_mobility()
        receiver_mobility = self.mac.get_phy().get_mobility()
        ######################

        distance = sender_mobility.get_distance_from(receiver_mobility.get_position())

        self.packet_list.append(rx_packet)

    def send_beacon(self, event, pbar: tqdm.tqdm | None = None):
        if not self.coordinator:
            BanSSCS.logger.log(
                sim_time=self.env.now,
                msg=f"{self.__class__.__name__}[{self.tx_params.node_id}] This device is not coordinator, ignoring send_beacon request.",
                level=logging.WARNING
            )
            return

        tx_packet = Packet(10)
        tx_params = BanTxParams()
        tx_params.tx_option = BanTxOption.TX_OPTION_NONE
        tx_params.seq_num = None
        tx_params.ban_id = self.tx_params.ban_id
        tx_params.node_id = self.tx_params.node_id
        tx_params.recipient_id = 999  # broadcast id: 999

        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=
            f"{self.__class__.__name__}[{self.tx_params.node_id}] sending becaon signal...",
            newline="\n"
        )

        if pbar is not None:
            pbar.update(1)

        self.mac.set_mac_header(
            packet=tx_packet,
            tx_params=tx_params,
            frame_type=BanFrameType.IEEE_802_15_6_MAC_MANAGEMENT,
            frame_subtype=BanFrameSubType.WBAN_MANAGEMENT_BEACON
        )

        beacon_length = self.beacon_interval * 1000  # ms
        start_offset = 0
        num_slot = 20  # for test. the number of allocation slots

        if self.coordinator:
            '''Q-learning: allocate time slot by strategy'''
            # strategy = self.ENVIRONMENT[self.current_state]
            #
            # BanSSCS.logger.log(
            #     sim_time=self.env.now,
            #     msg=f"{self.__class__.__name__}[{self.tx_params.node_id}] Q-learning: selected strategy is: {strategy}",
            #     level=logging.DEBUG
            # )
            #
            # print(f"{self.__class__.__name__}[{self.tx_params.node_id}] Q-learning: selected strategy is: {strategy}")
            #
            # for node in strategy:
            #     assigned_link = AssignedLinkElement()
            #     assigned_link.allocation_id = node
            #     assigned_link.interval_start = start_offset
            #     assigned_link.interval_end = num_slot
            #     assigned_link.tx_power = self.tx_power
            #     start_offset += (num_slot + 1)
            #
            #     if start_offset > beacon_length:
            #         break
            #
            #     tx_packet.get_frame_body().set_assigned_link_info(assigned_link)

        self.mac.mlme_data_request(tx_packet)

        event = self.env.event()
        event._ok = True
        event.callbacks.append(self.beacon_interval_timeout)  # this method must be called before the send_beacon()
        # event.callbacks.append(self.send_beacon)
        event.callbacks.append(lambda _: self.send_beacon(event=None, pbar=pbar))
        self.env.schedule(event, priority=NORMAL, delay=self.beacon_interval)


    def beacon_interval_timeout(self, event):
        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=f"{self.__class__.__name__}[{self.tx_params.node_id}] beacon signal interval timeout triggered.",
            level=logging.DEBUG
        )


    def send_data(self, tx_packet: Packet):
        tx_params = BanTxParams()
        tx_params.ban_id = self.tx_params.ban_id
        tx_params.node_id = self.tx_params.node_id
        tx_params.recipient_id = self.tx_params.recipient_id

        self.mac.mcps_data_request(self.tx_params, tx_packet)

        event = self.env.event()
        event._ok = True
        event.callbacks.append(
            lambda _: self.send_data(tx_packet=tx_packet)
        )
        self.env.schedule(event, priority=NORMAL, delay=0.1)


    def get_data(self):
        return self.packet_list
