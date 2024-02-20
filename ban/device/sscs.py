import logging
from enum import Enum
import sys

import simpy
import tqdm
from dataclasses import dataclass

from ban.base.dqn.dqn_trainer import DQNTrainer
from ban.base.logging.log import SeoungSimLogger
from ban.base.packet import Packet
from ban.base.utils import milliseconds
from ban.device.mac_header import BanFrameType, BanFrameSubType, AssignedLinkElement

from typing import List

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

    ACTION_SET = [- 25, -24, -23, -22, -21, -20, -18, -16, -14, -12, -10, -8, -6, -4, -2]    # dBm

    def __init__(self):
        self.__env = None
        self.__packet_list = list()
        self.__mac = None   # To interact with a MAC layer
        self.__node_list = list()
        self.__tx_params = BanTxParams()
        self.__beacon_interval = milliseconds(255)  # ms
        self.__tx_power = 0   # dBm

        # DQN feature
        self.dqn_status_info: List[DqnStatusInfo] = list()
        self.__dqn_trainer = None  # To interact with a dqn_trainer
        self.use_dqn_features = False

        self.__logger = logging.getLogger("BAN-SSCS")

    def set_env(self, env):
        self.__env = env

    def get_env(self) -> simpy.Environment:
        return self.__env

    def set_dqn_trainer(self, dqn_trainer: DQNTrainer):
        self.__dqn_trainer = dqn_trainer
        dqn_trainer.env = self.get_env()

    def get_dqn_trainer(self) -> DQNTrainer:
        if self.__dqn_trainer is None:
            raise Exception("DQN trainer is not defined.")
        return self.__dqn_trainer

    def set_mac(self, mac):
        self.__mac = mac

    def get_mac(self):
        return self.__mac

    def set_tx_params(self, tx_params):
        self.__tx_params = tx_params

    def set_node_list(self, node_id):
        self.__node_list.append(node_id)

        if self.use_dqn_features:
            self.dqn_status_info.append(self.init_dqn_status_info(node_id))

    def use_dqn(self):
        self.use_dqn_features = True
        return

    def init_dqn_status_info(self, node_id) -> DqnStatusInfo | None:
        if not self.use_dqn_features:
            BanSSCS.logger.log(
                sim_time=self.get_env().now,
                msg=f"{self.__class__.__name__}[{self.get_mac().get_mac_params().node_id}] "
                    + f"init_dqn_status_info: use_dqn_features is False. ignoring."
                    + f"if you want to use DQN features, please call use_dqn() first.",
                level=logging.WARN
            )
            return None

        new_dqn_status = DqnStatusInfo()
        new_dqn_status.node_id = node_id
        new_dqn_status.current_state = (-80, 0)   # initial state is (Rx power, distance)
        new_dqn_status.current_action = 0
        new_dqn_status.reward = 0
        new_dqn_status.next_state = 0
        new_dqn_status.done = True
        new_dqn_status.steps = 0
        return new_dqn_status

    def data_confirm(self, status: BanDataConfirmStatus):
        BanSSCS.logger.log(
            sim_time=self.get_env().now,
            msg=f"{self.__class__.__name__}[{self.get_mac().get_mac_params().node_id}] "
                + f"MAC reported transaction result: {status.name}",
            level=logging.INFO,
        )

    def data_indication(self, rx_packet: Packet):
        # data received
        rx_power = rx_packet.get_spectrum_tx_params().tx_power
        sender_id = rx_packet.get_mac_header().sender_id

        if self.use_dqn_features:
            for dqn_status in self.dqn_status_info:
                if dqn_status.node_id == sender_id:
                    # calculate the reward value
                    if dqn_status.current_action == 0:      # -25 dBm
                        dqn_status.reward += 10
                    elif dqn_status.current_action == 1:    # -24 dBm
                        dqn_status.reward += 9.5
                    elif dqn_status.current_action == 2:    # -23 dBm
                        dqn_status.reward += 9
                    elif dqn_status.current_action == 3:    # -22 dBm
                        dqn_status.reward += 8.5
                    elif dqn_status.current_action == 4:    # -21 dBm
                        dqn_status.reward += 8
                    elif dqn_status.current_action == 5:    # -20 dBm
                        dqn_status.reward += 7.5
                    elif dqn_status.current_action == 6:    # -18 dBm
                        dqn_status.reward += 7
                    elif dqn_status.current_action == 7:    # -16 dBm
                        dqn_status.reward += 6.5
                    elif dqn_status.current_action == 8:    # -14 dBm
                        dqn_status.reward += 6
                    elif dqn_status.current_action == 9:    # -12 dBm
                        dqn_status.reward += 5.5
                    elif dqn_status.current_action == 10:    # -10 dBm
                        dqn_status.reward += 5
                    elif dqn_status.current_action == 11:    # -8 dBm
                        dqn_status.reward += 4
                    elif dqn_status.current_action == 12:    # -6 dBm
                        dqn_status.reward += 3
                    elif dqn_status.current_action == 13:    # -4 dBm
                        dqn_status.reward += 2
                    elif dqn_status.current_action == 14:    # -2 dBm
                        dqn_status.reward += 1
                    else:
                        print('Invalid action', file=sys.stderr)

                    sender_mobility = rx_packet.get_spectrum_tx_params().tx_phy.get_mobility()
                    receiver_mobility = self.__mac.get_phy().get_mobility()

                    distance = sender_mobility.get_distance_from(receiver_mobility.get_position())

                    dqn_status.next_state = (rx_power, distance)
                    dqn_status.done = False  # allocate Tx power to this node and successfully receive the data packet

                    result = self.get_dqn_trainer().set_observation(
                        dqn_status.current_state,
                        dqn_status.current_action,
                        dqn_status.next_state,
                        dqn_status.reward,
                        dqn_status.steps,
                        dqn_status.done
                    )

                    # start new episode
                    if result is True:
                        dqn_status.current_state = (-80, 0)  # initial state is (Rx power, distance)
                        dqn_status.current_action = 0
                        dqn_status.reward = 0
                        dqn_status.next_state = 0
                        dqn_status.done = True
                        dqn_status.steps = 0
                    else:
                        dqn_status.current_state = dqn_status.next_state
                        dqn_status.steps += 1

                    break

        ##### added code #####
        sender_mobility = rx_packet.get_spectrum_tx_params().tx_phy.get_mobility()
        receiver_mobility = self.__mac.get_phy().get_mobility()
        ######################

        distance = sender_mobility.get_distance_from(receiver_mobility.get_position())

        self.__packet_list.append(rx_packet)

    def send_beacon(self, event, pbar: tqdm.tqdm | None = None):
        tx_packet = Packet(10)
        tx_params = BanTxParams()
        tx_params.tx_option = BanTxOption.TX_OPTION_NONE
        tx_params.seq_num = None
        tx_params.ban_id = self.__tx_params.ban_id
        tx_params.node_id = self.__tx_params.node_id
        tx_params.recipient_id = 999  # broadcast id: 999

        # tx_packet.set_mac_header(
        #     BanFrameType.IEEE_802_15_6_MAC_MANAGEMENT,
        #     BanFrameSubType.WBAN_MANAGEMENT_BEACON,
        #     tx_params
        # )

        BanSSCS.logger.log(
            sim_time=self.get_env().now,
            msg=
            f"{self.__class__.__name__}[{self.__tx_params.node_id}] sending becaon signal...",
            newline="\n"
        )

        if pbar is not None:
            pbar.update(1)

        self.get_mac().set_mac_header(
            packet=tx_packet,
            tx_params=tx_params,
            frame_type=BanFrameType.IEEE_802_15_6_MAC_MANAGEMENT,
            frame_subtype=BanFrameSubType.WBAN_MANAGEMENT_BEACON
        )

        beacon_length = self.__beacon_interval * 1000  # ms
        start_offset = 0
        num_slot = 20  # for test. the number of allocation slots

        if self.use_dqn_features:
            for n_index in self.__node_list:
                # get the action from DQN trainer
                for dqn_status in self.dqn_status_info:
                    if n_index == dqn_status.node_id:
                        action = self.get_dqn_trainer().get_action(dqn_status.current_state)
                        dqn_status.current_action = action
                        dqn_status.done = True
                        self.__tx_power = BanSSCS.ACTION_SET[action]
                        break

        for n_index in self.__node_list:
            assigned_link = AssignedLinkElement()
            assigned_link.allocation_id = n_index
            assigned_link.interval_start = start_offset
            assigned_link.interval_end = num_slot
            assigned_link.tx_power = self.__tx_power  # get the tx power (action) from the DQN
            start_offset += (num_slot + 1)

            if start_offset > beacon_length:
                break

            tx_packet.get_frame_body().set_assigned_link_info(assigned_link)

        self.get_mac().mlme_data_request(tx_packet)

        event = self.get_env().event()
        event._ok = True
        event.callbacks.append(self.beacon_interval_timeout)  # this method must be called before the send_beacon()
        # event.callbacks.append(self.send_beacon)
        event.callbacks.append(lambda _: self.send_beacon(event=None, pbar=pbar))
        self.get_env().schedule(event, priority=0, delay=self.__beacon_interval)



    def beacon_interval_timeout(self, event):
        BanSSCS.logger.log(
            sim_time=self.get_env().now,
            msg=f"{self.__class__.__name__}[{self.__tx_params.node_id}] beacon signal interval timeout triggered.",
            level=logging.DEBUG
        )
        if self.use_dqn_features:
            # Calculate the next_state, reward, done
            for dqn_status in self.dqn_status_info:
                # if the previous resource allocation (tx power) was failed
                if dqn_status.done is True:
                    dqn_status.next_state = (-85, -1)  # Rx power beyond the rx_sensitivity
                    dqn_status.reward = -10
                    result = self.get_dqn_trainer().set_observation(
                        dqn_status.current_state, dqn_status.current_action,
                        dqn_status.next_state, dqn_status.reward, dqn_status.steps,
                        dqn_status.done
                    )

                    # start new episode
                    if result is True:
                        dqn_status.current_state = (-80, 0)  # initial state is (Rx power, distance)
                        dqn_status.current_action = 0
                        dqn_status.reward = 0
                        dqn_status.next_state = 0
                        dqn_status.done = True
                        dqn_status.steps = 0


    def send_data(self, tx_packet: Packet):
        # print("send_data: ", tx_packet.get_spectrum_tx_params().tx_power)
        tx_params = BanTxParams()
        tx_params.ban_id = self.__tx_params.ban_id
        tx_params.node_id = self.__tx_params.node_id
        tx_params.recipient_id = self.__tx_params.recipient_id

        self.get_mac().mcps_data_request(self.__tx_params, tx_packet)

        event = self.get_env().event()
        event._ok = True
        event.callbacks.append(
            lambda _: self.send_data(tx_packet=tx_packet)
        )
        self.get_env().schedule(event, priority=0, delay=0.1)

    def get_data(self):
        return self.__packet_list
