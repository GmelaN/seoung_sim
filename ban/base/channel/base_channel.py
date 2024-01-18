from dataclasses import dataclass
from abc import ABC, abstractmethod

from ban.base.mobility import MobilityModel


class LossModel(ABC):
    @abstractmethod
    def calculate_path_loss(self, sender_mobility: MobilityModel, receiver_mobility: MobilityModel) -> float:
        pass

    @abstractmethod
    def calculate_rx_power_friis(self, tx_power_dbm: float, a: MobilityModel, b: MobilityModel) -> float:
        pass


class DelayModel(ABC):
    @abstractmethod
    def get_delay(self, sender_mobility: MobilityModel, receiver_mobility: MobilityModel) -> float:
        pass


class AntennaModel(ABC):
    pass


@dataclass
class SpectrumSignalParameters:
    duration: float | None = None
    tx_phy: None = None
    tx_power: float | None = None  # dBm
    tx_antenna: AntennaModel | None = None
