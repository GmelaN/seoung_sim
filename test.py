import simpy
from simpy.events import NORMAL
from tqdm import tqdm

from ban.base.channel.channel import Channel
from ban.base.channel.prop_delay_model import PropDelayModel
from ban.base.channel.prop_loss_model import PropLossModel
from ban.base.helper.mobility_helper import MobilityHelper
from ban.base.mobility import MobilityModel, BodyPosition
from ban.base.packet import Packet
from ban.base.tracer import Tracer
from ban.config.JSONConfig import JSONConfig
from ban.device.mac_header import BanMacHeader
from ban.device.node import NodeBuilder, Node
from ban.device.sscs import BanSSCS, BanTxParams

# Test start
env = simpy.Environment()  # Create the SimPy environment


'''SET SIMULATION PARAMETERS'''
simulation_time = int(JSONConfig.get_config("simulation_time"))  # Set the simulation run time(in seconds)
NODE_COUNT = int(JSONConfig.get_config("node_count"))  # count for non-coordinator node(s), MAX: 8

# channel
channel = Channel()      # All nodes share a channel environment
channel.set_env(env)
prop_loss_model = PropLossModel()
prop_loss_model.set_frequency(0.915e9)  # We assume the wireless channel operates in 915 Mhz
prop_delay_model = PropDelayModel()
channel.set_loss_model(prop_loss_model)
channel.set_delay_model(prop_delay_model)

COORDINATOR_ID = 99

def get_ban_sscs(mobility_helper: MobilityHelper, tracers: list[Tracer]):
    sscs = BanSSCS(
        node_count=NODE_COUNT,
        mobility_helper=mobility_helper,
        node_priority=tuple(i+10 for i in range(NODE_COUNT)),
        coordinator=True,
        tracers=tracers
    )
    return sscs


# Create node containers
nodes: list[Node] = [
    NodeBuilder()
    .set_device_params(BanTxParams(0, i, COORDINATOR_ID))
    .set_channel(channel)
    .set_env(env)
    .build()
    for i in range(NODE_COUNT)
]

# Mobility
mobility_helper: MobilityHelper = MobilityHelper(env)

tracers: list[Tracer] = [node.get_mac().get_tracer() for node in nodes]

# Create agent containers
nodeBuilder = NodeBuilder()
nodeBuilder.set_device_params(BanTxParams(0, COORDINATOR_ID, COORDINATOR_ID))
nodeBuilder.set_channel(channel)
nodeBuilder.set_env(env)
nodeBuilder.set_sscs(get_ban_sscs(mobility_helper, tracers))

agent: Node = nodeBuilder.build()

mob_agent = MobilityModel(BodyPosition.BODY)
mobility_helper.add_mobility_list(mob_agent)
agent.get_phy().set_mobility(mob_agent)

# Mobility positions
mobility_positions = tuple(BodyPosition)[7:]

for i, position in enumerate(mobility_positions):
    if i >= NODE_COUNT:
        break

    mobility = MobilityModel(position)
    nodes[i].get_phy().set_mobility(mobility)
    mobility_helper.add_mobility_list(mobility)

    # Set mac parameters
    nodes[i].get_mac().set_mac_params(BanTxParams(0, i + 1, COORDINATOR_ID))

    agent.m_sscs.set_node_list(i)

# Generate events (generate packet events)
agent.m_sscs.send_beacon(event=env)

delay = 0.01

def send_data(env):
    for node in nodes:
        packet: Packet = Packet(packet_size=int(JSONConfig.get_config("packet_size")))
        mac_header = BanMacHeader()
        mac_header.set_tx_params(ban_id=0, sender_id=node.m_tx_params.node_id, recipient_id=COORDINATOR_ID)

        packet.set_mac_header_(mac_header=mac_header)
        node.m_sscs.send_data(packet)

event = env.event()
event._ok = True
event.callbacks.append(send_data)
env.schedule(event, priority=NORMAL, delay=delay)



# Generate events (generate mobility)
event = env.event()
event._ok = True
event.callbacks.append(mobility_helper.do_walking)

env.schedule(event, priority=NORMAL, delay=0)

# Print statistical results
# event = env.event()
# event._ok = True
# for node in nodes:
#     event.callbacks.append(node.m_mac.show_result)
# env.schedule(event, priority=NORMAL, delay=10)


pbar = tqdm(total=simulation_time - 1)

def update_pbar(ev=None):
    event = env.event()
    event._ok = True
    event.callbacks.append(lambda _: pbar.update(1))
    event.callbacks.append(update_pbar)
    env.schedule(event, priority=NORMAL, delay=1)

update_pbar()

# Run simulation

# Print statistical results
event = env.event()
event._ok = True

# for node in range(len(nodes)):
#     event = env.event()
#     event._ok = True
#     event.callbacks.append(lambda _: nodes[node].m_mac.show_result(total=True))
#     env.schedule(event, priority=NORMAL, delay=simulation_time - 0.00001)


event.callbacks.append(lambda _: nodes[0].m_mac.show_result(total=True))
event.callbacks.append(lambda _: nodes[1].m_mac.show_result(total=True))
event.callbacks.append(lambda _: nodes[2].m_mac.show_result(total=True))
event.callbacks.append(lambda _: nodes[3].m_mac.show_result(total=True))
event.callbacks.append(lambda _: nodes[4].m_mac.show_result(total=True))
event.callbacks.append(lambda _: nodes[5].m_mac.show_result(total=True))
event.callbacks.append(lambda _: nodes[6].m_mac.show_result(total=True))
event.callbacks.append(lambda _: nodes[7].m_mac.show_result(total=True))

env.schedule(event, priority=NORMAL, delay=simulation_time - 0.00001)

env.run(until=simulation_time)


