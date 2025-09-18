from selenium.webdriver.chrome.options import Options 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from time import sleep
from random import uniform
from urllib.parse import urljoin
from selenium_stealth import stealth
from src.aws_ml.models.property_model import PropertySchema
from pydantic import ValidationError

import logging
from typing import Literal

# Configura do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Configuração das Opções do Navegador Chrome ---

# Cria um objeto para armazenar as configurações do navegador Chrome.
chrome_options = Options()

# Configura o Chrome para rodar em modo "headless", ou seja, sem abrir uma janela visual.
chrome_options.add_argument("--headless")

# Define um tamanho de janela fixo (Full HD), essencial para que o layout da página seja renderizado corretamente em modo headless.
chrome_options.add_argument("--window-size=1920,1080")

# Desativa a aceleração de hardware (GPU), uma medida que evita problemas de compatibilidade em alguns ambientes, como Windows e Docker.
chrome_options.add_argument("--disable-gpu")

# Desabilita o modo "sandbox" do Chrome, necessário para executar o navegador em certos ambientes de servidor ou containers (como Docker).
chrome_options.add_argument("--no-sandbox")

# Evita problemas com o uso de memória compartilhada (/dev/shm) em ambientes com recursos limitados, como containers.
chrome_options.add_argument("--disable-dev-shm-usage")

# Inicia o navegador maximizado (funciona apenas quando não está em modo headless).
chrome_options.add_argument("--start-maximized")

# Remove a barra de aviso "O Chrome está sendo controlado por software de teste automatizado", uma técnica para parecer menos com um robô.
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

# Desativa o uso de extensões de automação, outra medida para dificultar a detecção do scraper.
chrome_options.add_experimental_option('useAutomationExtension', False)

# Define um User-Agent de um navegador comum para que o scraper se identifique como um usuário real, e não um script padrão.
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
chrome_options.add_argument(f"user-agent={user_agent}")


# --- Inicialização do WebDriver ---

# Inicializa o WebDriver do Chrome, aplicando todas as configurações definidas acima.
# O ChromeDriverManager cuida de baixar e gerenciar a versão correta do driver automaticamente.
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)


# --- Configuração do Selenium Stealth ---

# Aplica as configurações da biblioteca 'selenium-stealth' ao driver.
# Esta função modifica várias propriedades do navegador em tempo de execução para torná-lo praticamente indistinguível de um navegador usado por um humano.
stealth(driver,
        # Define o idioma do navegador como português do Brasil.
        languages=["pt-BR", "pt"],
        # Informa que o fornecedor do navegador é a Google.
        vendor="Google Inc.",
        # Simula que o sistema operacional é Windows.
        platform="Win32",
        # Mascara as informações de renderização gráfica (WebGL) para parecerem mais comuns.
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        # Corrige um pequeno detalhe de renderização que pode denunciar a automação.
        fix_hairline=True,
        )

# Criação de um driver de espera
wait = WebDriverWait(driver, 10)

# URLs utilizadas na raspagem
url_base = "https://www.zapimoveis.com.br/venda/"
urls_alter = {"apartamento":"apartamentos/?transacao=venda&tipos=apartamento_residencial&ordem=MOST_RELEVANT", "casa":"casas/?transacao=venda&tipos=casa_residencial&ordem=MOST_RELEVANT",
              "quitinete":"quitinetes/?transacao=venda&tipos=kitnet_residencial&ordem=MOST_RELEVANT","sobrado":"sobrados/?transacao=venda&tipos=sobrado_residencial&ordem=MOST_RELEVANT",
              "terreno":"terrenos-lotes-condominios/?transacao=venda&tipos=lote-terreno_residencial&ordem=MOST_RELEVANT", "sitio":"fazendas-sitios-chacaras/?transacao=venda&tipos=granja_residencial&ordem=MOST_RELEVANT",
}


