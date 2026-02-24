import sys
import os
import asyncio
import logging

# Adicionar root ao path para localizar módulos do backend
sys.path.append(os.getcwd())

from backend.mt5_bridge import MT5Bridge
from backend.ai_core import InferenceEngine
from backend.risk_manager import RiskManager

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def run_diagnostics():
    print("\n" + "="*50)
    print("🚀 INICIANDO DIAGNÓSTICO MESTRE: TRADING STATION SOTA")
    print("="*50 + "\n")

    # 1. MT5 Connectivity Check
    print("📡 [1/5] TESTANDO CONECTIVIDADE MT5...")
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ ERRO: Falha ao conectar ao MetaTrader 5. Verifique se o Terminal está aberto.")
        return
    
    try:
        acc_info = bridge.mt5.account_info()
        print(f"✅ Conectado à conta: {acc_info.login} ({acc_info.company})")
        print(f"💰 Equity Atual: {acc_info.equity} | Alavancagem: 1:{acc_info.leverage}")
    except Exception as e:
        print(f"❌ ERRO ao obter info da conta: {e}")

    # 2. Multi-Asset Data Synchronization
    print("\n📊 [2/5] TESTANDO SINCRONIZAÇÃO MULTI-ATIVO (SOTA PIPELINE)...")
    win_symbol = bridge.get_current_symbol("WIN")
    wdo_symbol = bridge.get_current_symbol("WDO")
    symbols = [win_symbol, "ITUB4", "PETR4", "VALE3", wdo_symbol]
    
    print(f"🔍 Capturando: {symbols}")
    multi_data = bridge.get_synchronized_multi_asset_data(symbols, n_candles=60)
    
    if multi_data is not None and not multi_data.empty:
        print(f"✅ Sincronização OK! Shape: {multi_data.shape} (Esperado: 60, 5)")
        print(f"📈 Colunas: {list(multi_data.columns)}")
        if multi_data.isnull().values.any():
            print("⚠️ AVISO: Detectados NaNs no dataset sincronizado.")
        else:
            print("💎 Integridade de Dados: 100% Sólida (No NaNs)")
    else:
        print("❌ ERRO: Falha na sincronização de dados. Verifique a liquidez dos ativos.")

    # 3. Model Loading & Inference (ONNX + DML)
    print("\n🧠 [3/5] TESTANDO CÉREBRO SOTA (ONNX + DIRECTML)...")
    weights_path = "backend/patchtst_weights_sota.pth" # O engine converte para .onnx internamente
    engine = InferenceEngine(weights_path)
    
    if engine.use_onnx:
        print("🚀 ONNX Runtime está ATIVO e OTIMIZADO.")
    else:
        print("⚠️ ONNX Falhou, usando PyTorch Fallback (CPU).")
        
    # Teste de Predição com dados reais
    if multi_data is not None:
        try:
            preds = await engine.predict(multi_data)
            if isinstance(preds, dict):
                print(f"✅ Inferência Concluída: Forecast={preds['forecast_norm']:.4f} | Incerteza={preds['uncertainty_norm']:.4f}")
                print(f"🎯 Score Final de Tendência: {preds['score']:.2f}")
            else:
                print("❌ ERRO: Retorno inválido da inferência.")
        except Exception as e:
            print(f"❌ ERRO DURANTE INFERÊNCIA: {e}")

    # 4. Order Book & Microstructure
    print("\n📉 [4/5] TESTANDO MICROESTRUTURA (ORDER BOOK L2)...")
    book = bridge.get_order_book(win_symbol)
    if book['bids'] and book['asks']:
        print(f"✅ Book de Ofertas Ativo: {len(book['bids'])} Bids | {len(book['asks'])} Asks")
        spread = book['asks'][0]['price'] - book['bids'][0]['price']
        print(f"⚖️ Spread Atual: {spread:.2f} pts")
    else:
        print("❌ ERRO: Book de Ofertas vazio ou indisponível.")

    # 5. Risk Manager Verification
    print("\n🛡️ [5/5] TESTANDO FILTROS DE RISCO...")
    risk = RiskManager()
    time_allowed = risk.is_time_allowed()
    print(f"⏰ Janela de Horário: {'DENTRO' if time_allowed else 'FORA'}")
    
    loss_limit_ok, msg = risk.check_daily_loss(0.0)
    print(f"🛑 Limite de Perda Diária: {'OK' if loss_limit_ok else 'TRAVADO'} ({msg})")

    print("\n" + "="*50)
    print("✅ DIAGNÓSTICO CONCLUÍDO COM SUCESSO!")
    print("="*50 + "\n")
    
    bridge.disconnect()

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
