from keras.layers import Input, Dense, Dropout, Conv2D, Flatten, concatenate, LSTM
from keras.models import Sequential, Model
from collections import deque
import random
import numpy as np
import keras
import tensorflow as tf
from tqdm.auto import tqdm
import pickle
import os

NUM_CHANNELS = 1
NUM_ACTIONS = 15


class DQNTrainer:
    def __init__(self):
        self.env = None
        self.net_env = None  # BAN environment
        self.data_list = list()

        # DQN parameters
        self.episodes = 2000
        self.epsilon = 1.0
        self.min_epsilon = 0.1
        self.exploration_ratio = 0.5
        self.max_steps = 300
        self.save_dir = 'checkpoints'
        self.enable_save = False
        self.render_freq = 500
        self.enable_render = True
        self.render_fps = 20
        self.save_freq = 500
        self.gamma = 0.99
        self.batch_size = 64
        self.min_replay_memory_size = 1000
        self.replay_memory_size = 100000
        self.target_update_freq = 5
        self.seed = 42

        self.set_random_seed(self.seed)

        if self.enable_save and not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        # Create model
        self.model = self._create_model()
        self.target_model = self._create_model()
        self.target_model.set_weights(self.model.get_weights())
        self.model.summary()

        self.replay_memory = deque(maxlen=self.replay_memory_size)
        self.target_update_counter = 0

        self.current_episode = 0

        self.epsilon_decay = (self.epsilon - self.min_epsilon) / (self.exploration_ratio * self.episodes)
        self.pbar = tqdm(
            initial=self.current_episode,
            total=self.episodes,
            unit='episodes',
            position=0,
            desc="TRAIN STATUS",
            leave=True
        )

    def _create_model(self):
        # Create a neural network using Sequential model
        model = Sequential([
            Dense(24, activation='relu', input_dim=2),  # if the input (state) is one-dimension array, input_dim=2
            Dense(24, activation='relu'),
            Dense(NUM_ACTIONS)
        ])
        model.compile(optimizer='rmsprop', loss='mse')

        return model

    def update_replay_memory(self, current_state, action, reward, next_state, done):
        self.replay_memory.append((current_state, action, reward, next_state, done))

    def get_q_values(self, x):
        # 신경망으로 예측된 Q값 반환
        return self.model.predict(x, verbose=0)

    def train(self):
        # Q값을 예측하는 신경망 학습
        # guarantee the minimum number of samples
        if len(self.replay_memory) < self.min_replay_memory_size:
            return

        # get current q values and next q values
        samples = random.sample(self.replay_memory, self.batch_size)
        current_input = np.stack([sample[0] for sample in samples])
        current_q_values = self.model.predict(current_input,
                                              verbose=0)  # return current Q-values (behavior (off-policy))
        next_input = np.stack([sample[3] for sample in samples])
        next_q_values = self.target_model.predict(next_input, verbose=0)  # return target Q-values (target (off-policy))

        # update q values
        for i, (current_state, action, reward, _, done) in enumerate(samples):
            if done:
                next_q_value = reward
            else:
                next_q_value = reward + self.gamma * np.max(next_q_values[i])
            current_q_values[i, action] = next_q_value

        # fit model
        hist = self.model.fit(current_input, current_q_values, batch_size=self.batch_size, verbose=0, shuffle=False)
        loss = hist.history['loss'][0]
        return loss

    def increase_target_update_counter(self):
        self.target_update_counter += 1
        if self.target_update_counter >= self.target_update_freq:
            self.target_model.set_weights(self.model.get_weights())
            self.target_update_counter = 0

    def save(self, model_filepath, target_model_filepath):
        self.model.save(model_filepath)
        self.target_model.save(target_model_filepath)

    def load(self, model_filepath, target_model_filepath):
        self.model = keras.models.load_model(model_filepath)
        self.target_model = keras.models.load_model(target_model_filepath)

    # ############### Q-learning trainer ######################
    def set_random_seed(self, seed):
        random.seed(seed)
        np.random.seed(seed)
        os.environ['PYTHONHASHSEED'] = str(seed)
        tf.random.set_seed(seed)

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

    def trainer_save(self, suffix):
        self.save(
            self.save_dir + '/model_{}.h5'.format(suffix),
            self.save_dir + '/target_model_{}.h5'.format(suffix)
        )

        dic = {
            'replay_memory': self.replay_memory,
            'target_update_counter': self.target_update_counter,
            'current_episode': self.current_episode,
            'epsilon': self.epsilon,
        }

        with open(self.save_dir + '/training_info_{}.pkl'.format(suffix), 'wb') as fout:
            pickle.dump(dic, fout)

    def trainer_load(self, suffix):
        self.load(
            self.save_dir + '/model_{}.h5'.format(suffix),
            self.save_dir + '/target_model_{}.h5'.format(suffix)
        )

        with open(self.save_dir + '/training_info_{}.pkl'.format(suffix), 'rb') as fin:
            dic = pickle.load(fin)

        self.replay_memory = dic['replay_memory']
        self.target_update_counter = dic['target_update_counter']
        self.current_episode = dic['current_episode']
        self.epsilon = dic['epsilon']

    # ############## Q-learning methods end ##################

    def set_env(self, env):
        self.env = env

    def get_env(self):
        return self.env

    def set_sscs(self, m_sscs):
        self.net_env = m_sscs

    def get_sscs(self):
        return self.net_env

    def get_data(self, event):
        self.data_list = self.net_env.get_data()
        # print('get a packet in the dqn_trainer (agent) at time:', self.env.now, len(self.data_list))
