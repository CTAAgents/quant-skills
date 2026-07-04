"""
贵金属交易决策辅助系统 - 强化学习模块
使用强化学习优化策略选择
"""

import json
import numpy as np
from datetime import datetime, timedelta

class ReinforcementLearning:
    def __init__(self, n_states=5, n_actions=8):
        self.n_states = n_states  # 状态数（Regime数）
        self.n_actions = n_actions  # 动作数（策略数）
        self.q_table = np.zeros((n_states, n_actions))
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.epsilon = 0.1  # 探索率

    def choose_action(self, state):
        """选择动作（ε-贪心策略）"""
        if np.random.random() < self.epsilon:
            # 探索：随机选择动作
            return np.random.randint(self.n_actions)
        else:
            # 利用：选择Q值最大的动作
            return np.argmax(self.q_table[state])

    def update_q_table(self, state, action, reward, next_state):
        """更新Q表"""
        # Q-learning更新公式
        current_q = self.q_table[state, action]
        next_max_q = np.max(self.q_table[next_state])
        new_q = current_q + self.learning_rate * (reward + self.discount_factor * next_max_q - current_q)
        self.q_table[state, action] = new_q

    def train(self, n_episodes=1000):
        """训练强化学习模型"""
        rewards_history = []

        for episode in range(n_episodes):
            state = np.random.randint(self.n_states)  # 随机初始状态
            total_reward = 0

            for step in range(100):  # 每个episode最多100步
                # 选择动作
                action = self.choose_action(state)

                # 执行动作，获取奖励和下一个状态
                reward = self._get_reward(state, action)
                next_state = self._get_next_state(state, action)

                # 更新Q表
                self.update_q_table(state, action, reward, next_state)

                state = next_state
                total_reward += reward

            rewards_history.append(total_reward)

            if episode % 100 == 0:
                avg_reward = np.mean(rewards_history[-100:])
                print(f"  Episode {episode}/{n_episodes}, Avg Reward: {avg_reward:.2f}")

        return rewards_history

    def _get_reward(self, state, action):
        """获取奖励"""
        # 简化的奖励函数
        # 根据状态和动作的匹配程度给予奖励
        optimal_actions = {
            0: [0, 3, 5],  # R1: 宏观利率波段、均线顺势、突破追单
            1: [4, 7],     # R2: 区间高抛低吸、波动率交易
            2: [0, 3, 5],  # R3: 宏观利率波段、均线顺势、突破追单
            3: [1],         # R4: 央行抄底
            4: []           # R5: 只平仓不开新仓
        }

        if action in optimal_actions.get(state, []):
            return 1.0  # 正确的动作
        else:
            return -0.1  # 错误的动作

    def _get_next_state(self, state, action):
        """获取下一个状态"""
        # 简化的状态转移
        # 根据当前状态和动作，随机转移到下一个状态
        return np.random.randint(self.n_states)

    def predict(self, state):
        """预测最佳动作"""
        return np.argmax(self.q_table[state])

    def get_policy(self):
        """获取策略"""
        policy = {}
        for state in range(self.n_states):
            policy[state] = np.argmax(self.q_table[state])
        return policy

class PolicyGradient:
    """策略梯度算法"""

    def __init__(self, n_states=5, n_actions=8):
        self.n_states = n_states
        self.n_actions = n_actions
        self.policy_network = PolicyNetwork(n_states, n_actions)
        self.learning_rate = 0.01

    def choose_action(self, state):
        """选择动作"""
        # 计算策略概率
        probs = self.policy_network.forward(state)

        # 根据概率选择动作
        return np.random.choice(self.n_actions, p=probs)

    def train(self, n_episodes=1000):
        """训练策略梯度模型"""
        rewards_history = []

        for episode in range(n_episodes):
            states = []
            actions = []
            rewards = []

            state = np.random.randint(self.n_states)

            for step in range(100):
                # 选择动作
                action = self.choose_action(state)

                # 执行动作
                reward = self._get_reward(state, action)
                next_state = self._get_next_state(state, action)

                # 记录经验
                states.append(state)
                actions.append(action)
                rewards.append(reward)

                state = next_state

            # 计算折扣奖励
            discounted_rewards = self._discount_rewards(rewards)

            # 更新策略网络
            self.policy_network.update(states, actions, discounted_rewards, self.learning_rate)

            total_reward = sum(rewards)
            rewards_history.append(total_reward)

            if episode % 100 == 0:
                avg_reward = np.mean(rewards_history[-100:])
                print(f"  Episode {episode}/{n_episodes}, Avg Reward: {avg_reward:.2f}")

        return rewards_history

    def _get_reward(self, state, action):
        """获取奖励"""
        optimal_actions = {
            0: [0, 3, 5],
            1: [4, 7],
            2: [0, 3, 5],
            3: [1],
            4: []
        }

        if action in optimal_actions.get(state, []):
            return 1.0
        else:
            return -0.1

    def _get_next_state(self, state, action):
        """获取下一个状态"""
        return np.random.randint(self.n_states)

    def _discount_rewards(self, rewards):
        """计算折扣奖励"""
        discounted = np.zeros_like(rewards, dtype=float)
        cumulative = 0
        for t in reversed(range(len(rewards))):
            cumulative = rewards[t] + 0.99 * cumulative
            discounted[t] = cumulative
        return discounted

class PolicyNetwork:
    """策略网络"""

    def __init__(self, n_states, n_actions):
        self.n_states = n_states
        self.n_actions = n_actions
        self.weights = np.random.randn(n_states, n_actions) * 0.01

    def forward(self, state):
        """前向传播"""
        # 简化的策略网络
        logits = self.weights[state]
        probs = self._softmax(logits)
        return probs

    def update(self, states, actions, rewards, learning_rate):
        """更新网络"""
        for state, action, reward in zip(states, actions, rewards):
            # 简化的梯度更新
            self.weights[state, action] += learning_rate * reward

    def _softmax(self, x):
        """Softmax激活函数"""
        exp_x = np.exp(x - np.max(x))
        return exp_x / np.sum(exp_x)

def test_reinforcement_learning():
    """测试强化学习"""
    print("\n" + "="*80)
    print("强化学习测试")
    print("="*80)

    # 测试Q-learning
    print("\n1. 测试Q-learning...")
    ql = ReinforcementLearning(n_states=5, n_actions=8)
    rewards = ql.train(n_episodes=500)
    print(f"  最终平均奖励: {np.mean(rewards[-100:]):.2f}")
    print(f"  策略: {ql.get_policy()}")

    # 测试策略梯度
    print("\n2. 测试策略梯度...")
    pg = PolicyGradient(n_states=5, n_actions=8)
    rewards = pg.train(n_episodes=500)
    print(f"  最终平均奖励: {np.mean(rewards[-100:]):.2f}")

    # 测试预测
    print("\n3. 测试预测...")
    for state in range(5):
        action = ql.predict(state)
        print(f"  状态 {state} -> 动作 {action}")

    return ql, pg

if __name__ == "__main__":
    test_reinforcement_learning()
