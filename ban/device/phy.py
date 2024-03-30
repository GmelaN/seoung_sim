import logging
import math
from dataclasses import dataclass, fields
from enum import Enum
from typing import Tuple

import simpy

from ban.base.channel.base_channel import AntennaModel, SpectrumSignalParameters
from ban.base.logging.log import SeoungSimLogger
from ban.base.mobility import MobilityModel
from ban.base.packet import Packet
from ban.base.utils import seconds
from ban.base.channel.channel import Channel


class BanPhyTRxState(Enum):
    IEEE_802_15_6_PHY_BUSY = 0
    IEEE_802_15_6_PHY_BUSY_RX = 1
    IEEE_802_15_6_PHY_BUSY_TX = 2
    IEEE_802_15_6_PHY_FORCE_TRX_OFF = 3
    IEEE_802_15_6_PHY_IDLE = 4
    IEEE_802_15_6_PHY_INVALID_PARAMETER = 5
    IEEE_802_15_6_PHY_RX_ON = 6
    IEEE_802_15_6_PHY_SUCCESS = 7
    IEEE_802_15_6_PHY_TRX_OFF = 8
    IEEE_802_15_6_PHY_TX_ON = 9
    IEEE_802_15_6_PHY_UNSUPPORTED_ATTRIBUTE = 10
    IEEE_802_15_6_PHY_READ_ONLY = 11
    IEEE_802_15_6_PHY_UNSPECIFIED = 12


class BanPhyOption(Enum):
    IEEE_802_15_6_868MHZ_BPSK = 0
    IEEE_802_15_6_915MHZ_BPSK = 1
    IEEE_802_15_6_868MHZ_ASK = 2
    IEEE_802_15_6_915MHZ_ASK = 3
    IEEE_802_15_6_868MHZ_OQPSK = 4
    IEEE_802_15_6_915MHZ_OQPSK = 5
    IEEE_802_15_6_2_4GHZ_OQPSK = 6
    IEEE_802_15_6_INVALID_PHY_OPTION = 7


class BanPibAttributeIdentifier(Enum):
    PHY_CURRENT_CHANNEL = 0
    PHY_CHANNELS_SUPPORTED = 1
    PHY_TRANSMIT_POWER = 2
    PHY_CCA_MODE = 3
    PHY_CURRENT_PAGE = 4
    PHY_MAX_FRAME_DURATION = 5
    PHY_SHR_DURATION = 6
    PHY_SYMBOLS_PER_OCTET = 7


@dataclass
class BanPhyPibAttributes:
    phy_current_channel = None
    phy_channels_supported = None
    phy_tx_power: float | None = None
    phy_cca_mode = None
    phy_current_page = None
    phy_max_frame_duration = None
    phy_shr_duration = None
    phy_symbols_per_octet = None


@dataclass
class BanPhyDataAndSymbolRates:
    bit_rate: float | None = None
    symbol_rate: float | None = None


@dataclass
class BanPhyPpduHeaderSymbolNumber:         # PPDU: Physical layer Protocol Data Unit
    shr_preamble: float | None = None       # Physical Layer Header: T_PHR
    shr_sfd: float | None = None            # PSDU: T_PSDU
    phr: float | None = None                # Synchronization header: T_SHR

NOISE = -10

