import unittest

import simpy
from simpy.events import NORMAL

from ban.base.channel.channel import Channel
from ban.base.channel.csma_ca import CsmaCa
from ban.base.channel.prop_delay_model import PropDelayModel
from ban.base.channel.prop_loss_model import PropLossModel
from ban.base.dqn.dqn_trainer import DQNTrainer
from ban.base.helper.mobility_helper import MobilityHelper
from ban.base.mobility import MobilityModel, BodyPosition
from ban.base.packet import Packet
from ban.device.mac import BanMac
from ban.device.mac_header import BanMacHeader
from ban.device.node import NodeBuilder, Node
from ban.device.phy import BanPhy
from ban.device.sscs import BanSSCS, BanTxParams
from ban.base.positioning import Vector


class TestChannel(unittest.TestCase):
    def setUp(self):
        self.env: simpy.Environment = simpy.Environment()

        # SET UP CHANNEL
        self.channel: Channel = Channel()
        self.channel.set_delay_model(PropDelayModel())
        loss_model: PropLossModel = PropLossModel()
        loss_model.set_frequency(0.915e9)
        self.channel.set_loss_model(loss_model)
        self.channel.set_env(self.env)

        # SET UP NODE
        self.coordinator: Node = (
            NodeBuilder()
               .set_env(self.env)
               .set_channel(self.channel)
               .set_device_params(BanTxParams(0, 1, 2))
               .build()
        )

        mobility_model: MobilityModel = MobilityModel(BodyPosition.LEFT_ELBOW)
        mobility_model.set_position(Vector(0, 0, 0))
        self.coordinator.get_phy().set_mobility(mobility_model)
        self.coordinator.m_sscs.set_node_list(2)

        self.n2: Node = (
            NodeBuilder()
            .set_env(self.env)
            .set_channel(self.channel)
            .set_device_params(BanTxParams(0, 2, 1))
            .build()
        )

        mobility_model: MobilityModel = MobilityModel(BodyPosition.LEFT_ELBOW)
        mobility_model.set_position(Vector(0, 0, 1))
        self.n2.get_phy().set_mobility(mobility_model)
        self.n2.m_sscs.set_node_list(1)

        # SEND BEACON SIGNAL
        event: simpy.Event = self.env.event()
        event._ok = True
        event.callbacks.append(self.coordinator.m_sscs.send_beacon)
        self.env.schedule(event, NORMAL, 0)

    def test_tracer(self):
        event: simpy.Event = self.env.event()
        event._ok = True
        event.callbacks.append(self.n2.generate_data)
        self.env.schedule(event, NORMAL, 0.1)

        self.env.run(until=0.5)

        self.n2.get_mac().get_tracer().get_energy_consumption_ratio()
        self.n2.get_mac().get_tracer().get_throughput()
        self.n2.get_mac().get_tracer().get_transaction_count()
        self.n2.get_mac().get_tracer().get_pkt_delivery_ratio()



if __name__ == "__main__":
    unittest.main()
