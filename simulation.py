from datetime import date
import simpy
from simpy.events import NORMAL

from ban.base.channel.channel import Channel
from ban.base.helper.mobility_helper import MobilityHelper
from ban.base.mobility import MobilityModel, BodyPosition
from ban.base.packet import Packet
from ban.base.q_learning.q_learning_trainer import QLearningTrainer
from ban.base.tracer import Tracer
from ban.config.JSONConfig import JSONConfig
from ban.device.mac_header import BanMacHeader
from ban.device.node import NodeBuilder, Node
from ban.device.sscs import BanSSCS, BanTxParams


'''SET SIMULATION PARAMETERS'''
# SIMULATION_TIME = int(JSONConfig.get_config("simulation_time"))  # Set the simulation run time(in seconds)
# NODE_COUNT = int(JSONConfig.get_config("node_count"))  # count for non-coordinator node(s), MAX: 8
# WEIGHT = int(JSONConfig.get_config("priority_weight"))
# use_q_learning = bool(JSONConfig.get_config("use_q_learning"))
# TIME_SLOTS = int(JSONConfig.get_config("time_slots"))
# COORDINATOR_ID = 99
# MOBILITY_POSITIONS = tuple(BodyPosition)[7:]


class Simulation:
    MOBILITY_POSITIONS = tuple(BodyPosition)[7:]

    def __init__(
            self,
            simulation_time: int = 1000,
            node_count: int = 8,
            priority_weight: float = 0.1,
            use_q_learning: bool = True,
            time_slots: int = 8,
            coordinator_id: int = 99,
            ):
        
        self.NODE_COUNT = node_count
        self.USE_Q_LEARNING = use_q_learning
        self.SIMULATION_TIME = simulation_time
        self.COORDINATOR_ID = coordinator_id
        self.priority_wight = priority_weight


        self.env: simpy.Environment = simpy.Environment()
        self.mobility_helper: MobilityHelper = MobilityHelper(self.env)
        self.channel = Channel(self.mobility_helper)
        self.channel.set_env(self.env)

        # Create node containers
        self.nodes: list[Node] = [
            NodeBuilder()
            .set_device_params(BanTxParams(0, i, self.COORDINATOR_ID))
            .set_channel(self.channel)
            .set_env(self.env)
            .build()
            for i in range(node_count)
        ]

        self.tracers: list[Tracer] = [node.get_mac().get_tracer() for node in self.nodes]

        # Create agent containers
        nodeBuilder = NodeBuilder()
        nodeBuilder.set_device_params(BanTxParams(0, self.COORDINATOR_ID, self.COORDINATOR_ID))
        nodeBuilder.set_channel(self.channel)
        nodeBuilder.set_env(self.env)
        nodeBuilder.set_sscs(self.get_coor_sscs(self.mobility_helper, self.tracers))
        self.agent: Node = nodeBuilder.build()

        self.mob_agent = MobilityModel(BodyPosition.BODY)
        self.mobility_helper.add_mobility_list(self.mob_agent)
        self.agent.get_phy().set_mobility(self.mob_agent)

        for i, position in enumerate(Simulation.MOBILITY_POSITIONS):
            if i >= node_count:
                break

            mobility = MobilityModel(position)
            self.nodes[i].get_phy().set_mobility(mobility)
            self.mobility_helper.add_mobility_list(mobility)

            # Set mac parameters
            self.nodes[i].get_mac().set_mac_params(BanTxParams(0, i, self.COORDINATOR_ID))

            self.agent.m_sscs.set_node_list(i)

        if not use_q_learning:
            self.agent.m_sscs.q_learning_trainer.turn_off()

    def set_q_learning_parameter(self, learning_rate: float, discount_factor: float, exploration_rate: float):
        trainer: QLearningTrainer = self.agent.m_sscs.q_learning_trainer

        trainer.learning_rate = learning_rate
        trainer.discount_factor = discount_factor
        trainer.exploration_rate = exploration_rate

    def get_coor_sscs(self, mobility_helper: MobilityHelper, tracers: list[Tracer]):
        sscs = BanSSCS(
            node_count=self.NODE_COUNT,
            mobility_helper=mobility_helper,
            node_priority=tuple(i+self.priority_wight for i in range(self.NODE_COUNT)),
            coordinator=True,
            tracers=tracers
        )
        return sscs
    

    def send_data(self, env):
        for node in self.nodes:
            packet: Packet = Packet(packet_size=int(JSONConfig.get_config("packet_size")))
            mac_header = BanMacHeader()
            mac_header.set_tx_params(ban_id=0, sender_id=node.m_tx_params.node_id, recipient_id=self.COORDINATOR_ID)

            packet.set_mac_header_(mac_header=mac_header)
            node.m_sscs.send_data(packet)

    def schedule_send_beacon(self, delay: float=0):
        event = self.env.event()
        event._ok = True
        event.callbacks.append(lambda _: self.agent.m_sscs.send_beacon(event=self.env))
        self.env.schedule(event, priority=NORMAL, delay=delay)

    def schedule_do_walking(self, delay: float = 0.5 - 0.000001):
        event = self.env.event()
        event._ok = True
        event.callbacks.append(self.mobility_helper.change_cycle)
        self.env.schedule(event, priority=NORMAL, delay=delay)

    def schedule_send_data(self, delay: float = 0.0002):
        event = self.env.event()
        event._ok = True
        event.callbacks.append(self.send_data)
        self.env.schedule(event, priority=NORMAL, delay=delay)

    def schedule_show_result(self):
        event = self.env.event()
        event._ok = True
        event.callbacks.append(self.show_result)
        event.callbacks.append(self.agent.m_sscs.print_q_table)
        self.env.schedule(event, priority=NORMAL, delay=self.SIMULATION_TIME - 0.00001)


    def show_result(self, env):
        result: list[dict] = [dict() for _ in range(self.NODE_COUNT)]

        for i in range(self.NODE_COUNT):
            result[i] = self.nodes[i].m_mac.show_result(total=True)

        config: str = f"nodes: {self.NODE_COUNT}\tsimulation time: {self.SIMULATION_TIME}\tpriority weight: {self.priority_wight}"
        string = str(date.today()) + ("_q_learning" if self.USE_Q_LEARNING else "vanilla")

        with open(f"{string}.txt", 'w', encoding="UTF8") as f:
            for k in result[0].keys():
                f.write(f"{str(k):>20}")

            f.write('\n')

            for i in result:
                for j in i.keys():
                    f.write(f"{i[j]:>20.3f}")

                f.write('\n')

            f.write(config)


    def run(self):
        self.env.run(until=self.SIMULATION_TIME)


if __name__ == "__main__":
    simulation = Simulation()

    simulation.schedule_send_beacon()
    simulation.schedule_send_data()
    simulation.schedule_do_walking()
    simulation.schedule_show_result()

    simulation.set_q_learning_parameter(
        learning_rate=0.5,
        discount_factor=0.9,
        exploration_rate=0.5
    )

    simulation.agent.m_sscs.q_learning_trainer.turn_off()
    simulation.run()

    del simulation

    simulation = Simulation()

    simulation.schedule_send_beacon()
    simulation.schedule_send_data()
    simulation.schedule_do_walking()
    simulation.schedule_show_result()

    simulation.set_q_learning_parameter(
        learning_rate=2,
        discount_factor=0.9,
        exploration_rate=0.9
    )

    simulation.run()
