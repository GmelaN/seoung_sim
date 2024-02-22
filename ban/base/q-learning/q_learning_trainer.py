import random
import numpy as np
from tqdm.auto import tqdm

from ban.base.tracer import Tracer

NUM_CHANNELS = 1
NUM_ACTIONS = 15

class QLearningTrainer:
    def __init__(self, node_count: int):
        # WBAN에서 현재 에이전트에 연결되어 있는 노드의 수
        self.node_count = node_count

        self.env = None
        self.net_env = None  # BAN environment
        self.data_list = list()

        self.tracer: Tracer = Tracer()

        self.current_episode = 0

        self.pbar = tqdm(
            initial=self.current_episode,
            total=self.episodes,
            unit='episodes',
            position=0,
            desc="TRAIN STATUS",
            leave=True
        )

    def get_q_values(self, x):
        # 신경망으로 예측된 Q값 반환
        return self.model.predict(x, verbose=0)

    def increase_target_update_counter(self):
        self.target_update_counter += 1
        if self.target_update_counter >= self.target_update_freq:
            self.target_model.set_weights(self.model.get_weights())
            self.target_update_counter = 0

    def set_observation(self, current_state, current_action, next_state, reward, steps, done) -> bool:
        if self.current_episode > self.episodes:
            # print('All the training episodes end: do nothing')
            return True

        self.update_replay_memory(current_state, current_action, reward, next_state, done)

        if done is True or steps > self.max_steps:
            self.current_episode += 1

            self.increase_target_update_counter()

            # decay epsilon
            self.epsilon = max(self.epsilon - self.epsilon_decay, self.min_epsilon)

            # update pbar
            self.pbar.update(1)

            # current episode is done
            return True
        else:
            # current episode is not done
            return False

    """
    에이전트가 다음 에피소드에 취할 액션을 선택합니다.

    :param current_state:  
    """
    def get_action(self, current_state):
        # 에피소드 반복 종료 시: 최고의 보상을 받은 행동을 선택
        if self.current_episode > self.episodes:
            action = np.argmax(self.get_q_values(np.array([current_state])))
            return action

        # epsilon에 따라 새로운 탐험을 할 것인지, 활용을 할 것인지 정함

        # 활용(Exploitation): 에이전트가 알고 있는 정보를 바탕으로 최적 행동을 선택
        if random.random() > self.epsilon:
            action = np.argmax(self.get_q_values(np.array([current_state])))

        # 탐험(Exploration): 에이전트가 무작위 행동을 선택하여 새로운 지식을 얻음
        else:
            action = np.random.randint(NUM_ACTIONS)

        return action

    def set_env(self, env):
        self.env = env
        self.tracer.set_env(env)

    def set_sscs(self, m_sscs):
        self.net_env = m_sscs

    def get_data(self, event):
        self.data_list = self.net_env.get_data()
