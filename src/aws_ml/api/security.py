import os
from dotenv import load_dotenv
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

# Carregamento das variaveis de ambiente
load_dotenv()

api_key_header = APIKeyHeader(name="X-API-Key")

# Pega a nossa chave secreta da variável de ambiente
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY não encontrada nas variáveis de ambiente.")

def get_api_key(api_key_header: str = Security(api_key_header)):
    """
    Verifica se a chave de API enviada pelo cliente é válida.
    """
    
    if api_key_header == API_KEY:
        return api_key_header
    else:
        # Se a chave for inválida, levanta um erro HTTP 403 Forbidden
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials"
        )