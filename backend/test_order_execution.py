
import asyncio
import pandas as pd
import numpy as np
import logging
from backend.bot_sniper_win import SniperBotWIN
from backend.mt5_bridge import MT5Bridge
from backend.risk_manager import RiskManager
from backend.ai_core import AICore

async def test_end_to_end_execution():
    print("Iniciando Teste de Execucao Ponta a Ponta (Simulacao)...")
    
    # Setup
    bridge = MT5Bridge()
    # Forçamos conexão simulada se necessário, mas o bridge deve lidar com dry_run
    risk = RiskManager()
    risk.dry_run = True
    ai = AICore()
    
    bot = SniperBotWIN(bridge=bridge, risk=risk, ai=ai, dry_run=True)
    bot.symbol = "WIN$"
    
    # Simulando Dados de Mercado Ideais
    # Precisamos de um DataFrame com RSI baixo e Volume alto
    data = {
        'time': pd.date_range(start='2026-03-09', periods=50, freq='1min'),
        'open': [120000] * 50,
        'high': [120100] * 50,
        'low': [119900] * 50,
        'close': [119950] * 49 + [119800], # Queda para forçar RSI baixo
        'tick_volume': [1000] * 49 + [5000]   # Spike de volume
    }
    df = pd.DataFrame(data)
    
    print("Dados de mercado simulados gerados.")
    
    # Mocking necessary methods to avoid real network calls during logic validation
    # No entanto, queremos ver se o fluxo chega ao execute_trade
    
    print("Executando ciclo de decisão do Sniper...")
    
    # Criamos um callback para capturar o log do dashboard
    def capture_log(msg, type):
        print(f"[DASHBOARD LOG] {type.upper()}: {msg}")
    
    bot.log_callback = capture_log
    
    # Injetando sinal forçado para teste
    # last['rsi'] < 30 and last['tick_volume'] > (last['vol_sma'] * flux_mult)
    # Calculamos RSI manualmente para o DF simulado
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['vol_sma'] = df['tick_volume'].rolling(20).mean()
    
    # Ajustamos o último valor para garantir o sinal
    df.loc[df.index[-1], 'rsi'] = 25.0
    df.loc[df.index[-1], 'tick_volume'] = 10000.0
    
    # Executa a lógica de trade
    # Normalmente isso roda no loop, vamos chamar o execute_trade diretamente 
    # ou simular o bloco de filtragem
    
    print("Disparando execucao simulada...")
    # ai_decision simulado
    ai_decision = {
        "direction": "COMPRA",
        "score": 95.0,
        "quantile_confidence": 0.9,
        "action": "BUY",
        "reason": "Sinal de Teste Forte",
        "lot_multiplier": 1.0,
        "tp_multiplier": 1.0
    }
    
    success = await bot.execute_trade("buy", ai_decision=ai_decision, quantile_confidence=0.9, tp_multiplier=1.0, current_atr=100.0, is_scaling_in=False)
    
    if success:
        print("✅ SUCESSO: A ordem simulada foi processada pelo motor de execução.")
    else:
        print("❌ FALHA: A ordem foi vetada ou ocorreu um erro no fluxo.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_end_to_end_execution())
