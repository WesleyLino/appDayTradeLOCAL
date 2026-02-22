import numpy as np
import random

class DayTradeEnv:
    """
    Ambiente de Reinforcement Learning customizado para Day Trade (B3/WIN).
    Simula uma interface Gym (reset, step) sem depender da biblioteca gym pesada.
    
    State Space (Observação):
    - Janela de Candles (Close, High, Low, Volatility) normalizada
    - OBI (Order Book Imbalance)
    - Sentiment Score
    - Posição Atual (Flat, Long, Short)
    - Lucro/Prejuízo da Posição Atual
    
    Action Space (Discreto):
    0: Hold (Manter/Nada)
    1: Buy (Comprar/Virar a mão para Long)
    2: Sell (Vender/Virar a mão para Short)
    3: Zerar (Close Position)
    """
    def __init__(self, data_feed, initial_balance=2000.0):
        self.data_feed = data_feed # DataFrame com histórico
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = 0 # 0=Flat, 1=Long, -1=Short
        self.entry_price = 0.0
        self.current_step = 0
        self.window_size = 60
        self.fee_per_contract = 0.25 # Custo estimado spread+taxas
        
    def reset(self):
        """Reinicia o episódio em um ponto aleatório do histórico."""
        self.balance = self.initial_balance
        self.position = 0
        self.entry_price = 0.0
        
        # Começar em um ponto onde tenhamos histórico suficiente
        self.current_step = random.randint(self.window_size, len(self.data_feed) - 200)
        return self._get_observation()
        
    def _get_observation(self):
        """Monta o vetor de estado (Tensor input para a Rede Neural)."""
        idx = self.current_step
        window = self.data_feed.iloc[idx-self.window_size : idx]
        
        # 1. Market Data Normalizado (Z-Score local)
        closes = window['close'].values
        mean = closes.mean()
        std = closes.std() + 1e-8
        norm_closes = (closes - mean) / std
        
        # 2. Features Extras (Se existirem no DF)
        obi = window['obi'].iloc[-1] if 'obi' in window else 0.5
        sentiment = window['sentiment'].iloc[-1] if 'sentiment' in window else 0.0
        
        # 3. Estado da Conta
        # PnL latente normalizado (para a IA saber se está ganhando ou perdendo)
        current_price = self.data_feed.iloc[idx]['close']
        unrealized_pnl = 0.0
        if self.position != 0:
            unrealized_pnl = (current_price - self.entry_price) * self.position
            
        # Concatenar tudo em um vetor 1D
        # [60 closes, obi, sentiment, position, unrealized_pnl]
        obs = np.concatenate((
            norm_closes, 
            [obi, sentiment, self.position, unrealized_pnl/100.0] # Normalizando PnL grosseiramente
        ))
        return obs
        
    def step(self, action):
        """Executa uma ação no ambiente e retorna (next_state, reward, done)."""
        current_price = self.data_feed.iloc[self.current_step]['close']
        self.current_step += 1
        done = False
        reward = 0.0
        
        # Próximo preço (para calcular PnL imediato)
        next_price = self.data_feed.iloc[self.current_step]['close']
        
        # Lógica de Execução
        if action == 1: # BUY
            if self.position == 1:
                pass # Já comprado, mantem
            elif self.position == -1:
                # Reversão (Short -> Long)
                pnl = (current_price - self.entry_price) * -1
                reward += pnl - (2 * self.fee_per_contract)
                self.balance += pnl
                self.position = 1
                self.entry_price = current_price
            else: # Flat -> Long
                self.position = 1
                self.entry_price = current_price
                reward -= self.fee_per_contract # Custo de entrada
                
        elif action == 2: # SELL
            if self.position == -1:
                pass 
            elif self.position == 1:
                # Reversão (Long -> Short)
                pnl = (current_price - self.entry_price) * 1
                reward += pnl - (2 * self.fee_per_contract)
                self.balance += pnl
                self.position = -1
                self.entry_price = current_price
            else:
                self.position = -1
                self.entry_price = current_price
                reward -= self.fee_per_contract
                
        elif action == 3: # CLOSE (Zerar)
            if self.position != 0:
                pnl = (current_price - self.entry_price) * self.position
                reward += pnl - self.fee_per_contract
                self.balance += pnl
                self.position = 0
                self.entry_price = 0.0
                
        elif action == 0: # HOLD
            # Recompensa por estar na direção certa (Shaping Reward)
            if self.position != 0:
                step_pnl = (next_price - current_price) * self.position
                reward += step_pnl * 0.1 # Pequeno incentivo para segurar tendência
                
        # Condições de Término
        if self.balance < self.initial_balance * 0.8: # Quebrou 20%
            done = True
            reward -= 100 # Punição forte
            
        if self.current_step >= len(self.data_feed) - 1:
            done = True
            
        return self._get_observation(), reward, done, {}
