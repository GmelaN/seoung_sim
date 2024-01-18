import math

from ban.base.channel.base_channel import LossModel
from ban.base.mobility import MobilityModel


class PropLossModel(LossModel):
    def __init__(self):
        self.m_frequency = None
        self.m_lambda = None    # wave length = speed of light in vacuum (m/s) / frequency (Hz)
        self.m_min_loss = 0.0
        self.m_system_loss = 1.0

    def calculate_path_loss(self, model1: MobilityModel, model2: MobilityModel) -> float:

        distance = model1.get_distance_from(model2.get_position())

        distance *= 1000    # convert meter to millimeter

        is_los = model1.is_los(model2.get_position())

        # We can see the BAN-specific path loss model below
        # G. Dolmans and A. Fort, "Channel models WBAN-holst centre/imec-nl," IEEE 802.15-08-0418-01-0006, 2008.
        a = 15.5
        b = 5.38
        sigma_n = 5.35
        shadowing_db = 9.05    # shadowing factor
        path_loss_db = a * math.log10(distance) + b + sigma_n

        if is_los is False:
            path_loss_db += shadowing_db


        # print("DEBUG: calculate_path_loss returning", path_loss_db)
        return path_loss_db

    # Calculate the rx power based on friis propagation loss model
    def calculate_rx_power_friis(self, tx_power_dbm: float, a: MobilityModel, b: MobilityModel) -> float:
        distance = a.get_distance_from(b.get_position())

        if self.m_lambda is None:
            raise Exception("you must set lambda by PropLossModel.set_frequency first.")

        if distance < (3 * self.m_lambda):
            print('distance not within the far field region => inaccurate propagation loss value')
        if distance <= 0:
            return tx_power_dbm - self.m_min_loss

        numerator = self.m_lambda * self.m_lambda
        denominator = 16 * math.pi * math.pi * distance * distance * self.m_system_loss
        loss_db = -10 * math.log10(numerator / denominator)

        # print("DEBUG: calculate_rx_power_friis returning", tx_power_dbm - max(loss_db, self.m_min_loss))
        return tx_power_dbm - max(loss_db, self.m_min_loss)

    def set_frequency(self, m_frequency: float) -> None:
        self.m_frequency = m_frequency
        # This default value is the propagation speed of light in the vacuum
        c = 299792458  # m/s
        self.m_lambda = c / m_frequency
