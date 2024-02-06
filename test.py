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


def get_ban_sscs():
    sscs = BanSSCS()
    sscs.use_dqn()
    sscs.set_dqn_trainer(DQNTrainer())
    return sscs


# Create node containers

n1 = NodeBuilder() \
.set_device_params(BanTxParams(ban_id=0, node_id=1, recipient_id=10)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_sscs(BanSSCS()) \
.set_csma_ca(CsmaCa()) \
.set_channel(channel) \
.set_env(env) \
.build()

n2 = NodeBuilder() \
.set_device_params(BanTxParams(ban_id=0, node_id=2, recipient_id=10)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_sscs(BanSSCS()) \
.set_csma_ca(CsmaCa()) \
.set_channel(channel) \
.set_env(env) \
.build()

n3 = NodeBuilder() \
.set_device_params(BanTxParams(0, 3, 10)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_sscs(BanSSCS()) \
.set_csma_ca(CsmaCa()) \
.set_channel(channel) \
.set_env(env) \
.build()

n4 = NodeBuilder() \
.set_device_params(BanTxParams(0, 4, 10)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_sscs(BanSSCS()) \
.set_csma_ca(CsmaCa()) \
.set_channel(channel) \
.set_env(env) \
.build()

n5 = NodeBuilder() \
.set_device_params(BanTxParams(0, 5, 10)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_sscs(BanSSCS()) \
.set_csma_ca(CsmaCa()) \
.set_channel(channel) \
.set_env(env) \
.build()

n6 = NodeBuilder() \
.set_device_params(BanTxParams(0, 6, 10)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_sscs(BanSSCS()) \
.set_csma_ca(CsmaCa()) \
.set_channel(channel) \
.set_env(env) \
.build()

n7 = NodeBuilder() \
.set_device_params(BanTxParams(0, 7, 10)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_sscs(BanSSCS()) \
.set_csma_ca(CsmaCa()) \
.set_channel(channel) \
.set_env(env) \
.build()

n8 = NodeBuilder() \
.set_device_params(BanTxParams(0, 8, 10)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_sscs(BanSSCS()) \
.set_csma_ca(CsmaCa()) \
.set_channel(channel) \
.set_env(env) \
.build()

mob_n1 = MobilityModel(BodyPosition.LEFT_ELBOW)
mob_n2 = MobilityModel(BodyPosition.LEFT_WRIST)
mob_n3 = MobilityModel(BodyPosition.RIGHT_ELBOW)
mob_n4 = MobilityModel(BodyPosition.RIGHT_WRIST)
mob_n5 = MobilityModel(BodyPosition.LEFT_KNEE)
mob_n6 = MobilityModel(BodyPosition.LEFT_ANKLE)
mob_n7 = MobilityModel(BodyPosition.RIGHT_KNEE)
mob_n8 = MobilityModel(BodyPosition.RIGHT_ANKLE)
mob_agent = MobilityModel(BodyPosition.RIGHT_LOWER_TORSO)

n1.get_phy().set_mobility(mob_n1)
n2.get_phy().set_mobility(mob_n2)
n3.get_phy().set_mobility(mob_n3)
n4.get_phy().set_mobility(mob_n4)
n5.get_phy().set_mobility(mob_n5)
n6.get_phy().set_mobility(mob_n6)
n7.get_phy().set_mobility(mob_n7)
n8.get_phy().set_mobility(mob_n8)

n1.get_mac().set_mac_params(BanTxParams(ban_id=0, node_id=1, recipient_id=10))
n2.get_mac().set_mac_params(BanTxParams(ban_id=0, node_id=2, recipient_id=10))
n3.get_mac().set_mac_params(BanTxParams(ban_id=0, node_id=3, recipient_id=10))
n4.get_mac().set_mac_params(BanTxParams(ban_id=0, node_id=4, recipient_id=10))
n5.get_mac().set_mac_params(BanTxParams(ban_id=0, node_id=5, recipient_id=10))
n6.get_mac().set_mac_params(BanTxParams(ban_id=0, node_id=6, recipient_id=10))
n7.get_mac().set_mac_params(BanTxParams(ban_id=0, node_id=7, recipient_id=10))
n8.get_mac().set_mac_params(BanTxParams(ban_id=0, node_id=8, recipient_id=10))

mobility_helper = MobilityHelper(env)
mobility_helper.add_mobility_list(mob_n1)
mobility_helper.add_mobility_list(mob_n2)
mobility_helper.add_mobility_list(mob_n3)
mobility_helper.add_mobility_list(mob_n4)
mobility_helper.add_mobility_list(mob_n5)
mobility_helper.add_mobility_list(mob_n6)
mobility_helper.add_mobility_list(mob_n7)
mobility_helper.add_mobility_list(mob_n8)
mobility_helper.add_mobility_list(mob_agent)

# Create an agent container
# agent = Agent(env)
agent = NodeBuilder() \
.set_device_params(BanTxParams(0, 10, 0)) \
.set_mac(BanMac()) \
.set_phy(BanPhy()) \
.set_csma_ca(CsmaCa()) \
.set_sscs(get_ban_sscs()) \
.set_channel(channel) \
.set_env(env) \
.build()

agent.m_sscs.set_node_list(1)
agent.m_sscs.set_node_list(2)
agent.m_sscs.set_node_list(3)
agent.m_sscs.set_node_list(4)
agent.m_sscs.set_node_list(5)
agent.m_sscs.set_node_list(6)
agent.m_sscs.set_node_list(7)
agent.m_sscs.set_node_list(8)

agent.m_sscs.set_dqn_trainer(DQNTrainer())

agent.m_phy.set_mobility(mob_agent)



def start(event, node: Node = agent):
    ev = node.env.event()
    ev._ok = True
    ev.callbacks.append(node.m_sscs.send_beacon)
    node.env.schedule(ev, priority=0, delay=0)



def send_data(device: Node, delay: float):
    packet: Packet = Packet(packet_size=10)
    mac_header = BanMacHeader()
    mac_header.set_tx_params(ban_id=0, sender_id=1, recipient_id=0)

    packet.set_mac_header_(mac_header=mac_header)

    event = device.env.event()
    event._ok = True
    event.callbacks.append(
        lambda _: device.m_sscs.send_data(tx_packet=packet)
    )

    device.env.schedule(event, priority=0, delay=delay)


# Generate events (generate packet events)
event = env.event()
event._ok = True
event.callbacks.append(start)
# event.callbacks.append()
# event.callbacks.append(n2.generate_data)
# event.callbacks.append(n3.generate_data)
# event.callbacks.append(n4.generate_data)
# event.callbacks.append(n5.generate_data)
# event.callbacks.append(n6.generate_data)
# event.callbacks.append(n7.generate_data)
# event.callbacks.append(n8.generate_data)
env.schedule(event, priority=NORMAL, delay=0.1)

delay = 0.1
send_data(n1, delay)
send_data(n2, delay)
send_data(n3, delay)
send_data(n4, delay)
send_data(n5, delay)
send_data(n6, delay)
send_data(n7, delay)
send_data(n8, delay)


# Generate events (generate mobility)
event = env.event()
event._ok = True
event.callbacks.append(mobility_helper.do_walking)

env.schedule(event, priority=NORMAL, delay=0)

# Set the simulation run time
run_time = 500  # seconds

# Print statistical results
event = env.event()
event._ok = True
event.callbacks.append(n1.m_mac.show_result)
event.callbacks.append(n2.m_mac.show_result)
event.callbacks.append(n3.m_mac.show_result)
event.callbacks.append(n4.m_mac.show_result)
event.callbacks.append(n5.m_mac.show_result)
event.callbacks.append(n6.m_mac.show_result)
event.callbacks.append(n7.m_mac.show_result)
event.callbacks.append(n8.m_mac.show_result)
env.schedule(event, priority=NORMAL, delay=1)

# Run simulation
env.run(until=run_time)
