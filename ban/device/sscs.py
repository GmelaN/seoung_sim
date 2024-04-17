import logging
from enum import Enum

import simpy
from dataclasses import dataclass

from simpy.events import NORMAL

from ban.base.helper.mobility_helper import MobilityHelper, MovementInfo
from ban.base.logging.log import SeoungSimLogger
from ban.base.packet import Packet
from ban.base.utils import milliseconds, microseconds
from ban.config.JSONConfig import JSONConfig
from ban.device.mac_header import BanFrameType, BanFrameSubType, AssignedLinkElement

from ban.base.q_learning.q_learning_trainer import QLearningTrainer

from ban.base.tracer import Tracer


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


@dataclass(frozen=True)
class TimeSlotInfo:
    start_time: float
    end_time: float


@dataclass
class BanTxParams:
    ban_id: int | None = None
    node_id: int | None = None
    recipient_id: int | None = None
    seq_num: int | None = None
    tx_option: BanTxOption | None = None
    time_slot_info: int | None = None

@dataclass
class TimeSlotAllocationInfo:
    time_slot_index: int | None = None,
    node_id:int | None = None,
    mobility_phase: MovementInfo | None = None


# Service specific convergence sub-layer (SSCS)
class BanSSCS:
    logger = SeoungSimLogger(logger_name="BAN-SSCS", level=logging.DEBUG)

    NUM_SLOTS = int(JSONConfig.get_config("time_slots"))
    SLOT_DURATION = 1

    def __init__(
            self,
            coordinator: bool = False,
            mobility_helper: MobilityHelper | None = None,
            node_count: int | None = None,
            node_priority: tuple[float, ...] | None = None,
            tracers: list[Tracer] | None = None,
            q_learning_trainer: QLearningTrainer | None = None,
    ):
        self.env: simpy.Environment | None = None
        self.packet_list: list = list()
        self.mac: None = None   # To interact with a MAC layer
        self.node_list: list = list()
        self.tx_params: BanTxParams = BanTxParams()
        self.tx_power: float = 0   # dBm

        if coordinator:
            if q_learning_trainer is not None:
                self.q_learning_trainer = q_learning_trainer
            
            else:
                self.q_learning_trainer = QLearningTrainer(
                    mobility_helper=mobility_helper,
                    sscs=self,
                    movement_phases=mobility_helper.phase_info,
                    node_count=node_count,
                    time_slots=BanSSCS.NUM_SLOTS,
                    tracers=tracers
                )

            self.current_time_slot_index: int = 0

        # self.logger = logging.getLogger("BAN-SSCS")

        # 단위는 초 단위
        self.beacon_interval: float = milliseconds(float(JSONConfig.get_config("beacon_interval")))  # ms

        self.coordinator: bool = coordinator

        # 코디네이터인 경우 페이즈 검출을 위한 MobilityHelper를 붙임
        if self.coordinator:
            self.mobility_helper: MobilityHelper = mobility_helper
            self.movement_info: MovementInfo = self.mobility_helper.phase_info

            # 비콘 주기를 움직임 페이즈와 동기화
            self.beacon_interval = sum(self.movement_info.phase_duration)

            # 노드별 우선순위 리스트
            self.node_priority = node_priority

            self.time_slots: list[TimeSlotAllocationInfo] = []


    def set_env(self, env):
        self.env = env

    def set_mac(self, mac):
        self.mac = mac

    def set_tx_params(self, tx_params):
        self.tx_params = tx_params


    def set_node_list(self, node_id):
        self.node_list.append(node_id)


    def data_confirm(
            self,
            status: BanDataConfirmStatus,
            time_slot_index: int | None = None,
            node_id: int | None = None
    ):
        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=f"{self.__class__.__name__}[{self.mac.get_mac_params().node_id}] "
                + f"transaction result: {status.name}",
            level=logging.INFO,
            newline=" "
        )

        # '''update Q-table'''
        # # 전송이 성공한 경우 AND 코디네이터 디바이스인 경우 AND 데이터를 수신(ACK 메시지)받은 경우
        # # sender_id is not None이 있는 이유는 비콘 신호를 보낸 다음에도 data_confirm이 호출되기 때문
        # if self.coordinator:
        #     print("", end="")
        #
        # if status == BanDataConfirmStatus.IEEE_802_15_6_SUCCESS and self.coordinator and node_id is not None:
        #     BanSSCS.logger.log(
        #         sim_time=self.env.now,
        #         msg=f"{self.__class__.__name__}[{self.mac.get_mac_params().node_id}] updating Q-table",
        #         level=logging.DEBUG
        #     )
        #     # ev = self.env.event()
        #     # ev._ok = True
        #     # ev.callbacks.append(
        #
        #     if time_slot_index is None or node_id is None:
        #         raise Exception("time slot index and sender_id is needed to train.")
        #
        #     self.q_learning_trainer.train(time_slot_index, allocated_node_id=node_id)
        #     # )
        #
        #     # self.env.schedule(ev, priority=NORMAL, delay=0)




    def data_indication(self, rx_packet: Packet):
        # data received
        rx_power = rx_packet.get_spectrum_tx_params().tx_power
        sender_id = rx_packet.get_mac_header().sender_id

        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=f"{self.__class__.__name__}[{self.mac.get_mac_params().node_id}] "
                + f"MCPS-DATA.indication issued. received packet from: {sender_id}",
            level=logging.INFO,
            newline=" "
        )

        self.packet_list.append(rx_packet)


    def send_beacon(self, event):
        if not self.coordinator:
            BanSSCS.logger.log(
                sim_time=self.env.now,
                msg=f"{self.__class__.__name__}[{self.tx_params.node_id}] This device is not coordinator, ignoring send_beacon request.",
                level=logging.WARN
            )
            return

        # 비콘 패킷 설정
        tx_packet = Packet(packet_size=int(JSONConfig.get_config("packet_size")))
        tx_params = BanTxParams()
        tx_params.tx_option = BanTxOption.TX_OPTION_NONE
        tx_params.seq_num = None
        tx_params.ban_id = self.tx_params.ban_id
        tx_params.node_id = self.tx_params.node_id
        tx_params.recipient_id = 999  # broadcast id: 999

        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=
            f"{self.__class__.__name__}[{self.tx_params.node_id}] sending beacon signal...",
            newline="\n"
        )

        self.mac.set_mac_header(
            packet=tx_packet,
            tx_params=tx_params,
            frame_type=BanFrameType.IEEE_802_15_6_MAC_MANAGEMENT,
            frame_subtype=BanFrameSubType.WBAN_MANAGEMENT_BEACON
        )

        # 현재 페이즈의 주기에 맞게 비콘 주기 업데이트
        self.update_beacon_interval()

        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=
            f"{self.__class__.__name__}[{self.tx_params.node_id}] beacon interval is: {self.beacon_interval}, "
            f"current movement phase is: "
            f"{self.mobility_helper.phase_info.phase_duration[self.mobility_helper.current_phase.value]}",
            level=logging.INFO
        )

        # beacon_length는 ms 단위 -> beacon_interval은 s 단위이므로 1000을 곱함
        beacon_length = self.beacon_interval * 1000  # ms
        # TODO: 비콘 interval 기간과 비콘 신호 길이 분리


        start_offset = 0
        num_slot = BanSSCS.NUM_SLOTS  # for test. the number of allocation slots

        '''Q-learning: allocate time slot by strategy'''
        # [node, node, ..., node], slots[time_slot_index]: node_id
        slots = self.q_learning_trainer.get_time_slots(self.q_learning_trainer.detect_movement_phase())

        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=
            f"{self.__class__.__name__}[{self.tx_params.node_id}] time slot configuration is: {slots}",
            level=logging.CRITICAL
        )

        for time_slot_index, node_id in enumerate(slots):
            if node_id != -1:
                assigned_link = AssignedLinkElement()
                assigned_link.allocation_id = node_id
                assigned_link.interval_start = start_offset
                assigned_link.interval_end = num_slot
                assigned_link.tx_power = self.tx_power
                assigned_link.time_slot_index = time_slot_index

                tx_packet.get_frame_body().set_assigned_link_info(assigned_link)

            BanSSCS.logger.log(
                sim_time=self.env.now,
                msg=f"configuring time slots...{time_slot_index}, node id: {node_id}, PHASE: {self.mobility_helper.current_phase.name}",
                level=logging.DEBUG
            )

            self.time_slots.append(
                TimeSlotAllocationInfo(
                    time_slot_index=time_slot_index,
                    node_id=node_id,
                    mobility_phase=self.mobility_helper.current_phase
                )
            )
            start_offset += (num_slot + BanSSCS.SLOT_DURATION)

            if start_offset > beacon_length:
                break

        self.beacon_start_time = self.env.now

        self.mac.mlme_data_request(tx_packet)

        event = self.env.event()
        event._ok = True
        event.callbacks.append(self.beacon_interval_timeout)  # this method must be called before the send_beacon()
        event.callbacks.append(self.send_beacon)
        self.env.schedule(event, priority=NORMAL, delay=self.beacon_interval)


    def beacon_interval_timeout(self, event):
        self.q_learning_trainer.print_throughput()
        # self.update_q_table()

        while self.time_slots:
            time_slot: TimeSlotAllocationInfo = self.time_slots.pop(0)
            time_slot_index, node_id, mobility_phase = time_slot.time_slot_index, time_slot.node_id, time_slot.mobility_phase

            BanSSCS.logger.log(
                sim_time=self.env.now,
                msg=f"{self.__class__.__name__}[{self.mac.get_mac_params().node_id}] "
                    + f"updating Q-table, time slot:{time_slot_index}, node ID: {node_id}, phase: {mobility_phase}",
                level=logging.DEBUG,
            )

            self.q_learning_trainer.train(time_slot_index=time_slot_index, allocated_node_id=node_id, mobility_phase=mobility_phase)


    def send_data(self, tx_packet: Packet):
        tx_params = BanTxParams()
        tx_params.ban_id = self.tx_params.ban_id
        tx_params.node_id = self.tx_params.node_id
        tx_params.recipient_id = self.tx_params.recipient_id

        self.mac.mcps_data_request(self.tx_params, tx_packet)

        # 전송 대기열에 오른 패킷 카운트
        self.mac.get_tracer().requested_packet_count += 1
        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=f"{self.__class__.__name__}[{self.mac.get_mac_params().node_id}] "
                + f"requested_packet_count increased, now {self.mac.get_tracer().requested_packet_count}",
            level=logging.DEBUG,
        )

        event = self.env.event()
        event._ok = True
        event.callbacks.append(
            lambda _: self.send_data(tx_packet=tx_packet)
        )
        self.env.schedule(event, priority=NORMAL, delay=0.1)


    def get_data(self):
        return self.packet_list


    def update_beacon_interval(self):
        # 현재 페이즈의 길이를 구해 비콘 주기에 대입(s -> s)
        self.beacon_interval = self.movement_info.phase_duration[self.mobility_helper.current_phase.value]


    def get_throughput(self):
        tracer: Tracer = self.mac.get_tracer()
        return tracer.get_throughput()


    def get_priority(self, node_id):
        return self.node_priority[node_id]

    def reset_throughput(self):
        tracer: Tracer = self.mac.get_tracer()
        tracer.reset()


    def print_q_table(self, env):
        if self.q_learning_trainer.off:
            return

        q_table = self.q_learning_trainer.q_table

        actions_string = ""
        if bool(JSONConfig.get_config("use_unallocated")):
            for i in range(len(self.q_learning_trainer.action_space) - 1):
                actions_string += (f"ACTION_{i}" + '\t')

            actions_string += (f"ACTION_UALLOC" + '\t')
        
        else:
            for i in range(len(self.q_learning_trainer.action_space)):
                actions_string += (f"ACTION_{i}" + '\t')


        string = f"Q_TABLE\n[MOVEMENT_PHASE\tTIME_SLOT_INDEX]\t{actions_string}\n"
        for key in sorted(q_table.keys(), key=lambda x: x.phase.name):
            values_string = ""
            for i in q_table[key]:
                values_string += (f"{i:.3f}" + '\t\t')

            string += f"{key.phase.name}\t\tSLOT_{key.slot}\t\t\t{values_string}\n"

        BanSSCS.logger.log(
            sim_time=self.env.now,
            msg=string,
            level=logging.FATAL
        )