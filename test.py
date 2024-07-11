from collections import namedtuple
import json

import simpy
from simpy.events import NORMAL

# test comment

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

WEIGHT = int(JSONConfig.get_config("priority_weight"))

use_q_learning = bool(JSONConfig.get_config("use_q_learning"))

TIME_SLOTS = int(JSONConfig.get_config("time_slots"))


'''mobility helper'''
mobility_helper: MobilityHelper = MobilityHelper(env)

'''channel'''
channel = Channel(mobility_helper)      # All nodes share a channel environment
channel.set_env(env)

COORDINATOR_ID = 99

def get_ban_sscs(mobility_helper: MobilityHelper, tracers: list[Tracer]):
    sscs = BanSSCS(
        node_count=NODE_COUNT,
        mobility_helper=mobility_helper,
        node_priority=tuple(i+WEIGHT for i in range(NODE_COUNT)),
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

'''Mobility'''
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
    nodes[i].get_mac().set_mac_params(BanTxParams(0, i, COORDINATOR_ID))

    agent.m_sscs.set_node_list(i)

if not use_q_learning:
    agent.m_sscs.q_learning_trainer.turn_off()


'''GENERATE EVENTS'''
def send_data(env):
    for node in nodes:
        packet: Packet = Packet(packet_size=int(JSONConfig.get_config("packet_size")))
        mac_header = BanMacHeader()
        mac_header.set_tx_params(ban_id=0, sender_id=node.m_tx_params.node_id, recipient_id=COORDINATOR_ID)

        packet.set_mac_header_(mac_header=mac_header)
        node.m_sscs.send_data(packet)

'''do_walking event'''
event = env.event()
event._ok = True
event.callbacks.append(mobility_helper.change_cycle)
env.schedule(event, priority=NORMAL, delay=0.5 - 0.000001)

'''send_beacon event'''
event = env.event()
event._ok = True
event.callbacks.append(lambda _: agent.m_sscs.send_beacon(event=env))
env.schedule(event, priority=NORMAL, delay=0)

'''send_data event'''
delay = 0.0002
event = env.event()
event._ok = True
event.callbacks.append(send_data)
env.schedule(event, priority=NORMAL, delay=delay)


'''show result event'''
result: list[dict] = [dict() for _ in range(NODE_COUNT)]
def show_result(env):
    for i in range(NODE_COUNT):
        result[i] = nodes[i].m_mac.show_result(total=True)

    config: str = ""
    with open("./config.json", 'r', encoding="UTF8") as f:
        for i in f.readlines():
            config += i

    string = "q_learning" if use_q_learning else "vanilla"

    with open(f"result_{string}.txt", 'w', encoding="UTF8") as f:
        for k in result[0].keys():
            f.write(f"{str(k):>20}")

        f.write('\n')

        for i in result:
            for j in i.keys():
                f.write(f"{i[j]:>20.3f}")

            f.write('\n')

        f.write(config)


event = env.event()
event._ok = True
event.callbacks.append(show_result)
event.callbacks.append(agent.m_sscs.print_q_table)
env.schedule(event, priority=NORMAL, delay=simulation_time - 0.00001)


'''RUN SIMULATION'''
env.run(until=simulation_time)
