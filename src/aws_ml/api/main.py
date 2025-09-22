from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from typing import List, Literal
from functools import partial

from src.aws_ml.core.database import SessionLocal, engine
from src.aws_ml.scraper.scraping_zap_data_property import main_scraping_ad_and_url
from src.aws_ml.models import property_model
from src.aws_ml.api.security import get_api_key
from src.aws_ml.schemas import property_schema

import logging

# Configurando o logging
logging.basicConfig(
    level=logging.INFO, # Nível mínimo para exibir
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# Crie uma instância do logger para este módulo
logger = logging.getLogger(__name__)

# Criação das tabelas no banco de dados, baseado na models do sqlalchemy
property_model.Base.metadata.create_all(bind=engine)

# Criando uma instancia do FASTApi
app = FastAPI()

# --- Dependência para obter a sessão do banco de dados ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
# O decorator @app.get registra a função abaixo para responder a requisições HTTP GET
# no caminho "/collect-data".
# O 'response_model' garante que a resposta JSON seguirá o formato definido em
# 'property_schema.PropertySchema', além de documentar e serializar a saída automaticamente.
@app.get("/collect-data", response_model=List[property_schema.PropertySchema])
async def collect_data_and_save(
    # Efetua uma solicitação forçada de um tipo de imovel que deseja buscar
    tipo: Literal["apartamento", "casa", "quitinete", "sobrado", "terreno", "sitio"],
    
    # Determina o limite minimo (0) e o limite maximo (1000) de amostras a serem coletadas pelo scraping
    amostras_limit: int = Query(gt=0, le=1000),
    
    # 'db' recebe uma sessão de banco de dados da dependência 'get_db'.
    db: Session = Depends(get_db),
    
    # 'api_key' executa a função 'get_api_key' para validar a chave de API
    # enviada no cabeçalho da requisição. Se a chave for inválida, a execução é bloqueada.
    api_key: str = Depends(get_api_key)
):
    """
    Endpoint principal que aciona o Selenium, salva os dados e retorna os dados coletados.
    A resposta é garantida e formatada pelo response_model.
    """
    
    logger.info(f">>> Recebida requisição para coletar {amostras_limit} amostras de '{tipo}'...")
    
    try:
        # Prepara a função de scraping com o parametros passados na URL
        func_scraping_exec = partial(main_scraping_ad_and_url, tipo=tipo, amostras_limit=amostras_limit)
        
        # Executa a função de scraping (que é sincrona e demorada)
        # em uma thread separada, evitando que o servidor da API congele e não receba novas requisições
        list_properties_dict = await run_in_threadpool(func_scraping_exec)
        
        # Verifica se não foi coletado nenhum dado pelo Selenium
        if not list_properties_dict:
            raise HTTPException(status_code=404, detail="No data was collected by Selenium.")
        
        logger.info(f"Recebidos {len(list_properties_dict)} imóveis brutos do scraper. Removendo duplicatas...")
        
        # Usa um dicionario para garantir que cada ID sejá único, mantendo a ultima ocorrencia
        # Essa lógica foi feita para tratar de anuncios de imoveis que aparecem em 2 ou mais páginas e são coletados pelo scraping
        unique_properties = {}
        for prop in list_properties_dict:
            unique_properties[prop['id']] = prop
        deduplicated_list = list(unique_properties.values())
        
        logger.info(f"Total de {len(deduplicated_list)} imóveis únicos para salvar.")
        
        if not deduplicated_list:
             raise HTTPException(status_code=404, detail="No unique data was collected after deduplication.")
         
        # Pega uma referência à tabela
        properties_table = property_model.Property.__table__
        
        # Constrói a declaração de INSERT
        stmt = insert(properties_table).values(deduplicated_list)
        
        # Caso tenha dados de ID duplicados, iremos somente alterar as outras colunas menos a de id, data de coleta e hora de coleta
        update_dict = {
            col.name: col
            for col in stmt.excluded
            if col.name not in ["id", "collection_date", "collection_time"] # Não atualiza o ID nem a data/hora de criação
        }

        # index_elements=['id'] -> diz para o Postgre que o conflito é na coluna 'id'
        # set_=update_dict -> diz para o Postgre: "se houver conflito, atualize estes campos"
        final_stmt = stmt.on_conflict_do_update(
            index_elements=['id'],
            set_=update_dict
        )

        # Executa tudo em uma única chamada ao banco
        db.execute(final_stmt)
        db.commit()
        
        logger.info(f">>> {len(deduplicated_list)} imóveis foram salvos no banco de dados.")
        
        return deduplicated_list
    
    except Exception as e:
        db.rollback()
        logger.error(f"ERROR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")
    
@app.get("/consult-all-datas", response_model=List[property_schema.PropertySchema])
async def selection_all_datas(   
    # 'db' recebe uma sessão de banco de dados da dependência 'get_db'.
    db: Session = Depends(get_db),
    
    # 'api_key' executa a função 'get_api_key' para validar a chave de API
    # enviada no cabeçalho da requisição. Se a chave for inválida, a execução é bloqueada.
    api_key: str = Depends(get_api_key)
):
    """
    Consulta os dados de imóveis do banco de dados com suporte a paginação
    e tratamento de erros.
    """
    logger.info(f">>> Recebida requisição para consultar todos os dados.")

    try:
        logger.info(">>> Coletando os dados do banco...")
        
        datas = db.query(property_model.Property).all()
        
        logger.info(f">>> Foram coletados no total {len(datas)} dados de imóveis.")
        
        # Retorna a lista de dados (pode ser vazia).
        return datas

    except Exception as e:
        # --- Tratamento de Erros ---
        # Se qualquer coisa der errado na comunicação com o banco, capturamos o erro.
        logger.error(f"Ocorreu um erro ao consultar o banco de dados: {e}", exc_info=True)
        # Retornamos uma resposta de erro HTTP 500 padronizada.
        raise HTTPException(status_code=500, detail="Erro interno ao acessar o banco de dados.")
