from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class BanFrameType(Enum):
    IEEE_802_15_6_MAC_MANAGEMENT = 0
    IEEE_802_15_6_MAC_CONTROL = 1
    IEEE_802_15_6_MAC_DATA = 2


class BanFrameSubType(Enum):
    WBAN_MANAGEMENT_BEACON = 0
    WBAN_CONTROL_IACK = 1
    WBAN_DATA_UP0 = 2
    WBAN_DATA_UP1 = 3
    WBAN_DATA_UP2 = 4
    WBAN_DATA_UP3 = 5
    WBAN_DATA_UP4 = 6
    WBAN_DATA_UP5 = 7
    WBAN_DATA_UP6 = 8
    WBAN_DATA_UP7 = 9
    UNDEFINED = 10


@dataclass
class FrameControl:
    version = None
    ack_policy = None
    sec_level = None
    tk_index = None
    relay = None
    ack_timing = None
    frame_subtype = None
    frame_type: BanFrameType = None
    more_data = None
    last_frame = None
    sequence_number = None
    frag_number = None
    non_final_frag = None
    reserved = None


@dataclass
class AssignedLinkElement:
    allocation_id: int | None = None
    interval_start: int | None = None
    interval_end: int | None = None
    tx_power: float | None = None


class BanMacHeader:
    def __init__(self):
        self.__frame_control = FrameControl()
        self.ban_id: int = None
        self.sender_id: int = None
        self.recipient_id: int = None

    def set_frame_control(self, frame_type: BanFrameType, frame_subtype: BanFrameSubType, ack_policy, sequence_number):
        self.get_frame_control().frame_type = frame_type
        self.get_frame_control().frame_subtype = frame_subtype
        self.get_frame_control().ack_policy = ack_policy
        self.get_frame_control().sequence_number = sequence_number

    def get_frame_control(self):
        if self.__frame_control is None:
            raise Exception("frame control is not set.")

        return self.__frame_control

    def set_tx_params(self, ban_id, sender_id, recipient_id):
        self.ban_id = ban_id
        self.sender_id = sender_id
        self.recipient_id = recipient_id

    def get_tx_params(self) -> Tuple[int, int, int]:
        return self.ban_id, self.sender_id, self.recipient_id


class Beacon:
    def __init__(self):
        self.__assigned_slot_info = list()  # element type is '@dataclass AssignedLinkElement'

    def set_assigned_link_info(self, assigned_link: AssignedLinkElement):
        self.__assigned_slot_info.append(assigned_link)

    def get_assigned_link_info(self, node_id):
        for s_info in self.__assigned_slot_info:
            if s_info.allocation_id == node_id:
                return s_info
        return None


class IAck:
    def __init__(self):
        pass


class Data:
    def __init__(self, priority):
        self.priority = priority
