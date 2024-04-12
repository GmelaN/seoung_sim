import logging

from simpy import Environment

from ban.base.channel.base_channel import DelayModel, LossModel, SpectrumSignalParameters
from ban.base.logging.log import SeoungSimLogger
from ban.base.mobility import BodyPosition, MobilityModel
from ban.base.packet import Packet
from ban.base.positioning import Vector
from ban.config.JSONConfig import JSONConfig


class Channel:
    logger = SeoungSimLogger(logger_name="CHANNEL", level=logging.DEBUG)

    def __init__(self):
        self.__env = None
        self.__loss_model: LossModel = None
        self.__delay_model: DelayModel = None
        self.__path_loss_model = None  # path loss model

        self.__max_loss_db = 1.0e9
        self.__tx_packet: Packet = None
        self.__phy_list = list()  # send a data packet to all the registered phy modules

        self.additional_tx_power_loss = float(JSONConfig.get_config("additional_tx_loss"))

    def add_phy_list(self, phy):
        self.__phy_list.append(phy)

    def set_env(self, env: Environment):
        self.__env = env

    def get_env(self):
        return self.__env

    def set_loss_model(self, loss_model: LossModel):
        self.__loss_model = loss_model

    def set_delay_model(self, delay_model: DelayModel):
        self.__delay_model = delay_model

    def set_tx_packet(self, tx_packet):
        self.__tx_packet = tx_packet

    def start_tx(self, event):
        # Channel.logger.log(
        #     sim_time=self.get_env().now,
        #     msg=
        #     f"\tChannel: starting TX, "
        #     + f"packet size: {self.__tx_packet.get_size()}, "
        #     + f"from: {self.__tx_packet.get_mac_header().sender_id}, "
        #     + f"to: {self.__tx_packet.get_mac_header().recipient_id}, "
        # )

        # 필요한 멤버가 정의되어 있는지 검사
        if self.__tx_packet is None:
            raise Exception("Packet is not defined.")

        if self.__delay_model is None:
            raise Exception("delay model is not set.")

        sender_mobility = self.__tx_packet.get_spectrum_tx_params().tx_phy.get_mobility()

        if sender_mobility is None:
            raise Exception("mobility model is not set.")

        for receiver in self.__phy_list:
            if receiver == self.__tx_packet.get_spectrum_tx_params().tx_phy:
                # if the sender is the receiver, skip the transmission
                continue

            receiver_mobility: MobilityModel = receiver.get_mobility()
            if receiver_mobility is None:
                raise Exception("mobility model is not set.")

            # LOS 미확보 여부 계산
            body_pos: BodyPosition = receiver_mobility.body_position
            node_pos: Vector = receiver_mobility.get_position()
            if body_pos == BodyPosition.LEFT_ELBOW or body_pos == BodyPosition.RIGHT_ELBOW:
                if node_pos.y > 1.6 and 0.7 <= node_pos.z <= 0.8:
                    continue

            if body_pos == BodyPosition.LEFT_WRIST or body_pos == BodyPosition.RIGHT_WRIST:
                if node_pos.y > 1.6 and 0.5 <= node_pos.z <= 0.6:
                    continue

            if body_pos == BodyPosition.LEFT_KNEE or body_pos == BodyPosition.RIGHT_KNEE:
                if node_pos.y > 0.95 and 0.7 <= node_pos.z <= 0.8:
                    continue

            if body_pos == BodyPosition.LEFT_ANKLE or body_pos == BodyPosition.RIGHT_ANKLE:
                if node_pos.y > 1.0 and 0.5 <= node_pos.z <= 0.6:
                    continue

            # 패킷 손실, 지연 계산
            path_loss_db = self.__loss_model.calculate_path_loss(sender_mobility, receiver_mobility)
            prop_delay = self.__delay_model.get_delay(sender_mobility, receiver_mobility)

            # 수신 패킷 설정
            packet_copy = self.__tx_packet.copy()

            spec_rx_params = SpectrumSignalParameters()
            spec_rx_params.duration = packet_copy.get_spectrum_tx_params().duration
            spec_rx_params.tx_power = packet_copy.get_spectrum_tx_params().tx_power
            spec_rx_params.tx_phy = packet_copy.get_spectrum_tx_params().tx_phy
            spec_rx_params.tx_antenna = packet_copy.get_spectrum_tx_params().tx_antenna
            # 모델에서 계산된 손실값 반영
            spec_rx_params.tx_power -= path_loss_db

            spec_rx_params.tx_power -= self.additional_tx_power_loss

            # 수신 패킷 설정 완료
            packet_copy.set_spectrum_tx_params(spec_rx_params)
            receiver.set_rx_packet(packet_copy)

            # print("DEBUG: rx packet rx_params set to", packet_copy.get_spectrum_tx_params().tx_power)

            # 이벤트에 수신 이벤트 등록
            event = self.__env.event()
            event._ok = True
            event.callbacks.append(receiver.start_rx)
            self.__env.schedule(event, priority=0, delay=prop_delay)
