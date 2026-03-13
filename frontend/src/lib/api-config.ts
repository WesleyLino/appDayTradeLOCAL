/**
 * [ANTIVIBE-CODING] - Centralização da conectividade do Backend
 * Resolve problemas de "Failed to fetch" no Windows (localhost vs 127.0.0.1)
 * E permite acesso via IP de rede local.
 */

const getBackendConfig = () => {
  // No navegador, window.location.hostname nos diz como o usuário está acessando o site
  const hostname =
    typeof window !== "undefined" ? window.location.hostname : "127.0.0.1";

  // Porta padrão do backend FastAPI definida no main.py
  const PORT = "8000";

  // No Windows, usar o mesmo hostname de acesso garante consistência com CORS e WebSocket
  const host = hostname; 

  return {
    http: `http://${host}:${PORT}`,
    ws: `ws://${host}:${PORT}/ws`,
  };
};

export const API_CONFIG = getBackendConfig();
