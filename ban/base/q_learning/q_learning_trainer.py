import enum
import logging
import random
from collections import namedtuple, defaultdict
from typing import Dict

import numpy as np

np.random.seed(42)

from dataclasses import dataclass

from tqdm.auto import tqdm

from ban.base.helper.mobility_helper import MovementPhase, MobilityHelper
from ban.base.logging.log import SeoungSimLogger
from ban.base.tracer import Tracer
from ban.config.JSONConfig import JSONConfig


@dataclass(frozen=True)
class State:
    phase: MovementPhase
    slot: int


class QLearningTrainer:
    logger = SeoungSimLogger(logger_name="BAN-RL", level=logging.DEBUG)

    def __init__(
            self,
            node_count: int,
            time_slots: int,
            sscs,
            movement_phases: MovementPhase,
            mobility_helper: MobilityHelper,
            tracers: list[Tracer],

            learning_rate: float = 0.2,
            discount_factor: float = 0.9,
            exploration_rate: float = 0.5,
    ):
        '''

        :param node_count:
        :param time_slots:
        :param sscs:
        :param movement_phases:
        :param mobility_helper:
        :param tracers:
        :param learning_rate:
        :param discount_factor:
        :param exploration_rate:
        '''

        '''KEYS FROM CONFIGURATION'''
        CONFIG_KEYS: tuple[str, ...] = ("node_count", "time_slots", "learning_rate", "discount_factor", "exploration_rate")
        configs = dict()

        for key in CONFIG_KEYS:
            config = JSONConfig.get_config(key)

            if config is not None:
                configs[key] = float(config)
            else:
                configs[key] = None

        '''PARAMETERS FROM CONFIGURATION'''
        self.node_count: int = int(configs["node_count"]) if node_count is None else node_count
        self.time_slots: int = int(configs["time_slots"]) if time_slots is None else time_slots
        self.learning_rate: float = configs["learning_rate"] if learning_rate is None else learning_rate
        self.discount_factor: float = configs["discount_factor"] if discount_factor is None else discount_factor
        self.exploration_rate: float = configs["exploration_rate"] if exploration_rate is None else exploration_rate

        '''DEFAULT PARAMETERS'''
        self.sscs = sscs
        self.mobility_helper: MobilityHelper = mobility_helper
        self.tracers: list[Tracer] = tracers
        self.movement_phases: MovementPhase = movement_phases

        '''Q-LEARNING PARAMETERS'''
        self.action_space: tuple[int, ...] = tuple(i for i in range(-1, self.node_count, 1))  # -1: unallocated
        self.q_table = defaultdict(lambda: np.zeros(len(self.action_space)))  # "할당하지 않음" 포함

        '''initalize q_table(for first slot allocation)'''
        for phase in self.mobility_helper.phase_info.phases:
            for slot in range(time_slots):
                self.q_table[State(phase, slot)] = np.zeros(len(self.action_space))
                self.q_table[State(phase, slot)][slot] = np.float32(0.00001)

        self.off = False


    def turn_off(self):
        self.off = True


    def choose_action(self, current_state: State) -> int:
        '''
        :param current_state: State, 현재 상태
        :return action
        '''
        # explore
        if np.random.rand() < self.exploration_rate:
            action = self.action_space[np.random.randint(len(self.action_space))]

        # exploit
        else:
            action = self.action_space[np.argmax(self.q_table[current_state])]

        QLearningTrainer.logger.log(
            sim_time=self.sscs.env.now,
            msg=f"action is: {action}",
            level=logging.DEBUG
        )

        assert action in self.action_space

        return action


    def get_next_state(self, current_state: State, action: int) -> State:
        '''
        :param current_state: State, current state
        :param action: action(not used)
        :return next_state: next state
        '''

        if current_state.slot + 1== self.time_slots:
            return State(phase=current_state.phase, slot=-1)

        return State(phase=current_state.phase, slot=current_state.slot + 1)


    def update_q_table(self, current_state: State, action: int, reward: float, next_state: State):
        if self.off:
            return

        QLearningTrainer.logger.log(
            sim_time=self.sscs.env.now,
            msg=f"COORDINATOR: updating Q-table, state: {current_state.slot}, action: {action}, reward: {reward}",
            level=logging.INFO
        )

        # 다음 행동 중 가장 가치가 큰 행동 선택

        # 최종 행동(마지막 타임 슬롯)인 경우
        if next_state.slot == -1:
            td_target = reward
        else:
            best_next_action = np.argmax(self.q_table[next_state])
            td_target = reward + self.discount_factor * self.q_table[next_state][best_next_action]

        td_delta = td_target - self.q_table[current_state][action]

        self.q_table[current_state][action] += self.learning_rate * td_delta

        return


    def calculate_reward(self, action: int) -> float:
        if self.off:
            return 0

        # 할당되지 않은 슬롯 발견 시 약한 음의 보상
        if action == -1:
            return -0.1

        throughput = self.get_throughput(action)

        # 전송 데이터가 0인 경우 음의 보상
        if throughput == 0:
            return -1 * self.get_node_priority(action)

        reward = 0.001 * self.get_throughput(action) * self.get_node_priority(action)

        return reward


    def train(self, time_slot_index: int, allocated_node_id: int, mobility_phase: MovementPhase):
        if self.off:
            return

        QLearningTrainer.logger.log(
            sim_time=self.sscs.env.now,
            msg=f"training, time slot: {time_slot_index}, allocated: {allocated_node_id}, phase: {mobility_phase.name}",
            level=logging.INFO
        )

        current_state = State(mobility_phase, time_slot_index)

        # action = self.choose_action(current_state)                # node index(will allocate to current slot)
        action = allocated_node_id                                  # node's id that allocated at that time slot
        next_state = self.get_next_state(current_state, action)     # State(phase, slot + 1)
        reward = self.calculate_reward(action)                      # reward for taking that action

        self.update_q_table(current_state, action, reward, next_state)


    def get_time_slots(self, phase: MovementPhase) -> list[int]:
        if self.off:
            return [i for i in range(self.node_count)] + [-1 for _ in range(self.time_slots - self.node_count)]

        unallocated = -1
        time_slots = [unallocated for _ in range(self.time_slots)]

        state: State = State(phase=phase, slot=0)

        for i in range(self.time_slots):
            node: int = self.choose_action(current_state=state)

            time_slots[i] = node
            state = State(phase=state.phase, slot=state.slot + 1)

        # TODO: 스루풋 초기화 시점
        self.reset_throughput()

        return time_slots


    def detect_movement_phase(self) -> MovementPhase:
        return self.mobility_helper.current_phase


    def get_throughput(self, node_id: int) -> float:
        if node_id == -1:
            return 0
        # print(self.tracers[node_id].get_throughput())
        # TODO: 정확한 스루풋 반환
        return self.tracers[node_id].get_throughput()
        # return self.sscs.get_throughput()


    def get_node_priority(self, node_id: int) -> int:
        return self.sscs.get_priority(node_id)


    def reset_throughput(self) -> None:
        for tracer in self.tracers:
            tracer.reset()

        return

    def print_throughput(self):
        throughputs = tuple(f"node {i+1}: {len(self.tracers[i].success_tx_packet)} / {len(self.tracers[i].tx_packet)}" for i in range(len(self.tracers)))

        QLearningTrainer.logger.log(
            sim_time=self.sscs.env.now,
            msg="CURRENT ALLOCATION STAT:\n" + ", ".join(throughputs),
            level=logging.INFO
        )
