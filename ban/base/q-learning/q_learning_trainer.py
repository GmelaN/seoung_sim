import enum
import random
import numpy as np

from dataclasses import dataclass

from tqdm.auto import tqdm

from ban.base.tracer import Tracer
from ban.device.sscs import BanSSCS

class MovementPhase(enum):
    PHASE_0: int
    PHASE_1: int
    PHASE_2: int

# class DistanceLevel(enum):
#     VERY_CLOSE: int
#     CLOSE: int
#     NEUTRAL: int
#     FAR: int
#     VERY_FAR: int


@dataclass
class State:
    # distance_level: DistanceLevel
    movement_phase: MovementPhase
    time_slot_allocations: list[int]


class QLearningTrainer:
    def __init__(self, node_count: int, sscs: BanSSCS, learning_rate: float = 0.5, discount_factor: float = 0.9, exploration_rate: float = 0.1):
        self.node_count: int = node_count        # WBAN에서 현재 에이전트에 연결되어 있는 노드의 수
        self.sscs: BanSSCS = sscs                    # 코디네이터의 SSCS
        self.tracer: Tracer = Tracer()      # 패킷 정보를 담을 Tracer

        # 학습 파라미터
        self.alpha: float = learning_rate
        self.gamma: float = discount_factor
        self.epsilon: float = exploration_rate

        # 학습 공간
        self.actions: list = self.get_initalized_actions()
        # TODO: q-table 차원 적절하게 수정
        self.q_table: np.ndarray = np.zeros(1)



    def choose_acion(self, current_state):
        '''
        epsilon-greedy 전략으로 행동을 결정합니다.
        :param current_state: 현재 state
        :return: 현재 state에서 취할 action
        '''

        # 탐험
        if np.random.rand() < self.epsilon:
            action = np.random.choice(self.actions)

        # 탐색
        else:
            state_actions = self.q_table[current_state, :]
            action = self.actions[np.argmax(state_actions)]

        return action


    def get_current_state(self) -> State:
        '''
        현재 노드 간 거리,
        :return:
        '''
        # distance_level: DistanceLevel = self.measure_distance_level()
        movement_phase: MovementPhase = self.detect_movement_phase()
        time_slot_allocations: list[int] = [-1 for _ in range(self.node_count)]

        return State(
            # distance_level=distance_level,
            movement_phase=movement_phase,
            time_slot_allocations=time_slot_allocations
        )


    def get_next_state(self, current_state: State, action: tuple[int, int]) -> State:
        '''
        입력으로 받은 현재 state에 action을 반영한 next_state를 계산합니다.
        :param current_state: State, 현재 state
        :param action: tuple(node_id, time_slot_id), 현재 state에 가할 action
        :return: State, 다음 state
        '''

        node_id, time_slot_id = action

        next_state: State = State(
            # distance_level=current_state.distance_level,
            movement_phase=current_state.movement_phase,
            time_slot_allocations=current_state.time_slot_allocations.copy()
        )

        next_state.time_slot_allocations[time_slot_id] = node_id

        # 여기에서 추가적으로 환경 변화를 모의할 수 있습니다.
        # 예를 들어, 노드 간 거리 또는 움직임 패턴의 변화 등을 반영할 수 있습니다.
        # next_state.distance_level = self.measure_distance_level()
        # next_state.movement_phase = self.detect_movement_phase()

        return next_state


    def calculate_reward(self, current_state, action):
        pass


    def update_q_table(self, current_state, action, reward, next_state):
        pass

    def train(self):
        pass


    def get_initalized_actions(self):
        actions = []
        for node in range(self.node_count):
            for slot in range(self.node_count):
                actions.append((node, slot))

        return actions


    def measure_distance_level(self) -> DistanceLevel:
        pass


    def detect_movement_phase(self) -> MovementPhase:
        pass
