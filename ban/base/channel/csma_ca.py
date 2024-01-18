import random
from enum import Enum

from ban.base.utils import microseconds


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


class CsmaCa:
    def __init__(self):
        self.__env = None
        self.__mac = None
        self.__is_slotted = False   # beacon-enabled slotted or nonbeacon-enabled unslotted CSMA/CA
        self.__nb = 0   # number of backoffs for the current transmission
        self.__cw = 2   # contention window length (used in slotted ver only)
        self.__be = 3   # backoff exponent
        self.__ble = False  # battery life extension
        self.__mac_min_backoff_exp = 3   # minimum backoff exponent
        self.__mac_max_backoff_exp = 5   # maximum backoff exponent
        self.__mac_max_csma_backoffs = 4    # maximum number of backoffs
        self.__unit_backoff_period = 20   # number of symbols per CSMA/CA time unit, default 20 symbols
        self.__cca_request_running = False  # flag indicating that the PHY is currently running a CCA

    def set_env(self, env):
        self.__env = env

    def get_env(self):
        return self.__env

    def set_mac(self, mac):
        self.__mac = mac

    def get_mac(self):
        return self.__mac

    def set_slotted_csma_ca(self):
        self.__is_slotted = True

    def set_unslotted_csma_ca(self):
        self.__is_slotted = False

    def is_slotted_csma_ca(self):
        return self.__is_slotted

    def is_unslotted_csma_ca(self):
        return not self.__is_slotted

    def set_mac_min_backoff_exp(self, min_backoff_exp):
        self.__mac_min_backoff_exp = min_backoff_exp

    def get_mac_min_backoff_exp(self):
        return self.__mac_min_backoff_exp

    def set_mac_max_backoff_exp(self, max_backoff_exp):
        self.__mac_max_backoff_exp = max_backoff_exp

    def get_mac_max_backoff_exp(self):
        return self.__mac_max_backoff_exp

    def set_mac_max_csma_backoffs(self, max_csma_backoffs):
        self.__mac_max_csma_backoffs = max_csma_backoffs

    def get_mac_max_csma_backoffs(self):
        return self.__mac_max_csma_backoffs

    def set_unit_backoff_period(self, unit_backoff_period):
        self.__unit_backoff_period = unit_backoff_period

    def get_unit_backoff_period(self):
        return self.__unit_backoff_period

    def get_time_to_next_slot(self):
        # TODO: calculate the offset to the next slot
        return 0

    def start(self):
        self.__nb = 0
        if self.is_slotted_csma_ca() is True:
            self.__cw = 2
            if self.__ble is True:
                self.__be = min(2, self.__mac_min_backoff_exp)
            else:
                self.__be = self.__mac_min_backoff_exp
            # TODO: for slotted, locate backoff period boundary, i.e., delay to the next slot boundary
            backoff_boundary = self.get_time_to_next_slot()

            event = self.__env.event()
            event._ok = True
            event.callbacks.append(self.random_backoff_delay)
            self.__env.schedule(event, priority=0, delay=backoff_boundary)
        else:
            self.__be = self.__mac_min_backoff_exp

            event = self.__env.event()
            event._ok = True
            event.callbacks.append(self.random_backoff_delay)
            self.__env.schedule(event, priority=0, delay=0)

    def cancel(self):
        pass

    def random_backoff_delay(self, event):
        upper_bound = pow(2, self.__be - 1)
        is_data = False

        symbol_rate = self.__mac.get_phy().get_data_or_symbol_rate(is_data)    # symbols per second
        backoff_period = random.uniform(0, upper_bound + 1)    # number of backoff periods
        rando__backoff = microseconds(backoff_period * self.get_unit_backoff_period() * 1000 * 1000 / symbol_rate)

        if self.is_unslotted_csma_ca() is True:
            event = self.__env.event()
            event._ok = True
            event.callbacks.append(self.request_cca)
            self.__env.schedule(event, priority=0, delay=rando__backoff)
        else:
            event = self.__env.event()
            event._ok = True
            event.callbacks.append(self.can_proceed)
            self.__env.schedule(event, priority=0, delay=rando__backoff)

    def can_proceed(self, event):
        can_proceed = True

        if can_proceed is True:
            backoff_boundary = self.get_time_to_next_slot()

            event = self.__env.event()
            event._ok = True
            event.callbacks.append(self.request_cca)
            self.__env.schedule(event, priority=0, delay=backoff_boundary)
        else:
            next_cap = 0

            event = self.__env.event()
            event._ok = True
            event.callbacks.append(self.random_backoff_delay)
            self.__env.schedule(event, priority=0, delay=next_cap)

    def request_cca(self, event):
        self.__cca_request_running = True
        self.__mac.get_phy().plme_cca_request()

    def plme_cca_confirm(self, status: BanPhyTRxState):
        if self.__cca_request_running is True:
            self.__cca_request_running = False

            if status == BanPhyTRxState.IEEE_802_15_6_PHY_IDLE:
                if self.is_slotted_csma_ca() is True:
                    self.__cw -= 1
                    if self.__cw == 0:
                        self.__mac.set_mac_state(BanMacState.CHANNEL_IDLE)
                    else:
                        event = self.__env.event()
                        event._ok = True
                        event.callbacks.append(self.request_cca)
                        self.__env.schedule(event, priority=0, delay=0)
                else:
                    self.__mac.set_mac_state(BanMacState.CHANNEL_IDLE)
            else:
                if self.is_slotted_csma_ca() is True:
                    self.__cw = 2
                self.__be = min(self.__be + 1, self.__mac_max_backoff_exp)
                self.__nb += 1
                if self.__nb > self.__mac_max_csma_backoffs:
                    # no channel found so cannot send packet
                    self.__mac.set_mac_state(BanMacState.CHANNEL_ACCESS_FAILURE)
                    return
                else:
                    # perform another backoff (step 2)
                    event = self.__env.event()
                    event._ok = True
                    event.callbacks.append(self.random_backoff_delay)
                    self.__env.schedule(event, priority=0, delay=0)

    def get_nb(self):
        # return the number of CSMA retries
        return self.__nb
