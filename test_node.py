import logging

import simpy
import tqdm
from simpy.events import NORMAL

from ban.base.channel.channel import Channel
from ban.base.channel.prop_delay_model import PropDelayModel
from ban.base.channel.prop_loss_model import PropLossModel
from ban.base.helper.mobility_helper import MobilityHelper
from ban.base.mobility import BodyPosition, MobilityModel
from ban.base.packet import Packet
from ban.device.mac_header import BanMacHeader
from ban.device.node import NodeBuilder, Node
from ban.device.sscs import BanTxParams, BanSSCS


SIM_TIME = 10
show_result_delay_interval = 10
pbar = tqdm.tqdm(total=(int(SIM_TIME) * 1000) // 255, leave=True, position=0)


'''Test start'''
env = simpy.Environment()  # Create the SimPy environment


'''channel'''
channel = Channel()  # All nodes share a channel environment
channel.set_env(env)
prop_loss_model = PropLossModel()
prop_loss_model.set_frequency(0.915e9)  # We assume the wireless channel operates in 915 Mhz
prop_delay_model = PropDelayModel()
channel.set_loss_model(prop_loss_model)
channel.set_delay_model(prop_delay_model)


'''SET DEVICES'''
N_NODES = 3

devices = [
    NodeBuilder().set_device_params(BanTxParams(ban_id=0, node_id=i + 1, recipient_id=0)).set_channel(channel).set_env(env).build()
    for i in range(N_NODES)
]

positions = [
    BodyPosition.LEFT_ELBOW,
    BodyPosition.LEFT_WRIST,
    BodyPosition.RIGHT_ELBOW,
    BodyPosition.RIGHT_WRIST,
    BodyPosition.LEFT_KNEE,
    BodyPosition.RIGHT_KNEE,
    BodyPosition.LEFT_ANKLE,
    BodyPosition.RIGHT_ANKLE,
]
for idx, device in enumerate(devices):
    mob = MobilityModel(positions[idx])
    device.get_phy().set_mobility(mob)


'''SET AGENT'''
banSSCS = BanSSCS()
banSSCS.coordinator = True
banSSCS.set_env(env)
agent = NodeBuilder().set_device_params(BanTxParams(ban_id=0, node_id=0, recipient_id=0)).set_sscs(banSSCS).set_channel(channel).set_env(env).build()

mob_agent = MobilityModel(BodyPosition.HEAD)
agent.get_phy().set_mobility(mob_agent)


'''SET MOBILITY'''
mobility_helper = MobilityHelper(env)

mobility_helper.add_mobility_list(mob_agent)

for device in devices:
    mobility_helper.add_mobility_list(device.get_phy().get_mobility())
    agent.m_sscs.set_node_list(device.get_mac().get_mac_params().node_id)


'''SCHEDULE BEACON EVENT'''
ev = agent.env.event()
ev._ok = True
ev.callbacks.append(lambda _: agent.m_sscs.send_beacon(event=None, pbar=pbar))
agent.env.schedule(ev, priority=0, delay=0)

packet: Packet = Packet(packet_size=10)
mac_header = BanMacHeader()
mac_header.set_tx_params(ban_id=0, sender_id=1, recipient_id=0)

packet.set_mac_header_(mac_header=mac_header)


'''SCHEDULE WALKING EVENT'''
ev = env.event()
ev._ok = True
ev.callbacks.append(mobility_helper.do_walking)
env.schedule(ev, priority=NORMAL, delay=0)


'''SCHEDULE SENDING SAMPLE DATA'''
for device in devices:
    packet: Packet = Packet(packet_size=10)
    mac_header = BanMacHeader()
    mac_header.set_tx_params(ban_id=0, sender_id=device.get_mac().get_mac_params().node_id, recipient_id=0)
    packet.set_mac_header_(mac_header=mac_header)

    event = device.env.event()
    event._ok = True
    event.callbacks.append(lambda _: device.m_sscs.send_data(tx_packet=packet))
    device.env.schedule(event, priority=NORMAL, delay=0.1)


'''RUN SIMULATION'''
env.run(until=SIM_TIME)
device.get_mac().show_result()

pbar.close()
