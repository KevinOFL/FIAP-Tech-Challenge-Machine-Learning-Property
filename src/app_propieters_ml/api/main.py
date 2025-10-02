from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from typing import List, Literal
from functools import partial

from src.app_propieters_ml.core.database import SessionLocal, engine
from src.app_propieters_ml.scraper.scraping_zap_data_property import main_scraping_ad_and_url
from src.app_propieters_ml.models import property_model
from src.app_propieters_ml.api.security import get_api_key
from src.app_propieters_ml.schemas import property_schema, prediction_model_schema

import numpy as np
import logging
import joblib

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

# Criando uma instancia do FASTApi e capturando o PATH do modelo treinado
app = FastAPI(title="API e Web App de predição de valores de imóveis reais", version="1.0.0")
model = joblib.load("./src/app_propieters_ml/ml/models_trained/pred_price_model.joblib")

# Montando a pasta "static" para servir arquivos estáticos (CSS, JS)
app.mount("/static", StaticFiles(directory="./src/app_propieters_ml/api/static/"), name="static")

# Configurando o diretório de templates Jinja2
templates = Jinja2Templates(directory="./src/app_propieters_ml/api/templates")

# --- Dependência para obter a sessão do banco de dados ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Lista de tipos de imoveis
PROPERTY_TYPE_CATEGORIES = ["apartamento", "casa", "quitinete", "sobrados"]

# Página inicial onde está a aplicação completa
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    # O método TemplateResponse renderiza o template "index.html"
    return templates.TemplateResponse("index.html", {
        "request": request,
        "property_type": PROPERTY_TYPE_CATEGORIES
    })

# Endpoint de predição
@app.post("/predict")
def predict(data: prediction_model_schema.PredictionPriceSchema):
    """
    Recebe os dados de entrada, enviados via formulario no HTML e efetua a predição com o modelo carregado
    e retorna o resultado da predição.
    """
    # Construimos as features amais que o modelo utiliza
    rooms_safe = data.rooms if data.rooms > 0 else 1
    
    rooms_totality = data.rooms + data.bathrooms
    area_per_room = data.area_m2 / rooms_safe
    bathrooms_per_rooms = data.bathrooms / rooms_safe
    
    if data.property_type not in PROPERTY_TYPE_CATEGORIES:
        # Se o tipo de imóvel não for um dos conhecidos, retorna um erro.
        raise HTTPException(status_code=400, detail=f"Tipo de imóvel inválido. Use um de: {PROPERTY_TYPE_CATEGORIES}")

    # Cria um vetor de zeros com o mesmo tamanho das nossas categorias
    ohe_property_type = [0] * len(PROPERTY_TYPE_CATEGORIES)
    # Encontra o índice da categoria recebida
    category_index = PROPERTY_TYPE_CATEGORIES.index(data.property_type)
    # Define o valor 1 na posição correta
    ohe_property_type[category_index] = 1
    
    input_data = [
        data.area_m2,
        data.rooms,
        data.bathrooms,
        data.vacancies,
        rooms_totality,
        area_per_room,
        bathrooms_per_rooms
    ] + ohe_property_type
    
    # Transformamaos para uma dimensão 2D
    input_data_final = np.array(input_data).reshape(1, -1)
    
    # Passamos os dados para o modelo prever
    prediction_result = model.predict(input_data_final)
    
    # E retornamos o resultado
    return {
        "prediction": int(prediction_result[0]),
    }

# O decorator @app.get registra a função abaixo para responder a requisições HTTP GET
# no caminho "/collect-data".
# O 'response_model' garante que a resposta JSON seguirá o formato definido em
# 'property_schema.PropertySchema', além de documentar e serializar a saída automaticamente.
@app.get("/collect-data", response_model=List[property_schema.PropertySchema])
async def collect_data_and_save(
    # Efetua uma solicitação forçada de um tipo de imovel que deseja buscar
    tipo: Literal["apartamento", "casa", "quitinete", "sobrado"],
    
    # Determina o limite minimo (0) e o limite maximo (1000) de amostras a serem coletadas pelo scraping
    amostras_limit: int = Query(gt=0, le=3000, description="Limite máximo de amostras de imoveis a coletar."),
    
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
    Consulta os dados de imóveis do banco de dados com suporte a tratamento de erros.
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
        logger.error(f"An error occurred while querying the database: {e}", exc_info=True)
        # Retornamos uma resposta de erro HTTP 500 padronizada.
        raise HTTPException(status_code=500, detail="Internal error accessing the database.")
