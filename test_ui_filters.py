import sys
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright não instalado. Use: pip install playwright && playwright install")
    sys.exit(1)

def test_filters():
    print("Iniciando auditoria automatizada do Dashboard HFT (localhost:3000)...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Catch console logs from browser to detect API errors
            page.on("console", lambda msg: print(f"Browser Console [{msg.type}]: {msg.text}"))
            
            print("Acessando a página...")
            page.goto("http://localhost:3000", wait_until="load")
            
            print("Aguardando carregamento da interface e WebSocket...")
            page.wait_for_selector("#macro-filter", timeout=15000)
            page.wait_for_timeout(3000) # Tempo extra para websocket popular os botões
            
            def get_state(selector):
                try:
                    state = page.get_attribute(selector, "data-state")
                    is_disabled = page.evaluate(f"document.querySelector('{selector}').disabled")
                    return {"state": state, "disabled": is_disabled}
                except Exception as e:
                    return {"error": str(e)}
                
            print("\n--- [PASSO 1] ESTADO INICIAL DOS VETOS ---")
            state_news = get_state("#news-filter")
            state_cal = get_state("#calendar-filter")
            state_mac = get_state("#macro-filter")
            print(f"📰 Veto Origem: {state_news}")
            print(f"🕒 Veto Agenda: {state_cal}")
            print(f"🌍 Veto Macro:  {state_mac}")
            
            def toggle_and_check(selector, name):
                print(f"\n--- [PASSO] CLICANDO EM: {name} ---")
                
                # Clica na LABEL, que aciona nativamente o Switch no Radix UI
                label_selector = f"label[for='{selector.replace('#', '')}']"
                page.click(label_selector)
                
                # Aguarda o debouncer do React (500ms) + ciclo de varredura
                page.wait_for_timeout(1500)
                
                new_state = get_state(selector)
                print(f"✅ {name} Após Clique -> {new_state}")
                return new_state
                
            new_news = toggle_and_check("#news-filter", "Veto Origem")
            new_cal = toggle_and_check("#calendar-filter", "Veto Agenda")
            new_mac = toggle_and_check("#macro-filter", "Veto Macro")
            
            print("\n--- [VEREDITO FINAL DA AUDITORIA E2E] ---")
            print("Verificando consistência e inversão de estado:")
            
            def check_inversion(old, new, name):
                if old.get("state") != new.get("state"):
                    print(f"[✅] {name}: INVERTEU COM SUCESSO! ({old.get('state')} -> {new.get('state')})")
                else:
                    print(f"[❌] {name}: FALHOU NA INVERSÃO. Permaneceu: {old.get('state')}")
            
            check_inversion(state_news, new_news, "Veto Origem (#news-filter)")
            check_inversion(state_cal, new_cal, "Veto Agenda (#calendar-filter)")
            check_inversion(state_mac, new_mac, "Veto Macro (#macro-filter)")
            
            browser.close()
    except Exception as e:
        print(f"Erro Crítico no Teste: {str(e)}")

if __name__ == "__main__":
    test_filters()