# Função de main de raspagem
def main_scraping_ad_and_url(tipo: Literal["apartamento", "casa", "quitinete", "sobrado", "terreno", "sitio"], amostras_limit: int):
    """
    Função principal que orquestra o processo de web scraping no site Zap Imóveis.

    Esta função navega pelas páginas de resultados para um determinado tipo de imóvel, 
    coleta os links de todos os anúncios até atingir um limite especificado e gerencia
    a extração e validação dos dados de cada anúncio.

    Args:
        tipo (Literal): O tipo de imóvel a ser buscado. 
                        Valores aceitos: "apartamento", "casa", "quitinete", "sobrado", "terreno", "sitio".
        amostras_limit (int): O número máximo de anúncios a serem coletados antes de parar o processo.

    Returns:
        list: Uma lista de dicionários, onde cada dicionário contém os dados de um imóvel,
              validados e prontos para serem salvos em JSON.
    """
    logging.info(f"Iniciando o processo de scraping da Zap Imoveis em {tipo}.")
    
    
    ad_links = [] # -> Lista auxiliar para verificação interna de volume
    list_data_propertys_json = [] # -> Lista principal, a cada interação e devolvida para uma função

    full_url = urljoin(url_base, urls_alter[tipo]) # -> URL que efetua a junção da URL main mais a URL determinada pelo tipo de imovel
    driver.get(full_url) # -> Acessando a URL 
    
    logging.info(f"Página acessada: {driver.title}")
        
    number_page = 1 
    sleep(3)
    try:
        while True:
            ad_links_current_page = [] # -> Lista que recebe os links dos anuncios da página atual
            ad_selector = 'li[data-cy="rp-property-cd"] a' # -> Variavel que contem o valor dos elementos de anuncios da página
                
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ad_selector))) # -> Arguarde até os anuncios aparecem na página

            property_listing = driver.find_elements(By.CSS_SELECTOR, ad_selector) # -> Salvamos cada anuncio (elementos) em uma variavel que se torna uma lista
            logging.info(f"Coletando links da página: {number_page}.")
            
            # Verificação para ver se ultrapassamos o limite de amostras solicitadas ou já atingimos
            if len(ad_links) >= amostras_limit:
                logging.info(f"Limite de amostras atingido ou ultrapassado (limite={amostras_limit}).")
                break
            
            # Pausas longas para fingir comportamento humano quando atingimos uma quantidade de amostras
            if len(ad_links) == 600 or len(ad_links) == 1200 or len(ad_links) == 1800:
                sleep(uniform(10, 15))
                
            # Pegamos o endpoint de cada anuncio, pois e neles que contém o ID do imovel, e salvamos em 2 listas
            for property_link in property_listing:
                href = property_link.get_attribute('href')
                if href:
                    ad_links.append(str(href))
                    ad_links_current_page.append(str(href))
            
            # Enviamos os dados de elementos e endpoints dos anuncios e recebemos os retorno e repassamos para a próxima função que efetua a verificação desses dados       
            datas_propertys = scraping_data_ad_and_endpoints(property_listing, ad_links_current_page)
            property_json = vefiry_datas_for_send_json(datas_propertys)
            
            # Adicionamos os dados retornados a uma lista
            list_data_propertys_json.append(property_json)
            
            # Verificação do botão next-page para irmos para a próxima página caso ainda não tenhamos suprido a necessidade de amostras
            try:
                # 1. ENCONTRAR o botão de próxima página
                botao_next = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="next-page"]')))
                    
                # 2. ROLAR a página até o botão (para garantir que seja clicável)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_next)
                sleep(uniform(3, 5)) # Pequena pausa para a rolagem acontecer

                # 3. CLICAR no botão
                botao_next.click()
                number_page += 1
                    
                # Pausa aleatória para simular comportamento humano
                sleep(uniform(3, 6))

            except TimeoutException:
                # Se o botão não for encontrado após 15 segundos, significa que chegamos ao fim
                logging.info("Botão 'Próxima página' não encontrado. Fim do scraping.")
                break # Sai do loop while
        
    except Exception as e:
        logging.error(f"Ocorreu um erro inesperado durante o scraping: {e}")
        
    finally:
        # Por fim retornamos uma lista de dicionarios com os dados dos imoveis validados
        logging.info(f"--- COLETA DE DADOS CONCLUÍDA ---")
        logging.info(f"Total de imóveis com os dados coletados: {len(ad_links)}")
        driver.quit()
        return list_data_propertys_json
        
    


