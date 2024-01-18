from ban.base.channel.base_channel import DelayModel
from ban.base.mobility import MobilityModel


class PropDelayModel(DelayModel):
    def __init__(self):
        # This default value is the propagation speed of light in the vacuum
        self.m_delay = 299792458  # m/s

    def get_delay(self, a: MobilityModel, b: MobilityModel):
        distance = a.get_distance_from(b.get_position())
        seconds = distance / self.m_delay
        return seconds
