import logging

from simpy import Environment

from ban.base.channel.base_channel import DelayModel, LossModel, SpectrumSignalParameters
from ban.base.packet import Packet


class Channel:
    # TODO: builder 패턴 적용
    def __init__(self):
        self.__env = None
        self.__loss_model: LossModel = None
        self.__delay_model: DelayModel = None
        self.__path_loss_model = None  # path loss model

        self.__max_loss_db = 1.0e9
        self.__tx_packet: Packet = None
        self.__phy_list = list()  # send a data packet to all the registered phy modules

        self.__logger = logging.getLogger("CHANNEL")
        self.__logger.setLevel(logging.DEBUG)
        self.__logger.addHandler(logging.StreamHandler())

    def add_phy_list(self, phy):
        self.__phy_list.append(phy)

    def set_env(self, env: Environment):
        self.__env = env

    def set_loss_model(self, loss_model: LossModel):
        self.__loss_model = loss_model

    def set_delay_model(self, delay_model: DelayModel):
        self.__delay_model = delay_model

    def set_tx_packet(self, tx_packet):
        self.__tx_packet = tx_packet

    def start_tx(self, event):
        self.__logger.debug(
            f"Channel: starting TX"
            + f"packet size: {self.__tx_packet.get_size()}, "
            + f"from: {self.__tx_packet.get_mac_header().sender_id}, "
            + f"to: {self.__tx_packet.get_mac_header().recipient_id}, "
        )
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

            receiver_mobility = receiver.get_mobility()

            if receiver_mobility is None:
                raise Exception("mobility model is not set.")

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

            # 수신 패킷 설정 완료
            packet_copy.set_spectrum_tx_params(spec_rx_params)
            receiver.set_rx_packet(packet_copy)

            # print("DEBUG: rx packet rx_params set to", packet_copy.get_spectrum_tx_params().tx_power)

            # 이벤트에 수신 이벤트 등록
            event = self.__env.event()
            event._ok = True
            event.callbacks.append(receiver.start_rx)
            self.__env.schedule(event, priority=0, delay=prop_delay)
