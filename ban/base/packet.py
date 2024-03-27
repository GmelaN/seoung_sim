from ban.base.channel.base_channel import SpectrumSignalParameters
from ban.device.mac_header import BanFrameSubType, BanMacHeader, Data, Beacon, IAck, BanFrameType

class Packet:
    def __init__(self, packet_size: int):
        self.__size = packet_size
        self.__success = False
        self.__spectrum_tx_params = SpectrumSignalParameters()
        self.__mac_header = BanMacHeader()

        self.__mac_frame_body = None

    # def set_mac_header(self, frame_type: BanFrameType, frame_subtype: BanFrameSubType, tx_params: BanTxParams):
    #     assert frame_type is not None
    #     assert frame_subtype is not None
    #     assert tx_params is not None
    #     assert tx_params.node_id is not None and tx_params.ban_id is not None and tx_params.recipient_id is not None
    #
    #     self.__mac_header.set_tx_params(tx_params.ban_id, tx_params.node_id, tx_params.recipient_id)
    #     self.__mac_header.set_frame_control(frame_type, frame_subtype, tx_params.tx_option, tx_params.seq_num)
    #
    #     if frame_subtype == BanFrameSubType.WBAN_MANAGEMENT_BEACON:
    #         self.__mac_frame_body = Beacon()
    #     elif frame_subtype == BanFrameSubType.WBAN_CONTROL_IACK:
    #         self.__mac_frame_body = IAck()
    #     elif frame_subtype == BanFrameSubType.WBAN_DATA_UP0:
    #         self.__mac_frame_body = Data(0)
    #     elif frame_subtype == BanFrameSubType.WBAN_DATA_UP1:
    #         self.__mac_frame_body = Data(1)
    #     elif frame_subtype == BanFrameSubType.WBAN_DATA_UP2:
    #         self.__mac_frame_body = Data(2)
    #     elif frame_subtype == BanFrameSubType.WBAN_DATA_UP3:
    #         self.__mac_frame_body = Data(3)
    #     elif frame_subtype == BanFrameSubType.WBAN_DATA_UP4:
    #         self.__mac_frame_body = Data(4)
    #     elif frame_subtype == BanFrameSubType.WBAN_DATA_UP5:
    #         self.__mac_frame_body = Data(5)
    #     elif frame_subtype == BanFrameSubType.WBAN_DATA_UP6:
    #         self.__mac_frame_body = Data(6)
    #     elif frame_subtype == BanFrameSubType.WBAN_DATA_UP7:
    #         self.__mac_frame_body = Data(7)
    #     else:
    #         self.__mac_frame_body = None
    #         print('frame initialization error (invalid frame subtype)')

    def set_mac_header_(self, mac_header: BanMacHeader):
        self.__mac_header = mac_header

    def get_mac_header(self) -> BanMacHeader:
        if self.__mac_header is None:
            raise Exception("mac header is not set.")

        return self.__mac_header

    def set_frame_body(self, frame_body):
        self.__mac_frame_body = frame_body
        return

    def get_frame_body(self):
        if self.__mac_frame_body is None:
            raise Exception("mac frame body is not set.")

        return self.__mac_frame_body

    def set_spectrum_tx_params(self, spec_tx_params: SpectrumSignalParameters):
        self.__spectrum_tx_params = spec_tx_params

    def get_spectrum_tx_params(self):
        if self.__spectrum_tx_params is None:
            raise Exception("mac header is not set.")

        return self.__spectrum_tx_params

    def get_size(self):
        return self.__size

    def set_success(self, status: bool):
        self.__success = status
        return

    def get_success(self):
        return self.__success

    def copy(self):
        new_packet = Packet(self.__size)
        new_packet.set_spectrum_tx_params(self.get_spectrum_tx_params())
        new_packet.set_mac_header_(self.get_mac_header())
        new_packet.set_frame_body(self.get_frame_body())
        new_packet.set_success(self.get_success())

        return new_packet

    def set_data(self):
        return
