import logging
import math
from queue import Queue
from enum import Enum

import simpy
import tqdm
from simpy.core import SimTime
from simpy.events import NORMAL

from ban.base.logging.log import SeoungSimLogger
from ban.base.packet import Packet
from ban.base.tracer import Tracer
from ban.base.utils import microseconds
from ban.base.channel.csma_ca import CsmaCa
from ban.config.JSONConfig import JSONConfig
from ban.device.mac_header import BanFrameType, BanFrameSubType, BanMacHeader, Beacon, IAck, Data, AssignedLinkElement
from ban.device.phy import BanPhyPibAttributes, BanPhy, BanPibAttributeIdentifier, BanPhyTRxState
from ban.device.sscs import BanTxParams, BanSSCS, BanTxOption, BanDataConfirmStatus
from ban.device.mac_header import BanRecipientType


class BanMacState(Enum):
    MAC_IDLE = 0
    MAC_CSMA = 1
    MAC_SENDING = 2
    MAC_ACK_PENDING = 3
    CHANNEL_ACCESS_FAILURE = 4
    CHANNEL_IDLE = 5
    SET_PHY_TX_ON = 6


class BanMac:
    # MAC params specified in IEEE 802.15.6 standard 2012, 149p.
    pAllocationSlotMin = 500            # us
    pAllocationSlotResolution = 500     # us
    pSIFS = 75                          # us
    pMIFS = 20                          # us
    pExtraIFS = 10                      # us
    mClockResolution = 4                # us
    # A slot length can be calculated as pAllocationSlotMin + (L) * pAllocationSlotResolution = 1000 us (1 ms)
    mAllocationSlotLength = 1           # ms

    logger = SeoungSimLogger(logger_name="BAN-MAC", level=logging.DEBUG)

    def __init__(self):
        self.env = None
        self.sscs = None
        self.phy = None
        self.tx_queue = Queue()                    # packet queue
        self.tx_packet: Packet | None = None       # a packet to be sent
        self.rx_packet: Packet | None = None       # a packet received now
        self.mac_state = BanMacState.MAC_IDLE
        self.mac_rx_on_when_idle = True
        self.mac_params = BanTxParams()
        self.tracer = Tracer()
        self.csma_ca = None

        self.ack_wait_time = None
        self.seq_num = 0
        self.prev_tx_status = False
        self.alloc_start_time = 0
        self.alloc_end_time = 0
        self.beacon_rx_time = 0
        self.tx_power = 0
        self.initial_energy = 1

        self.time_slot_index = None
        self.packet_sent = False


    def set_env(self, env: simpy.Environment):
        self.env = env

    def get_env(self) -> simpy.Environment:
        return self.env

    def set_phy(self, phy: BanPhy):
        self.phy = phy

    def get_phy(self) -> BanPhy:
        return self.phy

    def get_mac_params(self) -> BanTxParams:
        return self.mac_params

    def set_sscs(self, sscs: BanSSCS):
        self.sscs = sscs

    def get_sscs(self) -> BanSSCS:
        return self.sscs

    def set_csma_ca(self, csma_ca: CsmaCa):
        self.csma_ca = csma_ca

    def set_mac_header(
            self,
            packet: Packet,
            frame_type: BanFrameType,
            frame_subtype: BanFrameSubType,
            tx_params: BanTxParams
    ):
        assert frame_type is not None
        assert frame_subtype is not None
        assert tx_params is not None
        assert tx_params.node_id is not None and tx_params.ban_id is not None and tx_params.recipient_id is not None


        packet.get_mac_header().set_tx_params(
            tx_params.ban_id,
            tx_params.node_id,
            tx_params.recipient_id,
            self.time_slot_index if self.time_slot_index is not None else None
        )
        packet.get_mac_header().set_frame_control(frame_type, frame_subtype, tx_params.tx_option, tx_params.seq_num)

        if frame_subtype == BanFrameSubType.WBAN_MANAGEMENT_BEACON:
            packet.set_frame_body(Beacon())
        elif frame_subtype == BanFrameSubType.WBAN_CONTROL_IACK:
            packet.set_frame_body(IAck())
        elif frame_subtype == BanFrameSubType.WBAN_DATA_UP0:
            packet.set_frame_body(Data(0))
        elif frame_subtype == BanFrameSubType.WBAN_DATA_UP1:
            packet.set_frame_body(Data(1))
        elif frame_subtype == BanFrameSubType.WBAN_DATA_UP2:
            packet.set_frame_body(Data(2))
        elif frame_subtype == BanFrameSubType.WBAN_DATA_UP3:
            packet.set_frame_body(Data(3))
        elif frame_subtype == BanFrameSubType.WBAN_DATA_UP4:
            packet.set_frame_body(Data(4))
        elif frame_subtype == BanFrameSubType.WBAN_DATA_UP5:
            packet.set_frame_body(Data(5))
        elif frame_subtype == BanFrameSubType.WBAN_DATA_UP6:
            packet.set_frame_body(Data(6))
        elif frame_subtype == BanFrameSubType.WBAN_DATA_UP7:
            packet.set_frame_body(Data(7))
        else:
            packet.set_frame_body(None)
            print('frame initialization error (invalid frame subtype)')

    def get_tracer(self) -> Tracer:
        return self.tracer

    def set_tracer(self, tracer: Tracer):
        self.tracer = tracer

    def set_mac_params(self, mac_params):
        self.mac_params = mac_params


    def do_initialize(self):
        self.seq_num = 0
        self.alloc_start_time = 0
        self.alloc_end_time = 0
        self.beacon_rx_time = 0
        self.tx_power = 0  # dBm
        self.initial_energy = 1  # watt
        self.tracer.set_env(self.env)
        self.tracer.set_initial_energy(self.initial_energy)

        pib_attribute = BanPhyPibAttributes()
        pib_attribute.phy_tx_power = self.tx_power
        pib_attribute.phy_cca_mode = 1
        self.phy.set_attribute_request(BanPibAttributeIdentifier.PHY_TRANSMIT_POWER, pib_attribute)
        self.phy.set_attribute_request(BanPibAttributeIdentifier.PHY_CCA_MODE, pib_attribute)

        if self.mac_rx_on_when_idle is True:
            self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)
        else:
            self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF)

        BanMac.logger.log(
            sim_time=self.get_env().now,
            msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] do_initialize: initialized.",
            level=logging.INFO,
            newline="\n"
        )


    def mlme_data_request(self, tx_packet: Packet):
        self.packet_sent = False
        # Push the packet into the Tx queue
        self.tx_queue.put_nowait(tx_packet)

        event = self.env.event()
        event._ok = True
        event.callbacks.append(self.check_queue)
        self.env.schedule(event, priority=0, delay=0)

        # recipient_id = tx_packet.get_mac_header().recipient_id
        # broadcast = "BROADCAST"

        # BanMac.logger.log(
        #     sim_time=self.get_env().now,
        #     msg=
        #     f"{self.__class__.__name__}[{self.mac_params.node_id}] mlme_data_request: processing MLME-DATA.request, "
        #     + f"packet size: {tx_packet.get_size()}, "
        #     + f"from : {tx_packet.get_mac_header().sender_id}, "
        #     + f"to: {broadcast if recipient_id == BanRecipientType.IEEE_802_15_6_BROADCAST.value else recipient_id}."
        # )


    def mcps_data_request(self, tx_params: BanTxParams, tx_packet: Packet):
        tx_params.tx_option = BanTxOption.TX_OPTION_ACK
        tx_params.seq_num = self.seq_num
        self.seq_num += 1

        # tx_packet.set_mac_header(
        #     BanFrameType.IEEE_802_15_6_MAC_DATA,
        #     BanFrameSubType.WBAN_DATA_UP0,
        #     tx_params
        # )

        tx_params.time_slot_info = self.time_slot_index

        self.set_mac_header(
            packet=tx_packet,
            tx_params=tx_params,
            frame_type=BanFrameType.IEEE_802_15_6_MAC_DATA,
            frame_subtype=BanFrameSubType.WBAN_DATA_UP0
        )

        recipient_id = tx_packet.get_mac_header().recipient_id

        assert recipient_id is not None

        broadcast = "BROADCAST"

        BanMac.logger.log(
            sim_time=self.get_env().now,
            msg=
            f"{self.__class__.__name__}[{self.mac_params.node_id}] MCPS-DATA.request issued: "
            + f"time slot: {tx_packet.get_mac_header().time_slot_index}, "
            + f"from : {self.mac_params.node_id}, "
            + f"to: {broadcast if recipient_id == BanRecipientType.IEEE_802_15_6_BROADCAST.value else recipient_id}.",
            level=logging.DEBUG
        )

        # Push the packet into the Tx queue
        self.tx_queue.put_nowait(tx_packet)
        # self.check_queue(self.get_env())


    # Callback function (called from PHY)
    def pd_data_confirm(self, trx_state: BanPhyTRxState):
        self.packet_sent = True # 한 슬롯당 한번만 데이터를 전송

        if trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_SUCCESS:
            # 전송하기로 했던 패킷이 정상적으로 전송된 경우
            # 전송한 패킷의 헤더를 까서, ACK을 받아야 하는 전송인지 확인하고, ACK를 받기 위해 수신 대기 모드로 들어감

            tx_header = self.tx_packet.get_mac_header()           # 보냈던 패킷의 헤더

            frame_type = tx_header.get_frame_control().frame_type
            ack_policy = tx_header.get_frame_control().ack_policy

            if frame_type == BanFrameType.IEEE_802_15_6_MAC_DATA and ack_policy == BanTxOption.TX_OPTION_ACK:
                # 방금 데이터를 보냈고, 추가로 ACK를 보내야 하는 경우
                # ACK 대기 모드로 돌입
                self.set_mac_state(BanMacState.MAC_ACK_PENDING)

                # ACK 대기 시간 설정
                # ack_wait_time = self.get_ack_wait_duration() * 1000 * 1000 / self.get_phy().get_data_or_symbol_rate(is_data=False)
                # self.ack_wait_time = microseconds(ack_wait_time)
                # self.ack_wait_time += self.get_phy().calc_tx_time(self.tx_packet) * 2
                # TODO: ACK 대기 시간 검증
                # self.ack_wait_time += self.get_phy().aTurnaroundTime * 2

                self.ack_wait_time = microseconds(
                    self.get_ack_wait_duration() * 1000 * 1000 / self.get_phy().get_data_or_symbol_rate(is_data=False)
                )

                self.ack_wait_time += (self.get_phy().calc_tx_time(self.tx_packet) * 2)
                self.ack_wait_time += microseconds(self.get_phy().aTurnaroundTime) * 2 * 2

                # ACK timeout 이벤트 등록
                BanMac.logger.log(
                    sim_time=self.get_env().now,
                    msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] packet sent, waiting ACK, ACK timeout at: {self.get_env().now + self.ack_wait_time:.10f}",
                    level=logging.DEBUG
                )

                event = self.env.event()
                event._ok = True
                event.callbacks.append(self.ack_wait_timeout)
                self.env.schedule(event, priority=0, delay=self.ack_wait_time)

            else:
                # ACK 수신 대기를 할 필요가 없는 경우 - 비콘 신호 보낸 경우, ACK 확인 메시지 보낸 경우

                mac_header: BanMacHeader = self.tx_packet.get_mac_header()

                # 한 노드로부터 데이터를 수신했고, 이 코디네이터에서 ACK 메시지를 성공적으로 보낸 경우
                if mac_header.get_frame_control().frame_subtype == BanFrameSubType.WBAN_CONTROL_IACK:
                    self.sscs.data_confirm(
                        BanDataConfirmStatus.IEEE_802_15_6_SUCCESS,
                        node_id=mac_header.recipient_id,
                        time_slot_index=mac_header.time_slot_index,
                    )

                # 기타(비콘 신호 등등)
                else:
                    self.sscs.data_confirm(BanDataConfirmStatus.IEEE_802_15_6_SUCCESS)



                self.tx_packet = None                                                 # TX 패킷 초기화
                self.change_mac_state(BanMacState.MAC_IDLE)                           # MAC은 IDLE 모드
                if self.mac_rx_on_when_idle is True:                                  # 'IDLE시 RX 대기 모드'인 경우
                    self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)
                else:                                                                   # 'IDLE시 TRX 끄기 모드'인 경우
                    self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF)

        elif trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_UNSPECIFIED:
            # PHY가 정상적인 상태에 있지 않음
            BanMac.logger.log(
                sim_time=self.get_env().now,
                msg=f"PHY reported abnormal state: {trx_state.name}",
                level=logging.WARN
            )

        else:
            # 기타 예외 상황
            BanMac.logger.log(
                sim_time=self.get_env().now,
                level=logging.ERROR,
                msg=f"PHY is not in the correct state for data transmission."
            )
            raise Exception("PHY is not in the correct state for data transmission.")


    # Callback function (called from PHY)
    def pd_data_indication(self, rx_packet: Packet):
        broadcast = "BROADCAST"
        recipient_id = rx_packet.get_mac_header().recipient_id
        sender_id = rx_packet.get_mac_header().sender_id

        # BanMac.logger.log(
        #     sim_time=self.get_env().now,
        #     msg=
        #     f"{self.__class__.__name__}[{self.mac_params.node_id}] pd_data_indication: processing PD-DATA.indication,"
        #     + f"time slot: {self.time_slot_index} "
        #     + f"type: {rx_packet.get_mac_header().get_frame_control().frame_type.name}, "
        #     + f"from: {rx_packet.get_mac_header().sender_id}, "
        #     + f"to: {broadcast if recipient_id == BanRecipientType.IEEE_802_15_6_BROADCAST.value else recipient_id}.",
        #     level=logging.DEBUG
        # )

        # BanMac.logger.log(
        #     sim_time=self.get_env().now,
        #     msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] packet received. from: {sender_id}, "
        #         + f"type: {rx_packet.get_mac_header().get_frame_control().frame_type.name}",
        #     level=logging.DEBUG
        # )

        rx_header: BanMacHeader = rx_packet.get_mac_header()
        accept_frame: bool = True                               # 수신된 패킷의 승인 여부

        # * accept_frame = false인 경우 무조건 return 때리면 어떤가

        # 수신된 패킷의 mac 헤더를 뜯어서 내가 무슨 처리를 해야 하는지 알아 보자.

        # 1. 자신이 자신에게 보낸 패킷인 경우 무시
        if rx_header.sender_id == self.mac_params.node_id:
            accept_frame = False

        # 2. 나에게 보내지 않은 패킷인 경우 무시
        elif rx_header.ban_id != self.mac_params.ban_id:
            accept_frame = False

        # 3. broadcast id: 999인 경우
        if (rx_header.recipient_id != BanRecipientType.IEEE_802_15_6_BROADCAST.value
                and rx_header.recipient_id != self.mac_params.node_id):
            accept_frame = False


        if accept_frame is True:                            # 이제 수신된 패킷을 처리해보자
            # Beacon received (note: we consider the management-type frame is a beacon frame)
            # Note: broadcast id is 999

            rx_frame_type = rx_header.get_frame_control().frame_type
            rx_recipient_id = rx_header.recipient_id


            # 1. 비콘 신호인 경우
            if (rx_frame_type == BanFrameType.IEEE_802_15_6_MAC_MANAGEMENT
                    and rx_recipient_id == BanRecipientType.IEEE_802_15_6_BROADCAST.value):
                self.packet_sent = False # 새 비콘 신호 수신 -> 패킷 전송 여부 플래그 초기화
                # 수신한 비콘 신호의 남은 할당 시간 계산
                self.beacon_rx_time = self.get_env().now
                assigned_link: AssignedLinkElement = rx_packet.get_frame_body().get_assigned_link_info(self.mac_params.node_id)

                BanMac.logger.log(
                    sim_time=self.get_env().now,
                    msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] accept this beacon signal.",
                    newline=' ',
                    level=logging.INFO
                )

                # 비콘 신호와 연결이 제대로 된 경우
                if assigned_link is not None:
                    # PIB attribute 업데이트(링크 품질)
                    pib_attribute = BanPhyPibAttributes()
                    pib_attribute.phy_tx_power = assigned_link.tx_power
                    self.get_phy().set_attribute_request(BanPibAttributeIdentifier.PHY_TRANSMIT_POWER, pib_attribute)

                    # 비콘 신호와 동기화
                    self.alloc_start_time = assigned_link.interval_start
                    self.alloc_end_time = assigned_link.interval_end

                    # TDMA 슬롯 기간 계산
                    slot_duration = (
                            self.mAllocationSlotLength * self.pAllocationSlotResolution
                            + self.pAllocationSlotMin
                    )

                    tx_start_time = microseconds(self.alloc_start_time * slot_duration) + microseconds(self.pSIFS)
                    tx_timeout = (
                            microseconds(self.alloc_start_time * slot_duration)
                            + microseconds(self.alloc_end_time * slot_duration)
                    )

                    self.alloc_start_time = tx_start_time
                    self.alloc_end_time = tx_timeout
                    self.time_slot_index = assigned_link.time_slot_index


                    BanMac.logger.log(
                        sim_time=self.get_env().now,
                        msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] "
                            f"time slot: {self.time_slot_index} "
                            f"alloc start: {self.alloc_start_time + + self.env.now:.6f}, "
                            f"alloc end: {self.alloc_end_time + + self.env.now:.6f}"
                            f"!!! {self.alloc_start_time}",
                        level=logging.INFO
                    )

                    event = self.env.event()
                    event._ok = True
                    event.callbacks.append(self.check_queue)

                    self.env.schedule(event, priority=0, delay=self.alloc_start_time)
                else:
                    BanMac.logger.log(
                        sim_time=self.env.now,
                        msg=f"{self.__class__.__name__}[{self.get_mac_params().node_id}] "
                            + f"dropping beacon signal because assigned_link is None.",
                        level=logging.WARN
                    )

            # for further processing the received control or data-type frame
            self.rx_packet = rx_packet
            mac_state = self.mac_state
            rx_ack_policy = rx_header.get_frame_control().ack_policy

            # 2. 데이터 신호인 경우
            if rx_frame_type == BanFrameType.IEEE_802_15_6_MAC_DATA:
                # if it is a data frame, push it up the stack
                self.get_sscs().data_indication(self.rx_packet)

                # if this is a data or management-type frame, which is not a broadcast,
                # generate and send an ACK frame.
                # if the MAC state is MAC_ACK_PENDING, then we drop the packet that just sent before (data packet)


                # ACK PENDING 상태인데 ACK가 아닌 데이터를 받은 경우: NO_ACK
                if rx_ack_policy == BanTxOption.TX_OPTION_ACK and mac_state == BanMacState.MAC_ACK_PENDING:
                    BanMac.logger.log(
                        sim_time=self.get_env().now,
                        msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] NO ACK received.",
                        level=logging.WARN
                    )
                    self.tx_packet = None
                    self.set_mac_state(BanMacState.MAC_IDLE)
                    self.get_sscs().data_confirm(BanDataConfirmStatus.IEEE_802_15_6_NO_ACK)

                # ACK PENDING 상태가 아닐 때 데이터를 받은 경우: ACK 보냄
                if rx_ack_policy == BanTxOption.TX_OPTION_ACK:
                    self.change_mac_state(BanMacState.MAC_IDLE)
                    event = self.env.event()
                    event._ok = True
                    event.callbacks.append(self.send_ack)
                    self.env.schedule(event, priority=0, delay=(self.pSIFS * 0.000001))

            # 3. 제어 신호이며 ACK_PENDING 상태인 경우
            elif rx_frame_type == BanFrameType.IEEE_802_15_6_MAC_CONTROL and mac_state == BanMacState.MAC_ACK_PENDING:
                # if self.tx_packet is None:
                #     raise Exception("packet is none")

                # if it is an ACK with the expected sequence number,
                # finish the transmission and notify the upper layer
                tx_header = self.tx_packet.get_mac_header()

                if rx_header.get_frame_control().sequence_number == tx_header.get_frame_control().sequence_number:
                    BanMac.logger.log(
                        sim_time=self.get_env().now,
                        msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] received ACK message.",
                        level=logging.DEBUG
                    )
                    # if the packet that just sent before is a data frame
                    if tx_header.get_frame_control().frame_type == BanFrameType.IEEE_802_15_6_MAC_DATA:
                        # update trace info
                        self.get_tracer().add_success_tx_packet(self.tx_packet)

                        self.sscs.data_confirm(BanDataConfirmStatus.IEEE_802_15_6_SUCCESS)

                        # Prepare the next transmission
                        self.tx_packet = None
                        self.prev_tx_status = True    # mark the current Tx result as a success
                        self.change_mac_state(BanMacState.MAC_IDLE)
                        if self.mac_rx_on_when_idle is True:
                            self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)
                        else:
                            self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF)

                        event = self.env.event()
                        event._ok = True
                        event.callbacks.append(self.check_queue)
                        self.get_env().schedule(event, priority=NORMAL, delay=self.pSIFS * 0.000001)
                    else:
                        pass
                else:
                    BanMac.logger.log(
                        sim_time=self.get_env().now,
                        msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] ERROR PROCESSING RX PACKET: COUNTER ERROR",
                        level=logging.FATAL
                    )
                    self.prev_tx_status = False   # mark the current Tx result as a fail
                    self.sscs.data_confirm(BanDataConfirmStatus.IEEE_802_15_6_COUNTER_ERROR)

        else:
            # accept_frame = False -> return
            return
            # print("error")


    # Callback function (called from PHY)
    def set_trx_state_confirm(self, status: BanPhyTRxState):
        if self.mac_state == BanMacState.MAC_SENDING and status == BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON:
            if self.tx_packet is None:
                raise Exception("NO TX packet.")

            # We give up the current transmission according to the three conditions below
            # Cond 1) if the current time is not in the boundary of allocation intervals
            # Cond 2) if the expected Tx time is over the remain allocation intervals
            # Cond 3) if the remain allocation interval is lower than the minimum time slot unit

            slot_duration = self.pAllocationSlotMin + self.mAllocationSlotLength * self.pAllocationSlotResolution
            guard_time = microseconds(self.pSIFS + self.pExtraIFS + self.mClockResolution)
            expected_tx_time = self.get_phy().calc_tx_time(self.tx_packet)
            remain_alloc_time = ((self.alloc_end_time - self.alloc_start_time) -
                                 (self.get_env().now - self.beacon_rx_time - self.alloc_start_time))

            ack_rx_time = self.get_phy().calc_tx_time(self.tx_packet)

            tx_header = self.tx_packet.get_mac_header()
            tx_frame_type = tx_header.get_frame_control().frame_type

            # BanMac.logger.log(
            #     sim_time=self.get_env().now,
            #     msg=
            #     f"{self.__class__.__name__}[{self.mac_params.node_id}] set_trx_state_confirm: "
            #     + f"packet frame type: {tx_frame_type.name}, "
            #     + f"allocation time expires at: {self.alloc_end_time:.10f}",
            #     level=logging.DEBUG
            # )

            if tx_frame_type == BanFrameType.IEEE_802_15_6_MAC_CONTROL:
                # Do nothing
                pass
            elif tx_frame_type == BanFrameType.IEEE_802_15_6_MAC_MANAGEMENT:
                # Do nothing
                pass
            elif tx_frame_type == BanFrameType.IEEE_802_15_6_MAC_DATA:
                # BanMac.logger.log(
                #     sim_time=self.get_env().now,
                #     msg=f"BanMac [{self.get_mac_params().node_id}] "
                #         f"alloc_start_time: {self.alloc_start_time: .6f}, "
                #         f"alloc_end_time: {self.alloc_end_time: .6f}, "
                #         f"beacon_rx_time: {self.beacon_rx_time: .6f}, "
                #         f"slot_duration:{slot_duration: .6f}, "
                #         f"reamin_alloc_time:{remain_alloc_time: .6f}, "
                #         f"expected_tx_time: {expected_tx_time: .6f}, "
                #         f"guard_time: {guard_time: .6f}, "
                #         f"ack_rx_time: {ack_rx_time: .6f}, ",
                #     level=logging.DEBUG
                # )

                if (microseconds(slot_duration) >= remain_alloc_time or
                        (expected_tx_time + guard_time + ack_rx_time) >= remain_alloc_time):

                    BanMac.logger.log(
                        sim_time=self.get_env().now,
                        msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] (remain_alloc: {remain_alloc_time}, {expected_tx_time + guard_time + ack_rx_time}, {microseconds(slot_duration)}) no remaining time left, TX failed.",
                        level=logging.WARN
                    )

                    self.change_mac_state(BanMacState.MAC_IDLE)

                    if self.mac_rx_on_when_idle is True:
                        self.get_phy().set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)

                    else:
                        self.get_phy().set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF)

                    return
                # pass

            BanMac.logger.log(
                sim_time=self.get_env().now,
                msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] TX start...",
                level=logging.DEBUG
            )

            self.get_phy().pd_data_request(self.tx_packet)

        elif self.mac_state == BanMacState.MAC_CSMA and (status == BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON
                                                           or status == BanPhyTRxState.IEEE_802_15_6_PHY_SUCCESS):
            # Start the CSMA algorithm as soon as the receiver is enabled
            self.csma_ca.start()

        elif self.mac_state == BanMacState.MAC_IDLE:
            # print('Do nothing special when going idle')
            pass
        elif self.mac_state == BanMacState.MAC_ACK_PENDING:
            # print('Do nothing special when waiting an ACK')
            pass
        else:
            print('Error changing transceiver state')


    def start_tx(self, event: simpy.Environment):
        if self.tx_packet is None:
            BanMac.logger.log(
                sim_time=self.get_env().now,
                msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] start_tx: TX packet is None.",
                level=logging.WARN
            )
            self.set_mac_state(BanMacState.MAC_IDLE)
            return


        if self.mac_state == BanMacState.MAC_ACK_PENDING:
            BanMac.logger.log(
                sim_time=self.get_env().now,
                msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] start_tx: current mode is ACK_PENDING, entering IDLE mode.",
                level=logging.WARN
            )
            self.set_mac_state(BanMacState.MAC_IDLE)
            return

        if self.mac_state == BanMacState.MAC_IDLE:
            self.change_mac_state(BanMacState.MAC_SENDING)
            self.get_phy().set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON)
            return


    def check_queue(self, event: simpy.Environment):
        if self.packet_sent: # 한 슬롯당 한번만 전송
            return

        BanMac.logger.log(
            sim_time=self.get_env().now,
            msg=(
                f"{self.__class__.__name__}[{self.mac_params.node_id}] check_queue: "
                + f"checking queue for pending TX requests..."
            ),
            level=logging.DEBUG
        )
        if self.mac_state == BanMacState.MAC_IDLE and self.tx_queue.empty() is False and self.tx_packet is None:
            self.tx_packet: Packet = self.tx_queue.get_nowait()
            # mac_header: BanMacHeader = self.tx_packet.get_mac_header()
            self.tx_packet.mac_header.time_slot_index = self.time_slot_index
            self.change_mac_state(BanMacState.MAC_SENDING)
            self.get_phy().set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON)


    def set_mac_state(self, mac_state: BanMacState):
        if mac_state == BanMacState.MAC_IDLE:
            self.change_mac_state(BanMacState.MAC_IDLE)
            if self.mac_rx_on_when_idle is True:
                self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)
            else:
                self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF)
            event = self.env.event()
            event._ok = True
            event.callbacks.append(self.check_queue)
            self.env.schedule(event, priority=0, delay=0)

        elif mac_state == BanMacState.MAC_ACK_PENDING:
            self.change_mac_state(BanMacState.MAC_ACK_PENDING)
            self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)

        # CSMA/CA conditions
        elif mac_state == BanMacState.MAC_CSMA:
            if self.mac_state != BanMacState.MAC_IDLE or self.mac_state != BanMacState.MAC_ACK_PENDING:
                raise Exception("Fatal error: CSMA/CA")

            self.change_mac_state(BanMacState.MAC_CSMA)
            self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)

        elif self.mac_state == BanMacState.MAC_CSMA and mac_state == BanMacState.CHANNEL_IDLE:
            self.change_mac_state(BanMacState.MAC_SENDING)
            self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON)

        elif self.mac_state == BanMacState.MAC_CSMA and mac_state == BanMacState.CHANNEL_ACCESS_FAILURE:
            BanMac.logger.log(
                sim_time=self.get_env().now,
                msg=f"{self.__class__.__name__}[{self.mac_params.node_id}]: "
                    + f"I couldn't find any clear channel, dropping TX packet.",
                level=logging.WARN
            )
            self.tx_packet = None
            self.change_mac_state(BanMacState.MAC_IDLE)


    def send_ack(self, event:simpy.Environment):
        if self.mac_state != BanMacState.MAC_IDLE:
            raise Exception(f"Fatal error: invaild MAC state: {self.mac_state.name}")

        BanMac.logger.log(
            sim_time=self.get_env().now,
            msg=f"{self.__class__.__name__}[{self.mac_params.node_id}] "
                + f"sending ACK packet...",
            level=logging.DEBUG
        )

        ack_packet = Packet(packet_size=int(JSONConfig.get_config("packet_size")))
        tx_params = BanTxParams()
        tx_params.ban_id = self.mac_params.ban_id
        tx_params.node_id = self.mac_params.node_id
        tx_params.recipient_id = self.rx_packet.get_mac_header().sender_id
        tx_params.tx_option = BanTxOption.TX_OPTION_NONE
        tx_params.seq_num = self.rx_packet.get_mac_header().get_frame_control().sequence_number
        tx_params.time_slot_info = self.rx_packet.get_mac_header().time_slot_index
        self.time_slot_index = tx_params.time_slot_info

        # ack_pkt.set_mac_header(
        #     BanFrameType.IEEE_802_15_6_MAC_CONTROL,
        #     BanFrameSubType.WBAN_CONTROL_IACK,
        #     tx_params
        # )

        self.set_mac_header(
            packet=ack_packet,
            tx_params=tx_params,
            frame_type=BanFrameType.IEEE_802_15_6_MAC_CONTROL,
            frame_subtype=BanFrameSubType.WBAN_CONTROL_IACK
        )

        # Enqueue the ACK packet for further processing when the transceiver is activated
        self.tx_packet = ack_packet

        # Switch transceiver to Tx mode. Proceed sending the Ack on confirm
        self.change_mac_state(BanMacState.MAC_SENDING)
        self.phy.set_trx_state_request(BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON)


    def ack_wait_timeout(self, event: simpy.Environment):
        # Check whether this timeout is called for previous tx packet or called for current tx packet
        if self.prev_tx_status is True:
            self.prev_tx_status = False   # this flag will be turned on when the node receives a corresponding Ack
            return

        if self.mac_state == BanMacState.MAC_ACK_PENDING:
            BanMac.logger.log(
                sim_time=self.get_env().now,
                level=logging.WARN,
                msg=f"{self.__class__.__name__}[{self.mac_params.node_id}]: "
                    + f"ACK timed out, dropping TX packet."
            )

            # Simply drop the pending packet
            self.tx_packet = None
            self.set_mac_state(BanMacState.MAC_IDLE)
            self.sscs.data_confirm(BanDataConfirmStatus.IEEE_802_15_6_NO_ACK)
        else:
            # Do nothing
            pass


    def set_attribute_confirm(self, status, attribute_id):
        # print('set_attribute_confirm:', status, attribute_id)
        pass


    def show_result(self, event:simpy.Environment | None = None, total: bool = False):
        result = {
            "request": 0,
            "enqueued": 0,
            "success": 0,
            "throughput": 0,
            "energy_cosumption_r": 0
        }

        if total is False:
            result["request"] = self.get_tracer().get_requested_packet_count()
            result["enqueued"] = self.get_tracer().get_enqueued_packet_count()
            result["success"] = self.get_tracer().get_success_packet_count()
            result["throughput"] = round(self.get_tracer().get_throughput() / 1000, 3)
            result["energy_cosumption_r"] = round(self.get_tracer().get_energy_consumption_ratio(), 3)

            output = (
                f"NODE ID: {self.get_mac_params().node_id}\t"
                f"REQUESTED: {self.get_tracer().get_requested_packet_count():5d}\t"
                f"ENQUEUED: {self.get_tracer().get_enqueued_packet_count():5d}\t"
                f"TRANSACTIONS: {self.get_tracer().get_transaction_count():5d}\t"
                f'Packet DELIVERY RATIO: {round(self.get_tracer().get_pkt_delivery_ratio(), 2) * 100:.3f}%\t'
                f"THROUGHPUT: {round(self.get_tracer().get_throughput() / 1000, 3):.3f} kbps\t"
                f"ENERGY CONSUMPTION RATIO: {round(self.get_tracer().get_energy_consumption_ratio(), 3):.3f}%\n"
            )

        else:
            result["request"] = self.get_tracer().get_requested_packet_count()
            result["enqueued"] = self.get_tracer().get_enqueued_packet_count()
            result["success"] = self.get_tracer().get_success_packet_count()
            result["throughput"] = round(self.get_tracer().get_throughput(total=True) / 1000, 3)
            result["energy_cosumption_r"] = round(self.get_tracer().get_energy_consumption_ratio(), 3)

            # output = (
            #     f"NODE: {self.get_mac_params().node_id}\t"
            #     f"REQUESTED: {self.get_tracer().get_requested_packet_count():5d}\t"
            #     f"ENQUEUED: {self.get_tracer().get_enqueued_packet_count():5d}\t"
            #     f"SUCCESS: {self.get_tracer().get_succesget_success_packet_counts_packet_count():5d}\t"
            #     f'Packet DELIVERY RATIO: {round(self.get_tracer().get_pkt_delivery_ratio(total=True), 2) * 100:.3f}%\t'
            #     f"THROUGHPUT: {round(self.get_tracer().get_throughput(total=True) / 1000, 3):.3f} kbps\t"
            #     f"TRANSACTIONS: {self.get_tracer().get_transaction_count():5d}\t"
            #     f"ENERGY CONSUMPTION RATIO: {round(self.get_tracer().get_energy_consumption_ratio(), 3):.3f}%\n"
            # )

            output = (
                f"NODE: {self.get_mac_params().node_id}\t"
                f"REQ / ENQUE / OK / SUCCESS/ENQUE(%) \t"
                f"{self.get_tracer().get_requested_packet_count():5d} / "
                f"{self.get_tracer().get_enqueued_packet_count():5d} / "
                f"{self.get_tracer().get_success_packet_count():5d} / "
                f"{self.get_tracer().get_success_packet_count() / self.get_tracer().get_enqueued_packet_count() * 100 :5.3f}%"
            )

        BanMac.logger.log(
            sim_time=self.env.now,
            msg=output,
            level=logging.FATAL,
        )

        return result


    def plme_cca_confirm(self, status: BanPhyTRxState):
        self.csma_ca.plme_cca_confirm(status)


    def get_ack_wait_duration(self):
        return (
                self.get_phy().aTurnaroundTime                                   # 모드 변경 소요 시간
                + self.get_phy().get_phy_shr_duration()                          #
                + (math.ceil(6 * self.get_phy().get_phy_symbols_per_octet()))    # 전송률(rate)
        )


    def change_mac_state(self, new_state: BanMacState):
        self.mac_state = new_state
