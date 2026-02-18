import asyncio
import pandas as pd
import numpy as np
import os
from datetime import datetime
import logging
from backend.mt5_bridge import MT5Bridge
from backend.data_labeler import apply_triple_barrier_method  # Importação SOTA

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class DataCollector:
    def __init__(self, symbol="WIN$", dataset_dir="data/sota_training"):
        self.bridge = MT5Bridge()
        self.symbol = symbol
        self.dataset_dir = dataset_dir
        self.is_running = False
        
        # Buffers em memória
        self.tick_buffer = []
        self.book_buffer = []
        
        # Garantir diretório
        if not os.path.exists(self.dataset_dir):
            os.makedirs(self.dataset_dir)

    def apply_zscore(self, df, window=20):
        """
        [SOTA] Aplica Normalização Z-Score (Rolling) para lidar com Non-Stationarity.
        x_norm = (x - mean) / std
        """
        if df is None or df.empty:
            return df
            
        df = df.copy()
        # Se tiver coluna 'close', usa ela.
        target_col = 'close' if 'close' in df.columns else df.columns[0]
        
        # Rolling stats
        rolling_mean = df[target_col].rolling(window=window).mean()
        rolling_std = df[target_col].rolling(window=window).std()
        
        # Z-Score
        df['zscore'] = (df[target_col] - rolling_mean) / (rolling_std + 1e-6)
        
        # Preencher NaNs iniciais com 0 ou ffill
        df['zscore'] = df['zscore'].fillna(0)
        
        return df

            
    async def start(self):
        """Inicia o loop de coleta de dados Híbridos (Tick + Book)."""
        if not self.bridge.connect():
            logging.error("Falha ao conectar no MT5 para coleta de dados.")
            return

        self.is_running = True
        logging.info(f"🚀 Iniciando Data Collector SOTA para {self.symbol}...")
        
        # Loop Principal de Coleta
        while self.is_running:
            try:
                # 1. Snapshot do Order Book (5 Níveis) - A "imagem" do mercado
                snapshot = self.bridge.get_order_book_snapshot(self.symbol, depth=5)
                if snapshot:
                    self.book_buffer.append(snapshot)
                
                # 2. Dados de Tick (Preço e Agressão Real)
                # Coletamos o último tick para cruzar com o book
                last_tick = self.bridge.get_market_data(self.symbol, n_candles=1).iloc[-1].to_dict()
                last_tick['timestamp'] = datetime.now().timestamp()
                self.tick_buffer.append(last_tick)
                
                # Despejo (Flush) a cada 1000 registros para CSV
                if len(self.tick_buffer) >= 1000:
                    await self.flush_data()
                    
                # Taxa de Amostragem: 100ms (High Frequency Data)
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logging.error(f"Erro no loop de coleta: {e}")
                await asyncio.sleep(1)

    async def flush_data(self):
        """Persiste os dados em disco (CSV) de forma assíncrona com pré-rotulagem."""
        if not self.tick_buffer: return

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Salvar Book Snapshots
        if self.book_buffer:
            df_book = pd.DataFrame(self.book_buffer)
            book_filename = f"{self.dataset_dir}/book_{self.symbol}_{timestamp_str}.csv"
            df_book.to_csv(book_filename, index=False)
        
        # Salvar Ticks com Rotulagem (Simulação para Dataset)
        df_ticks = pd.DataFrame(self.tick_buffer)
        
        # Aplicar Triple Barrier Method (Rotulagem On-the-Fly para otimizar treino futuro)
        # Nota: Em tempo real, isso rotula o passado recente do buffer.
        try:
             # Converter timestamp para datetime se necessário para o labeler
            if 'time' not in df_ticks.columns and 'timestamp' in df_ticks.columns:
                df_ticks['time'] = pd.to_datetime(df_ticks['timestamp'], unit='s')
            
            # Aplicar rotulagem SOTA
            df_labeled = apply_triple_barrier_method(df_ticks)
            tick_filename = f"{self.dataset_dir}/ticks_labeled_{self.symbol}_{timestamp_str}.csv"
            df_labeled.to_csv(tick_filename, index=False)
            logging.info(f"💾 Dataset salvo e rotulado: {len(df_labeled)} ticks em {tick_filename}")
            
        except Exception as e:
             logging.error(f"Erro ao rotular dados: {e}. Salvando bruto.")
             tick_filename = f"{self.dataset_dir}/ticks_raw_{self.symbol}_{timestamp_str}.csv"
             df_ticks.to_csv(tick_filename, index=False)

        
        # Limpar buffers
        self.book_buffer = []
        self.tick_buffer = []
