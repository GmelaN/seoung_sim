import logging

from simpy import Environment

from ban.base.channel.base_channel import DelayModel, LossModel, SpectrumSignalParameters
from ban.base.helper.mobility_helper import MobilityHelper
from ban.base.logging.log import SeoungSimLogger
from ban.base.mobility import MobilityModel
from ban.base.packet import Packet


class Channel:
    logger = SeoungSimLogger(logger_name="CHANNEL", level=logging.DEBUG)

    def __init__(self, mob_helper: MobilityHelper):
        self.env = None

        self.tx_packet: Packet = None
        self.phy_list = list()  # send a data packet to all the registered phy modules

        self.mob_helper: MobilityHelper = mob_helper


    def add_phy_list(self, phy):
        self.phy_list.append(phy)

    def set_env(self, env: Environment):
        self.env = env

    def get_env(self):
        return self.env

    def set_loss_model(self, loss_model: LossModel):
        return

    def set_delay_model(self, delay_model: DelayModel):
        return

    def set_tx_packet(self, tx_packet):
        self.tx_packet = tx_packet

    def start_tx(self, event):
        for receiver in self.phy_list:
            if receiver == self.tx_packet.get_spectrum_tx_params().tx_phy:
                # if the sender is the receiver, skip the transmission
                continue

            sender_id = self.tx_packet.get_mac_header().sender_id

            if sender_id != 99:
                time_slot = self.tx_packet.get_mac_header().time_slot_index

                assert time_slot is not None

                if not self.mob_helper.can_transaction(sender_id, time_slot):
                    Channel.logger.log(
                        sim_time=self.env.now,
                        msg=f"{self.mob_helper.current_phase.name} not allows transaction, dropping packet from: {sender_id} to: {self.tx_packet.get_mac_header().recipient_id}, "
                            + f"sender's position: {self.mob_helper.mobility_list[sender_id].get_body_position().name}, "
                            + f"current time slot info: {time_slot}, ",
                        level=logging.INFO
                    )
                    continue

            
            # 수신 패킷 설정
            packet_copy = self.tx_packet.copy()

            spec_rx_params = SpectrumSignalParameters()
            spec_rx_params.duration = packet_copy.get_spectrum_tx_params().duration
            spec_rx_params.tx_power = packet_copy.get_spectrum_tx_params().tx_power
            spec_rx_params.tx_phy = packet_copy.get_spectrum_tx_params().tx_phy
            spec_rx_params.tx_antenna = packet_copy.get_spectrum_tx_params().tx_antenna

            # 수신 패킷 설정 완료
            packet_copy.set_spectrum_tx_params(spec_rx_params)
            receiver.set_rx_packet(packet_copy)

            # print("DEBUG: rx packet rx_params set to", packet_copy.get_spectrum_tx_params().tx_power)

            # 이벤트에 수신 이벤트 등록
            event = self.env.event()
            event._ok = True
            event.callbacks.append(receiver.start_rx)
            self.env.schedule(event, priority=0, delay=0)
