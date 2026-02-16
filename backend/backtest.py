import pandas as pd
import numpy as np
import logging
import asyncio
import sys
import os
from datetime import datetime

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.ai_core import AICore, InferenceEngine
from backend.risk_manager import RiskManager
from backend.data_collector import DataCollector

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(message)s')

class Backtester:
    def __init__(self, symbol="WIN$", n_candles=2000):
        self.symbol = symbol
        self.n_candles = n_candles
        self.ai = AICore()
        # Inicializa motor de inferência com os pesos treinados
        self.inference = InferenceEngine(model_path="backend/patchtst_weights.pth")
        self.risk = RiskManager()
        self.collector = DataCollector(symbol)
        
        # Estado da Conta Simulada
        self.balance = 2000.0
        self.initial_balance = 2000.0
        self.position = 0 # 0=Flat, 1=Buy, -1=Sell
        self.avg_price = 0.0
        self.trades = []
        # Dados para Treino do XGBoost
        self.training_data = []

    def load_data(self):
        logging.info(f"Coletando {self.n_candles} candles de {self.symbol} do MT5...")
        # DataCollector retorna DataFrame com timestamps e OHLC
        df = self.collector.get_h1_history(self.n_candles)
        if df is None or df.empty:
            logging.error("ERRO: Não foi possível obter dados. Certifique-se que o MT5 está aberto e conectado.")
            return None
            
        # Normalização básica necessária para o PatchTST (Z-Score)
        # Em backtest real, o Z-Score deve ser janelado para não vazar dados futuros
        # Aqui usamos o método do DataCollector que já faz rolling window
        df = self.collector.apply_zscore(df)
        return df

    async def run(self):
        logging.info("Iniciando Backtest...")
        data = self.load_data()
        if data is None:
            return

        logging.info(f"Dados carregados: {len(data)} candles.")
        logging.info("Simulando execução barra-a-barra...")

        # Warmup do modelo (precisa de sequencia inicial)
        seq_len = 60
        
        for i in range(seq_len, len(data)):
            # Dados disponíveis até o momento (janela deslizante)
            # Para performance, o ideal seria batch, mas aqui simulamos o loop realtime
            current_slice = data.iloc[i-seq_len:i].copy()
            current_candle = data.iloc[i]
            
            # 1. Indicadores de Mercado (ATR simulado)
            # Recalculando ATR com os dados disponíveis até 'i'
            # (Simplificação: usando rolling do pandas no slice atual)
            # 1. Indicadores de Mercado (ATR simulado)
            # ATR Médio da janela de 60 períodos
            window_high_low = current_slice['high'] - current_slice['low']
            avg_atr = window_high_low.mean()
            
            # ATR Instantâneo (Range do último candle fechado na fatia)
            current_atr = window_high_low.iloc[-1]
            
            # 2. IA - Predição
            # Mockando OBI por enquanto pois não temos histórico de Order Book
            # Em backtest avançado, precisaria gravar o book também.
            mock_obi = 0.0 
            
            # Detectar Regime (usando std da janela)
            regime = self.ai.detect_regime(current_slice['close'].std(), mock_obi)
            
            # Predição do Modelo (Inferência real)
            # O predict espera dataframe com coluna 'close' (ou zscore)
            ai_confidence = await self.inference.predict(current_slice)

            
            # Mock de sentimento (aleatório ou neutro, já que não temos news históricas)
            mock_sentiment = 0.0 
            
            decision = self.ai.calculate_decision(mock_obi, mock_sentiment, ai_confidence)
            score = decision["score"]
            direction = decision["direction"]
            
            # 3. Gestão de Risco
            market_cond = self.risk.validate_market_condition(regime, current_atr, avg_atr)
            risk_ok, _ = self.risk.check_daily_loss(self.balance - self.initial_balance, self.initial_balance)
            
            allowed = (score >= 85 and market_cond["allowed"] and risk_ok)
            
            # --- COLETA DE DADOS PARA XGBOOST (TRIPLE BARRIER METHOD) ---
            # Paper: Advances in Financial Machine Learning (Lopez de Prado)
            # Labeling: 1 (Profit), -1 (Stop), 0 (Time Limit)
            
            look_ahead = 10 # Barreira de Tempo (10 candles)
            if i + look_ahead < len(data):
                future_slice = data.iloc[i+1 : i+look_ahead+1]
                
                # Barreiras Dinâmicas via ATR
                # Profit: 2x Volatilidade | Stop: 1x Volatilidade
                barrier_up = current_candle['close'] + (2.0 * current_atr)
                barrier_down = current_candle['close'] - (1.0 * current_atr)
                
                label = self._calculate_triple_barrier(current_candle['close'], barrier_up, barrier_down, future_slice)
                
                # Salvar apenas se houver uma oportunidade clara detectada pela IA ou Risco
                # Queremos treinar o XGBoost para filtrar os FP (Falsos Positivos) do PatchTST
                if score >= 70: # Baixei para 70 para ter mais massa de dados de "quase acertos"
                    self.training_data.append({
                        "obi": mock_obi,
                        "sentiment": mock_sentiment,
                        "patchtst_score": ai_confidence,
                        "volatility": current_atr,
                        "avg_volatility": avg_atr,
                        "regime": regime,
                        "hour": current_candle.name.hour if isinstance(current_candle.name, pd.Timestamp) else 0,
                        "score": score,
                        "direction": 1 if direction == "BUY" else -1,
                        "target": label # 1 (Gain), -1 (Loss), 0 (Time/Neutral)
                    })
            # ----------------------------------------------

            # 4. Execução (Simulação)
            target_price = current_candle['close'] # Assumimos execução no fechamento (ou abertura do próximo)
            
            # Fechamento de Posição (se houver sinal contrário ou stop/gain)
            # Simplificação: Sair se o sinal inverter ou score cair
            if self.position != 0:
                pnl = (target_price - self.avg_price) * self.position * 0.20 # R$ 0.20 por ponto (WDO/WIN ajustado)
                # Se posição comprada e sinal venda (ou vice versa) -> Zerar
                if (self.position == 1 and direction == "SELL") or (self.position == -1 and direction == "BUY"):
                    self.close_position(target_price, pnl, "Sinal Invertido")
                
                # TODO: Implementar simulador de Stop Loss / Take Profit intra-candle
                
            # Abertura de Posição
            if self.position == 0 and allowed:
                if direction == "BUY":
                    self.open_position(1, target_price)
                elif direction == "SELL":
                    self.open_position(-1, target_price)
            
            self.equity_curve.append(self.balance)
            
            if i % 100 == 0:
                print(f"Processado: {i}/{len(data)} | Saldo: {self.balance:.2f}", end="\r")

        print("\nBacktest Concluído.")
        self.generate_report()
        self.save_training_data()

    def save_training_data(self):
        """Salva os dados coletados para treinar o XGBoost."""
        if not self.training_data:
            logging.warning("Nenhum dado de treino coletado (nenhum score > 75).")
            return
            
        df = pd.DataFrame(self.training_data)
        output_path = "backend/xgb_training_data.csv"
        df.to_csv(output_path, index=False)
        logging.info(f"Dados de treino salvos em: {output_path} ({len(df)} amostras)")

    def open_position(self, side, price):
        self.position = side
        self.avg_price = price
        # logging.info(f"OPEN {'BUY' if side==1 else 'SELL'} @ {price}")

    def close_position(self, price, pnl, reason):
        self.balance += pnl
        self.position = 0
        self.avg_price = 0
        self.trades.append({
            "pnl": pnl,
            "reason": reason
        })
        if pnl > 0: self.wins += 1
        else: self.losses += 1
        # logging.info(f"CLOSE ({reason}) PnL: {pnl:.2f} | Saldo: {self.balance:.2f}")

    def _calculate_triple_barrier(self, entry_price, barrier_up, barrier_down, future_slice):
        """
        Método das Três Barreiras (Lopez de Prado):
        Retorna 1 se tocar 1º na Barreira Superior (Gain).
        Retorna -1 se tocar 1º na Barreira Inferior (Loss).
        Retorna 0 se não tocar em nenhuma até o fim da janela (Time Limit).
        """
        for _, row in future_slice.iterrows():
            if row['high'] >= barrier_up:
                return 1
            if row['low'] <= barrier_down:
                return -1
        return 0

    def calculate_psr(self, returns_series, benchmark_sharpe=0.0):
        """
        Probabilistic Sharpe Ratio (PSR).
        Valida a robustez estatística do Sharpe Ratio.
        """
        if len(returns_series) < 2:
            return 0.0
            
        sr_est = returns_series.mean() / returns_series.std() if returns_series.std() != 0 else 0
        skew = returns_series.skew()
        kurt = returns_series.kurtosis()
        n = len(returns_series)
        
        # Fórmula PSR aproximada
        numerator = (sr_est - benchmark_sharpe) * np.sqrt(n - 1)
        denominator = np.sqrt(1 - skew * sr_est + ((kurt - 1) / 4) * sr_est**2)
        
        if denominator == 0:
            return 0.0
            
        # Retorna probabilidade normal cumulativa (Z-score)
        # Aqui simplificamos retornando o Score Z. > 1.645 = 95% Confiança
        psr_z = numerator / denominator
        return psr_z

    def generate_report(self):
        total_trades = self.wins + self.losses
        win_rate = (self.wins / total_trades * 100) if total_trades > 0 else 0
        
        # Calcular PSR baseado nos retornos trade a trade
        trade_returns = pd.Series([t['pnl'] for t in self.trades])
        psr = self.calculate_psr(trade_returns)
        psr_confidence = "ALTA (>95%)" if psr > 1.645 else "BAIXA"

        print("\n" + "="*40)
        print("          RELATÓRIO DE PERFORMANCE")
        print("="*40)
        print(f"Saldo Inicial:   R$ {self.initial_balance:.2f}")
        print(f"Saldo Final:     R$ {self.balance:.2f}")
        print(f"Lucro Líquido:   R$ {self.balance - self.initial_balance:.2f}")
        print(f"Total Trades:    {total_trades}")
        print(f"Taxa de Acerto:  {win_rate:.1f}%")
        print(f"PSR (Z-Score):   {psr:.2f} ({psr_confidence})")
        print("="*40)

if __name__ == "__main__":
    backtester = Backtester(symbol="WIN$", n_candles=1000)
    asyncio.run(backtester.run())
