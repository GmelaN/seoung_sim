import logging

import simpy

from ban.base.channel.channel import Channel
from ban.base.channel.csma_ca import CsmaCa
from ban.base.channel.prop_delay_model import PropDelayModel
from ban.base.channel.prop_loss_model import PropLossModel
from ban.base.helper.mobility_helper import MobilityHelper
from ban.base.mobility import BodyPosition, MobilityModel
from ban.base.packet import Packet
from ban.device.mac import BanMac
from ban.device.node import NodeBuilder, Node
from ban.device.phy import BanPhy
from ban.device.sscs import BanTxParams, BanSSCS


# Test start
env = simpy.Environment()  # Create the SimPy environment

# channel
channel = Channel()      # All nodes share a channel environment
channel.set_env(env)
prop_loss_model = PropLossModel()
prop_loss_model.set_frequency(0.915e9)  # We assume the wireless channel operates in 915 Mhz
prop_delay_model = PropDelayModel()
channel.set_loss_model(prop_loss_model)
channel.set_delay_model(prop_delay_model)

device = NodeBuilder() \
.set_device_params(BanTxParams(ban_id=0, node_id=1, recipient_id=0)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_sscs(BanSSCS()) \
.set_csma_ca(CsmaCa()) \
.set_channel(channel) \
.set_env(env) \
.build()

mob_n1 = MobilityModel(BodyPosition.LEFT_ELBOW)
device.get_phy().set_mobility(mob_n1)
#
# n2.get_mac().set_mac_params(BanTxParams(ban_id=0, node_id=1, recipient_id=10))


agent = NodeBuilder() \
.set_device_params(BanTxParams(ban_id=0, node_id=0, recipient_id=1)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_csma_ca(CsmaCa()) \
.set_sscs(BanSSCS()) \
.set_channel(channel) \
.set_env(env) \
.build()

mob_agent = MobilityModel(BodyPosition.RIGHT_LOWER_TORSO)
agent.get_phy().set_mobility(mob_agent)

mobility_helper = MobilityHelper(env)
mobility_helper.add_mobility_list(mob_n1)
mobility_helper.add_mobility_list(mob_agent)


agent.m_sscs.set_node_list(device.get_mac().get_mac_params().node_id)

# agent.m_sscs.set_tx_params(BanTxParams(ban_id=2, node_id=2, recipient_id=0))
# n2.m_sscs.set_tx_params(BanTxParams(ban_id=0, node_id=0, recipient_id=2))


ev = agent.env.event()
ev._ok = True
ev.callbacks.append(agent.m_sscs.send_beacon)
agent.env.schedule(ev, priority=0, delay=0)

packet: Packet = Packet(packet_size=10)

event = device.env.event()
event._ok = True
event.callbacks.append(
    lambda _: device.m_sscs.send_data(tx_packet=packet))
device.env.schedule(event, priority=0, delay=0.01)

# Run simulation
env.run(until=1)