class BanPhy:
    # the turnaround time for switching the transceiver from RX to TX or vice versa
    aTurnaroundTime = 12

    logger = SeoungSimLogger(logger_name="BAN-PHY", level=logging.DEBUG)

    def __init__(self):
        self.__env = None
        self.__rx_sensitivity = None
        self.__tx_power = None
        self.__noise = NOISE  # dB
        self.__error_model = None
        self.__channel = None
        self.__mac = None
        self.__mobility = None
        self.__antenna = None
        self.__cca_peak_power = 0.0

        self.__pib_attributes = BanPhyPibAttributes()
        self.__rx_pkt = None
        self.__phy_option = BanPhyOption.IEEE_802_15_6_INVALID_PHY_OPTION

        self.__data_symbol_rates: Tuple[BanPhyDataAndSymbolRates, ...] = tuple(
            BanPhyDataAndSymbolRates(i, j)
            for i, j in (
                (20.0, 20.0),
                (40.0, 40.0),
                (250.0, 12.5),
                (250.0, 50.0),
                (100.0, 25.0),
                (250.0, 62.5),
                (250.0, 62.5)
            )
        )

        self.__ppdu_header_symbol_num: Tuple[BanPhyPpduHeaderSymbolNumber, ...] = tuple(
            BanPhyPpduHeaderSymbolNumber(i, j, k)
            for i, j, k in (
                (32.0, 8.0, 8.0),
                (32.0, 8.0, 8.0),
                (2.0, 1.0, 0.4),
                (6.0, 1.0, 1.6),
                (8.0, 2.0, 2.0),
                (8.0, 2.0, 2.0),
                (8.0, 2.0, 2.0)
            )
        )

        self.__trx_state = BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF


    def set_env(self, env: simpy.Environment):
        self.__env = env

    def get_env(self):
        return self.__env

    # For calling the MAC functions (callback)
    def set_mac(self, mac):
        self.__mac = mac

    def get_mac(self):
        return self.__mac

    def set_channel(self, channel: Channel):
        self.__channel = channel
        self.__channel.add_phy_list(self)

    def get_channel(self):
        return self.__channel

    def set_mobility(self, mobility: MobilityModel):
        self.__mobility = mobility

    def get_mobility(self):
        return self.__mobility

    def set_rx_packet(self, rx_packet: Packet):
        self.__rx_pkt = rx_packet

    def set_antenna(self, antenna: AntennaModel):
        self.__antenna = antenna

    def get_rx_antenna(self):
        return self.__antenna

    def do_initialize(self):
        self.__phy_option = BanPhyOption.IEEE_802_15_6_915MHZ_OQPSK
        self.__rx_sensitivity = -82  # dBm

    def set_attribute_request(self, attribute_id: BanPibAttributeIdentifier, attribute: BanPhyPibAttributes):
        status = BanPhyTRxState.IEEE_802_15_6_PHY_SUCCESS

        attribute_details = {
            f.name: getattr(attribute, f.name)
            for f in fields(attribute)
            if getattr(attribute, f.name) is not None
        }

        if attribute_id == BanPibAttributeIdentifier.PHY_TRANSMIT_POWER:
            if attribute.phy_tx_power > 0xbf:
                status = BanPhyTRxState.IEEE_802_15_6_PHY_INVALID_PARAMETER
            else:
                self.__pib_attributes.phy_tx_power = attribute.phy_tx_power

        elif attribute_id == BanPibAttributeIdentifier.PHY_CURRENT_CHANNEL:
            status = BanPhyTRxState.IEEE_802_15_6_PHY_UNSUPPORTED_ATTRIBUTE
        elif attribute_id == BanPibAttributeIdentifier.PHY_CHANNELS_SUPPORTED:
            status = BanPhyTRxState.IEEE_802_15_6_PHY_UNSUPPORTED_ATTRIBUTE
        elif attribute_id == BanPibAttributeIdentifier.PHY_CCA_MODE:
            if attribute.phy_cca_mode < 1 or attribute.phy_cca_mode > 3:
                status = BanPhyTRxState.IEEE_802_15_6_PHY_INVALID_PARAMETER
            else:
                self.__pib_attributes.phy_cca_mode = attribute.phy_cca_mode
        else:
            status = BanPhyTRxState.IEEE_802_15_6_PHY_UNSUPPORTED_ATTRIBUTE

        self.get_mac().set_attribute_confirm(status, attribute_id)

    def get_data_or_symbol_rate(self, is_data: bool) -> float:
        """
        returns rate of data or symbol in seconds
        :param is_data: bool
        :return: rate
        """
        rate = 0.0
        if self.__phy_option == BanPhyOption.IEEE_802_15_6_INVALID_PHY_OPTION:
            raise Exception("Invalid PHY option detected.")

        if is_data is True:
            rate = self.__data_symbol_rates[self.__phy_option.value].bit_rate  # data rate
        else:
            rate = self.__data_symbol_rates[self.__phy_option.value].symbol_rate  # symbol rate
        return rate * 1000.0

    def set_trx_state_request(self, new_state: BanPhyTRxState):
        # Trying to set __trx_state to new_state
        if self.__trx_state == new_state:
            self.__mac.set_trx_state_confirm(new_state)
            return

        if ((new_state == BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON or
             new_state == BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF) and
                self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_TX):
            # return  # Send set_trx_state_confirm() later
            self.change_trx_state(new_state)
            self.__mac.set_trx_state_confirm(new_state)

        if new_state == BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF:

            if self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX:
                # return  # Send set_trx_state_confirm() later
                self.change_trx_state(new_state)
                self.__mac.set_trx_state_confirm(new_state)
            elif (self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON or
                  self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON):
                self.change_trx_state(BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF)
                self.__mac.set_trx_state_confirm(new_state)
                return

        # turn on PHY_TX_ON
        if new_state == BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON:
            # terminate reception if needed
            # incomplete reception -- force packet discard
            if (self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX or
                    self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON):
                self.change_trx_state(BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON)
                self.__mac.set_trx_state_confirm(BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON)
                return
            # We do not change the transceiver state here.
            # We only report that the transceiver is already in Tx_On state
            elif (self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_TX or
                  self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON):
                self.__mac.set_trx_state_confirm(BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON)
                return
            # Simply set the transceiver to Tx mode
            elif self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF:
                self.change_trx_state(BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON)
                self.__mac.set_trx_state_confirm(BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON)
                return

        if new_state == BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON:
            if (self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON or
                    self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF):
                self.change_trx_state(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)
                self.__mac.set_trx_state_confirm(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)
                return
            # Simply set the transceiver to Rx mode
            if self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX:
                self.__mac.set_trx_state_confirm(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)
                return

    def change_trx_state(self, new_state: BanPhyTRxState):
        self.__trx_state = new_state

    def pd_data_request(self, tx_packet: Packet):
        if self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_TX_ON:
            self.change_trx_state(BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_TX)

            spec_tx_params = SpectrumSignalParameters()
            tx_duration = self.calc_tx_time(tx_packet)
            spec_tx_params.duration = tx_duration
            spec_tx_params.tx_phy = self
            spec_tx_params.tx_power = self.__pib_attributes.phy_tx_power
            spec_tx_params.tx_antenna = self.__antenna

            # Add the spectrum Tx parameters to the Tx_pkt
            tx_packet.set_spectrum_tx_params(spec_tx_params)

            # We have to previously forward the required parameter before we register the event of a function call
            self.get_channel().set_tx_packet(tx_packet)

            # update trace info
            self.get_mac().get_tracer().add_tx_packet(tx_packet)


            event = self.__env.event()
            event._ok = True
            event.callbacks.append(self.get_channel().start_tx)
            event.callbacks.append(self.end_tx)
            self.__env.schedule(event, priority=0, delay=tx_duration)

        # Transmission fails because the transceiver is not prepared to send a packet
        elif (self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON or
              self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF or
              self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_TX):

            BanPhy.logger.log(
                sim_time=self.__env.now,
                msg=f"{self.__class__.__name__}[{self.__mac.get_mac_params().node_id}] "
                    f"transmission failed due to PHY is not ready: current state is {self.__trx_state.name}",
                level=logging.WARN,
                newline=" "
            )

            self.get_mac().pd_data_confirm(self.__trx_state)

    def end_tx(self, event):
        # If the transmission successes
        self.get_mac().pd_data_confirm(BanPhyTRxState.IEEE_802_15_6_PHY_SUCCESS)

        # If the transmission aborted
        # self.change_trx_state(BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF)

        # print('Time:', round(self.__env.now, 5), '  Send a packet at the physical layer (NID:%d)'
        #       % self.__mac.__mac_params.node_id)

        # if the transmission fails

    def start_rx(self, event):
        drop_reason = ""
        if self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON:
            # If the 10*log10 (sinr) > -5, then receive the packet, otherwise drop the packet
            self.change_trx_state(BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX)

            if self.__rx_pkt.get_spectrum_tx_params().tx_power + self.__noise >= self.__rx_sensitivity:
                self.__rx_pkt.success = True
            else:
                drop_reason = "low TX power"
                self.__rx_pkt.success = False
            # print('Rx power (dBm):', self.__rx_pkt.get_spectrum_tx_params().tx_power + self.__noise)
        elif self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX:
            drop_reason = "current PHY state is BUSY_TX"
            self.__rx_pkt.success = False
        else:
            drop_reason = "unknown"
            self.__rx_pkt.success = False

        # Update peak power if CCA is in progress
        power = self.__rx_pkt.get_spectrum_tx_params().tx_power + self.__noise
        if self.__cca_peak_power < power:
            self.__cca_peak_power = power

        rx_duration = self.calc_tx_time(self.__rx_pkt)

        if len(drop_reason) != 0:
            BanPhy.logger.log(
                sim_time=self.get_env().now,
                msg=f"RX packet will dropped due to: {drop_reason}",
                level=logging.WARN
            )

        event = self.__env.event()
        event._ok = True
        event.callbacks.append(self.end_rx)
        self.__env.schedule(event, priority=0, delay=rx_duration)

    def end_rx(self, event):
        # If the packet was successfully received, push it up the stack
        if self.__rx_pkt.success is True:
            self.__mac.pd_data_indication(self.__rx_pkt)

        if self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX:
            self.change_trx_state(BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON)

    def calc_tx_time(self, tx_packet: Packet) -> float:
        """
        calculate total packet TX time(including PPDU header)
        :param tx_packet: Packet
        :return:
        """
        is_data = True
        tx_time = self.get_ppdu_header_tx_time()

        # multiply 8.0 for convert bits to bytes
        tx_time += (tx_packet.get_size() * 8.0 / self.get_data_or_symbol_rate(is_data))  # seconds

        return tx_time

    def get_ppdu_header_tx_time(self) -> float | None:
        """
        calculate total PPDU header TX time
        :return:
        """
        is_data = False
        if self.__phy_option != BanPhyOption.IEEE_802_15_6_INVALID_PHY_OPTION:
            total_ppdu_hdr_symbols = (
                self.__ppdu_header_symbol_num[self.__phy_option.value].shr_preamble +
                self.__ppdu_header_symbol_num[self.__phy_option.value].shr_sfd +
                self.__ppdu_header_symbol_num[self.__phy_option.value].phr
            )
        else:
            print('fatal error: Invalid phy option')
            return None
        return seconds((total_ppdu_hdr_symbols / self.get_data_or_symbol_rate(is_data)))

    def get_phy_shr_duration(self):
        if self.__phy_option != BanPhyOption.IEEE_802_15_6_INVALID_PHY_OPTION:
            return (self.__ppdu_header_symbol_num[self.__phy_option.value].shr_preamble +
                    self.__ppdu_header_symbol_num[self.__phy_option.value].shr_sfd)
        else:
            print('fatal error: Invalid phy option')
            return None

    def get_phy_symbols_per_octet(self):
        if self.__phy_option != BanPhyOption.IEEE_802_15_6_INVALID_PHY_OPTION:
            return (self.__data_symbol_rates[self.__phy_option.value].symbol_rate /
                    (self.__data_symbol_rates[self.__phy_option.value].bit_rate / 8))
        else:
            print('fatal error: Invalid phy option')
            return None

    def plme_cca_request(self):
        if (self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_RX_ON or
                self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX):
            self.__cca_peak_power = 0.0
            cca_time = seconds(8.0 / self.get_data_or_symbol_rate(False))

            event = self.__env.event()
            event._ok = True
            event.callbacks.append(self.end_cca)
            self.__env.schedule(event, priority=0, delay=cca_time)  # clear channel assessment during cca_time
        else:
            if self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF:
                self.__mac.plme_cca_confirm(BanPhyTRxState.IEEE_802_15_6_PHY_TRX_OFF)
            else:
                self.__mac.plme_cca_confirm(BanPhyTRxState.IEEE_802_15_6_PHY_BUSY)

    def end_cca(self, event):
        sensed_channel_state = BanPhyTRxState.IEEE_802_15_6_PHY_UNSPECIFIED

        # From here, we evaluate the historical channel state during cca_time
        if self.phy_is_busy() is True:
            sensed_channel_state = BanPhyTRxState.IEEE_802_15_6_PHY_BUSY
        elif self.__pib_attributes.phy_cca_mode == 1:
            if 10 * math.log10(self.__cca_peak_power / self.__rx_sensitivity) >= 10.0:
                sensed_channel_state = BanPhyTRxState.IEEE_802_15_6_PHY_BUSY
                print('CCA result =', sensed_channel_state)
            else:
                sensed_channel_state = BanPhyTRxState.IEEE_802_15_6_PHY_IDLE
                print('CCA result =', sensed_channel_state)
        elif self.__pib_attributes.phy_cca_mode == 2:
            if self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX:
                sensed_channel_state = BanPhyTRxState.IEEE_802_15_6_PHY_BUSY
            else:
                sensed_channel_state = BanPhyTRxState.IEEE_802_15_6_PHY_IDLE
        elif self.__pib_attributes.phy_cca_mode == 3:
            if (10 * math.log10(self.__cca_peak_power / self.__rx_sensitivity) >= 10.0 and
                    self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX):
                sensed_channel_state = BanPhyTRxState.IEEE_802_15_6_PHY_BUSY
            else:
                sensed_channel_state = BanPhyTRxState.IEEE_802_15_6_PHY_IDLE
        else:
            print('fatal error: Invalid CCA mode')

        self.__mac.plme_cca_confirm(sensed_channel_state)

    def phy_is_busy(self):
        return (self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_TX or
                self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY_RX or
                self.__trx_state == BanPhyTRxState.IEEE_802_15_6_PHY_BUSY)
