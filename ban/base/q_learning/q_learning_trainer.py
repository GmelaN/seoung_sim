import enum
import logging
import random
from collections import namedtuple, defaultdict
from typing import Dict

import numpy as np

from dataclasses import dataclass

from tqdm.auto import tqdm

from ban.base.helper.mobility_helper import MovementPhase, MobilityHelper
from ban.base.logging.log import SeoungSimLogger
from ban.base.tracer import Tracer




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
            learning_rate: float = 0.5,
            discount_factor: float = 0.9,
            exploration_rate: float = 0.7,
    ):
        self.sscs = sscs
        self.node_count: int = node_count
        self.time_slots: int = time_slots
        self.mobility_helper: MobilityHelper = mobility_helper
        self.tracers: list[Tracer] = tracers

        self.movement_phases: MovementPhase = movement_phases

        self.learning_rate: float = learning_rate
        self.discount_factor: float = discount_factor
        self.exploration_rate:float = exploration_rate

        # -1: unallocated
        self.action_space: tuple[int, ...] = tuple(i for i in range(-1, self.node_count, 1))

        self.q_table = defaultdict(lambda: np.zeros(node_count))


    def choose_action(self, current_state: State) -> int:
        '''
        :param current_state: State, 현재 상태
        :return action
        '''
        # explore
        if np.random.rand() < self.exploration_rate:
            action = self.action_space[np.random.randint(self.node_count)]

        # exploit
        else:
            action = self.action_space[np.argmax(self.q_table[current_state])]

        QLearningTrainer.logger.log(msg=f"action is: {action}")
        return action


    def get_next_state(self, current_state: State, action: int) -> State:
        '''
        :param current_state: State, current state
        :param action: action(not used)
        :return next_state: next state
        '''

        return State(phase=current_state.phase, slot=current_state.slot + 1)


    def update_q_table(self, current_state: State, action: int, reward: float, next_state: State):
        # 다음 행동 중 가장 가치가 큰 행동
        best_next_action = np.argmax(self.q_table[next_state])

        td_target = reward + self.discount_factor * self.q_table[next_state][best_next_action]
        td_delta = td_target - self.q_table[current_state][action]
        self.q_table[current_state][action] += self.learning_rate * td_delta


    def calculate_reward(self, action: int) -> float:
        throughput = self.get_throughput(action)

        # 전송 데이터가 0인 경우 음의 보상
        if throughput == 0:
            return -1

        return self.get_throughput(action) * self.get_node_priority(action)


    def train(self, iterations: int = 10):
        for _ in range(iterations):
            current_state = State(self.detect_movement_phase(), 0)

            for _ in range(self.time_slots):
                action = self.choose_action(current_state)                  # node index(will allocate to current slot)
                next_state = self.get_next_state(current_state, action)     # State(phase, slot + 1)
                reward = self.calculate_reward(action)                      # reward for taking that action
                self.update_q_table(current_state, action, reward, next_state)
                current_state = next_state


    def get_time_slots(self, phase: MovementPhase) -> list[int]:
        # TODO: 스루풋 초기화 시점
        # self.sscs.reset_throughput()
        for tracer in self.tracers:
            tracer.reset()

        unallocated = -1
        time_slots = [unallocated for _ in range(self.time_slots)]

        state: State = State(phase=phase, slot=0)

        for i in range(self.time_slots):
            node: int = np.argmax(self.q_table[state])

            if node == 0:
                node = -1

            time_slots[i] = node
            state = State(phase=state.phase, slot=state.slot + 1)

        # 타임 슬롯이 모두 빈 경우 - 기본값으로 설정
        if max(time_slots) == -1:
            time_slots = [i + 1 for i in range(self.time_slots)]

        return time_slots


    def detect_movement_phase(self) -> MovementPhase:
        return self.mobility_helper.current_phase


    def get_throughput(self, node_id: int) -> float:
        print(self.tracers[node_id].get_throughput())
        # TODO: 정확한 스루풋 반환
        return self.tracers[node_id].get_throughput()
        # return self.sscs.get_throughput()


    def get_node_priority(self, node_id: int) -> int:
        return self.sscs.get_priority(node_id)
