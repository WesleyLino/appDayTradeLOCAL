import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np


class ActorCritic(nn.Module):
    def __init__(self, input_dim, n_actions):
        super(ActorCritic, self).__init__()

        # Actor: Decide qual ação tomar (Probabilidades)
        self.actor = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.Tanh(),
            nn.Linear(128, 64),
            nn.Tanh(),
            nn.Linear(64, n_actions),
            nn.Softmax(dim=-1),
        )

        # Critic: Avalia o quão bom é o estado atual (Value Function)
        self.critic = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.Tanh(),
            nn.Linear(128, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
        )

    def forward(self, state):
        # state dimensions: [batch, input_dim]
        probs = self.actor(state)
        value = self.critic(state)
        return probs, value


class PPOAgent:
    """
    Agente Autônomo usando PPO (Proximal Policy Optimization).
    Algoritmo State-of-the-Art para Reinforcement Learning contínuo/discreto.
    """

    def __init__(self, input_dim, n_actions, lr=0.0003, gamma=0.99, eps_clip=0.2):
        self.gamma = gamma
        self.eps_clip = eps_clip
        self.device = torch.device("cpu")  # Leve para rodar local enquanto MT5 opera

        self.policy = ActorCritic(input_dim, n_actions).to(self.device)
        self.optimizer = optim.Adam(self.policy.parameters(), lr=lr)
        self.policy_old = ActorCritic(input_dim, n_actions).to(self.device)
        self.policy_old.load_state_dict(self.policy.state_dict())

        self.MseLoss = nn.MSELoss()

    def select_action(self, state):
        """Retorna uma ação baseada no estado atual."""
        state = torch.FloatTensor(state).to(self.device)
        with torch.no_grad():
            probs, _ = self.policy_old(state)

        # Sampling estocástico
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()

        return action.item(), dist.log_prob(action)

    def update(self, memory):
        """
        Treina o agente com um batch de experiências (PPO update).
        memory: lista de (states, actions, log_probs, rewards, is_terminals)
        """
        if not memory:
            return

        # Desempacotar memória
        rewards = []
        discounted_reward = 0
        for reward, is_terminal in zip(
            reversed(memory["rewards"]), reversed(memory["is_terminals"])
        ):
            if is_terminal:
                discounted_reward = 0
            discounted_reward = reward + (self.gamma * discounted_reward)
            rewards.insert(0, discounted_reward)

        rewards = torch.tensor(rewards, dtype=torch.float32).to(self.device)
        # Normalizar rewards para estabilidade
        rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-7)

        old_states = torch.tensor(np.array(memory["states"]), dtype=torch.float32).to(
            self.device
        )
        old_actions = torch.tensor(memory["actions"], dtype=torch.float32).to(
            self.device
        )
        old_log_probs = torch.tensor(memory["log_probs"], dtype=torch.float32).to(
            self.device
        )

        # Loop de Otimização (K epochs)
        for _ in range(4):
            # Avaliar actions antigas com a nova política
            probs, state_values = self.policy(old_states)
            dist = torch.distributions.Categorical(probs)

            log_probs = dist.log_prob(old_actions)
            dist_entropy = dist.entropy()
            state_values = torch.squeeze(state_values)

            # Razão de probabilidade (r_theta)
            ratios = torch.exp(log_probs - old_log_probs)

            # Loss do Surrogate
            advantages = rewards - state_values.detach()
            surr1 = ratios * advantages
            surr2 = (
                torch.clamp(ratios, 1 - self.eps_clip, 1 + self.eps_clip) * advantages
            )

            # Loss Total: Actor loss + Critic loss + Entropy bonus
            loss = (
                -torch.min(surr1, surr2)
                + 0.5 * self.MseLoss(state_values, rewards)
                - 0.01 * dist_entropy
            )

            self.optimizer.zero_grad()
            loss.mean().backward()
            self.optimizer.step()

        # Atualizar política antiga
        self.policy_old.load_state_dict(self.policy.state_dict())
        return loss.mean().item()
