import MetaTrader5 as mt5
import pandas as pd
import os
from datetime import datetime, timedelta
import logging
from backend.data_labeler import apply_triple_barrier_method

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class HistoricalDataCollector:
    def __init__(self, dataset_dir="data/sota_training"):
        self.dataset_dir = dataset_dir
        if not os.path.exists(self.dataset_dir):
            os.makedirs(self.dataset_dir)

    def connect(self):
        if not mt5.initialize():
            logging.error(f"Falha ao inicializar MT5: {mt5.last_error()}")
            return False
        return True

    def get_historical_candles(self, symbol, timeframe, start_date, end_date):
        """Coleta candles OHLCV históricos."""
        logging.info(f"Baixando candles para {symbol} de {start_date} até {end_date}...")
        rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
        if rates is None or len(rates) == 0:
            logging.warning(f"Nenhum candle encontrado para {symbol}.")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_historical_ticks(self, symbol, start_date, end_date):
        """Coleta dados de tick (agressão)."""
        logging.info(f"Baixando ticks para {symbol} de {start_date} até {end_date}...")
        ticks = mt5.copy_ticks_range(symbol, start_date, end_date, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            logging.warning(f"Nenhum tick encontrado para {symbol}.")
            return None
        
        df = pd.DataFrame(ticks)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def calculate_obi_from_ticks(self, df_ticks):
        """
        [HEURÍSTICA] Estima o OBI (Order Book Imbalance) baseado no volume de agressão.
        OBI ≈ (Volume Compra - Volume Venda) / (Volume Total)
        """
        if df_ticks is None or df_ticks.empty:
            return 0.0
        
        # Na B3, o campo 'flags' indica a direção do tick (buy/sell)
        # TICK_FLAG_BUY = 32, TICK_FLAG_SELL = 64
        df_ticks['is_buy'] = (df_ticks['flags'] & 32) > 0
        df_ticks['is_sell'] = (df_ticks['flags'] & 64) > 0
        
        buy_vol = df_ticks[df_ticks['is_buy']]['volume'].sum()
        sell_vol = df_ticks[df_ticks['is_sell']]['volume'].sum()
        
        total_vol = buy_vol + sell_vol
        if total_vol == 0: return 0.0
        
        return (buy_vol - sell_vol) / total_vol

    def process_and_save(self, symbol, df_candles, df_ticks):
        """Aplica Pipeline SOTA e salva em CSV."""
        if df_candles is None or df_candles.empty: return

        logging.info(f"Processando {len(df_candles)} candles para {symbol}...")
        
        # 1. Rotulagem SOTA
        try:
            df_labeled = apply_triple_barrier_method(df_candles)
        except Exception as e:
            logging.error(f"Erro na rotulagem: {e}")
            df_labeled = df_candles

        # Adicionar coluna de símbolo se não existir
        if 'symbol' not in df_labeled.columns:
            df_labeled['symbol'] = symbol
            
        filename = f"{self.dataset_dir}/training_{symbol}_MASTER.csv"
        
        file_exists = os.path.isfile(filename)
        
        # Salvar (Append se existir)
        df_labeled.to_csv(filename, mode='a', index=False, header=not file_exists)
        logging.info(f"✅ Chunk salvo em: {filename} (Total atual: {len(df_labeled)} linhas adicionadas)")

    def run_bulk_collection(self, symbols=None, days_back=180):
        if not self.connect(): return

        # Definição das Camadas conforme Plano SOTA
        if symbols is None:
            symbols = {
                "PRINCIPAL": ["WIN$", "WDO$"],
                "BLUE_CHIPS": ["VALE3", "PETR4", "ITUB4"],
                "CORRELATION": ["SPX", "DXY", "US10Y"] # Símbolos podem variar por corretora
            }

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        all_symbols = symbols["PRINCIPAL"] + symbols["BLUE_CHIPS"] + symbols["CORRELATION"]

        for symbol in all_symbols:
            logging.info(f"--- Iniciando Coleta Massiva: {symbol} ---")
            
            # Verificar se o símbolo existe no MT5
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logging.warning(f"Símbolo {symbol} não encontrado no MT5. Pulando...")
                continue
                
            if not symbol_info.visible:
                mt5.symbol_select(symbol, True)

            current_start = start_date
            while current_start < end_date:
                current_end = current_start + timedelta(days=30)
                if current_end > end_date: current_end = end_date
                
                # Candles M1 (Fonte principal para Transformer)
                df_c = self.get_historical_candles(symbol, mt5.TIMEFRAME_M1, current_start, current_end)
                
                # Para ativos principais, tentamos colher ticks para OBI
                df_t = None
                if symbol in symbols["PRINCIPAL"]:
                    # Ticks são pesados, colhemos apenas os últimos 7 dias de ticks por chunk para microestrutura
                    tick_start = max(current_start, current_end - timedelta(days=7))
                    df_t = self.get_historical_ticks(symbol, tick_start, current_end)
                
                self.process_and_save(symbol, df_c, df_t)
                
                current_start = current_end

        mt5.shutdown()

if __name__ == "__main__":
    collector = HistoricalDataCollector()
    # Por padrão, vamos coletar 6 meses (180 dias) para o treinamento SOTA
    collector.run_bulk_collection(days_back=180)