def scraping_data_ad_and_endpoints(ad_features:list, URLs:list):
    """
    Extrai informações detalhadas de cada anúncio de imóvel em uma página.

    Esta função itera sobre uma lista de elementos web (os cards de anúncio) e 
    extrai dados como preço, área, número de quartos, etc. Também utiliza a URL
    para extrair o ID único do anúncio.

    Args:
        ad_features (list): Lista de elementos web do Selenium, onde cada elemento 
                            corresponde a um card de anúncio.
        URLs (list): Lista de strings contendo as URLs de cada anúncio, usada para
                     extrair informações como o ID.

    Returns:
        list: Uma lista de dicionários, onde cada dicionário representa os dados 
              brutos de um imóvel.
    """
    list_data_propertys = [] # -> Lista principal que recebe o dicionarios de dados dos imoveis
    sleep(3)
    
    for index, data_ad in enumerate(ad_features):
        raw_data = {} # -> Dicionario que e resetado a cada ciclo
        try:
            # Pegando os dados de ID e Tipo de imovel dentro da URL
            data_links = URLs[index]
            parts_url = data_links.split('-')
            part_url_id = data_links.split('-id-')
            part_id = part_url_id[1]
            id_url = part_id.split('/')
                
            raw_data["id"] = id_url[0]
                
            raw_data["property_type"] = parts_url[1]
           
            try:
                # container_price contêm todos os dados de preços, IPTU e condominio
                container_price = data_ad.find_element(By.CSS_SELECTOR, "[data-cy='rp-cardProperty-price-txt']")
                price = container_price.find_element(By.TAG_NAME, 'p')
                
                # Pegando os dados de preço do imovel
                price_text = price.text
                raw_data["price"] = price_text
                    
                parags = container_price.find_elements(By.TAG_NAME, 'p')
                prices = parags[1].text
                    
                price_parts = prices.split('•')
                  
                # Verificando se o imovel possui somente o dado de IPTU  
                try:
                    if "IPTU" in prices and "Cond." not in prices:
                        raw_data["iptu"] = prices.strip()
                except Exception as e:
                        logging.error(f"Ocorreu um erro inesperado durante a coleta dos dados de IPTU sem condominio: {e}")
                
                # Caso passe da ultima verificação, verificamos se ele tem os dados de condominio e IPTU, pois geralmente o condominio vem antes do IPTU no texto 
                try:
                    if "Cond." in price_parts[0]:
                        raw_data["price_condominium"] = price_parts[0].strip()
                            
                        if len(price_parts) > 1 and "IPTU" in price_parts[1]:
                            raw_data["iptu"] = price_parts[1].strip()
                except Exception as e:
                    logging.error(f"Ocorreu um erro inesperado durante a coleta dos dados do imovel com IPTU e condominio: {e}")
                        
            except Exception as e:
                logging.error(f"Ocorreu um erro inesperado durante a coleta dos dados de IPTU e condominio: {e}")
            
            # Pegando os dados de área do imovel
            try:
                li_area = data_ad.find_element(By.CSS_SELECTOR, "[data-cy='rp-cardProperty-propertyArea-txt']")
                h3_area = li_area.find_element(By.TAG_NAME, "h3")
                area_m2 = h3_area.text
                raw_data["area_m2"] = area_m2.strip()
            except Exception as e:
                logging.error(f"Ocorreu um erro inesperado durante a coleta dos dados de área do imovel: {e}")
            
            # Pegando os dados de quantos comodos o imovel possui       
            try:
                li_room = data_ad.find_element(By.CSS_SELECTOR, "[data-cy='rp-cardProperty-bedroomQuantity-txt']")
                h3_room = li_room.find_element(By.TAG_NAME, "h3")
                room = h3_room.text
                raw_data["rooms"] = room.strip()
            except Exception as e:
                raw_data["rooms"] = 0
                logging.error(f"Ocorreu um erro inesperado durante a coleta dos dados dos comodos do imovel: {e}")
            
            # Pegando os dados de quantos banheiros o imovel possui            
            try:
                li_bathroom = data_ad.find_element(By.CSS_SELECTOR, "[data-cy='rp-cardProperty-bathroomQuantity-txt']")
                h3_bathroom = li_bathroom.find_element(By.TAG_NAME, "h3")
                bathroom = h3_bathroom.text
                # Aqui e uma verificação para caso esteja escrito dessa forma "1-2" banheiros, ai pegamos o valor maior
                if "-" in bathroom:
                    bathroom_parts = bathroom.split("-")
                    raw_data["bathrooms"] = bathroom_parts[1].strip()
                else:
                    raw_data["bathrooms"] = bathroom.strip()
            except Exception as e:
                raw_data["bathrooms"] = 0
                logging.error(f"Ocorreu um erro inesperado durante a coleta dos dados de banheiros do imovel: {e}")
            
            # Pegando os dados de quantas vagas de estacionamento o imovel possui           
            try:
                li_parking = data_ad.find_element(By.CSS_SELECTOR, "[data-cy='rp-cardProperty-parkingSpacesQuantity-txt']")
                h3_parking = li_parking.find_element(By.TAG_NAME, "h3")
                parking = h3_parking.text
                raw_data["vacancies"] = parking.strip()
            except Exception as e:
                raw_data["vacancies"] = 0
                logging.error(f"Ocorreu um erro inesperado durante a coleta dos dados de vagas de garagem do imovel: {e}")
            
            #  Pegando os dados de localização (estado, bairro) do imovel    
            try:
                li_location = data_ad.find_element(By.CSS_SELECTOR, "[data-cy='rp-cardProperty-location-txt']")
                location = li_location.text
                location_parts = location.split("\n")
                location_index = location_parts[-1]
                locations = location_index.split(",")
                raw_data["state"] = locations[1].strip()
                raw_data["neighborhood"] = locations[0].strip()
            except Exception as e:
                logging.error(f"Ocorreu um erro inesperado durante a coleta dos dados de estado e bairro onde o imovel se localiza: {e}")
                
            list_data_propertys.append(raw_data)
                    
        except Exception as e:
            logging.error(f"Ocorreu um erro inesperado durante a coleta dos dados da URL atual: {e}")
    
    # Retornamos uma lista de dicionarios
    return list_data_propertys
   
   
def vefiry_datas_for_send_json(datas_propertys:list):
    """
    Valida os dados brutos extraídos contra um esquema definido (Pydantic) e os 
    prepara para a serialização em JSON.

    Esta etapa é crucial para garantir a qualidade e a consistência dos dados antes
    de salvá-los ou enviá-los para outro sistema.

    Args:
        datas_propertys (list): Uma lista de dicionários contendo os dados brutos 
                                de cada imóvel.

    Returns:
        list: Uma lista de dicionários validados e prontos para serem convertidos 
              em JSON.
    """
    property_validate = [] # -> Cada dado validado pelo modelo do Pydantic vai ser adicionado aqui
    for property in datas_propertys:
        try: 
            valid_property = PropertySchema(**property) # -> Validando o imovel com o modelo do Pydantic
            
            property_validate.append(valid_property) # -> Adicinando a lista
        except ValidationError:
            logging.error(f"Arquivo falhou na validação: \n{valid_property}")
    
    property_list_validate = [property_for_json.model_dump() for property_for_json in property_validate]
    # Retornamos umas lista de dicionarios
    return property_list_validate