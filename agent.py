# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from vertexai.preview import reasoning_engines
from vertexai import agent_engines

import vertexai
import requests
import json
import logging
import google.auth
from google.auth.transport.requests import Request
import os
from dotenv import load_dotenv
import argparse

load_dotenv()

# Configura o logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# VARIÁVEIS
PROJECT_ID = os.getenv("PROJECT_ID")
PROJECT_NUMBER = os.getenv("PROJECT_NUMBER")
LOCATION = os.getenv("LOCATION")
STAGING_BUCKET = os.getenv("STAGING_BUCKET")
MODEL = os.getenv("MODEL")
AUTH_ID = os.getenv("AUTH_ID")
APP_REGION = os.getenv("APP_REGION")
APP_NAME = os.getenv("APP_NAME")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")


vertexai.init(
    project=PROJECT_ID,
    location=LOCATION,
    staging_bucket=STAGING_BUCKET,
)


def obter_info_usuario_e_dar_boas_vindas(tool_context: ToolContext) -> str:
    """
    Autentica o usuário via token OAuth do AgentSpace e fornece uma mensagem de boas-vindas personalizada.

    Esta função recupera o token de acesso OAuth que o AgentSpace fornece após o usuário
    concluir o fluxo OAuth e, em seguida, o utiliza para buscar informações do usuário na API OAuth2 do Google.

    Args:
        tool_context: O ToolContext que contém o token OAuth em seu estado

    Returns:
        Uma mensagem de boas-vindas personalizada com as informações do usuário ou uma mensagem de erro se
        a autenticação for necessária ou falhar.
    """
    try:
        # Registra a tentativa de recuperar o token OAuth
        token_key = f"temp:{AUTH_ID}"
        logger.info(f"Tentando recuperar o token OAuth com a chave: {token_key}")

        # Registra as chaves disponíveis no estado do contexto da ferramenta para depuração
        available_keys = (
            list(tool_context.state.keys())
            if hasattr(tool_context.state, "keys")
            else []
        )
        logger.debug(f"Chaves disponíveis em tool_context.state: {available_keys}")

        # Recupera o token de acesso OAuth do AgentSpace
        # O AgentSpace o armazena com o formato de chave: temp:{AUTH_ID}
        access_token = tool_context.state[f"temp:{AUTH_ID}"]

        # Registra a recuperação bem-sucedida do token (registra apenas os primeiros caracteres por segurança)
        (
            logger.info(f"Token OAuth recuperado com sucesso: {access_token[:10]}...")
            if access_token
            else logger.warning("Token OAuth recuperado, mas está vazio")
        )

        if not access_token:
            return (
                "❌ **Autenticação Necessária**\n\n"
                "Nenhum token de acesso encontrado. Autorize este agente através do AgentSpace:\n"
                "1. Clique no botão 'Autorizar' na interface do AgentSpace\n"
                "2. Conclua o processo de login do Google\n"
                "3. Tente sua solicitação novamente após a conclusão da autorização"
            )

        # Usa o token para buscar informações do usuário na API Google OAuth2
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo", headers=headers, timeout=10
        )

        if response.status_code == 200:
            user_info = response.json()

            # Extrai os detalhes do usuário
            email = user_info.get("email", "Desconhecido")
            name = user_info.get("name", "Usuário")
            picture = user_info.get("picture", "")

            welcome_message = (
                f"✅ **Autenticação bem-sucedida!**\n\n"
                f"Bem-vindo, **{name}**! 👋\n\n"
                f"**Seu Perfil:**\n"
                f"- Email: {email}\n"
                f"- Status de Autenticação: ✓ Verificado\n\n"
                f"Você foi autenticado com sucesso! A integração OAuth com o AgentSpace está funcionando corretamente."
            )

            return welcome_message

        elif response.status_code == 401:
            return (
                "❌ **Erro de Autenticação**\n\n"
                "O token de acesso é inválido ou expirou. Por favor:\n"
                "1. Reautorize através do AgentSpace\n"
                "2. Garanta que você tenha as permissões necessárias\n"
                "3. Tente novamente após a reautorização"
            )
        else:
            return (
                f"❌ **Erro de Autenticação**\n\n"
                f"Falha ao recuperar as informações do usuário (Status: {response.status_code}).\n"
                f"Por favor, tente novamente ou entre em contato com o suporte se o problema persistir."
            )

    except KeyError as e:
        # Token não encontrado no contexto da ferramenta
        logger.error(
            f"KeyError ao acessar o token: {e}. Chave '{token_key}' não encontrada em tool_context.state"
        )
        logger.debug(
            f"Chaves de estado disponíveis: {list(tool_context.state.keys()) if hasattr(tool_context.state, 'keys') else 'Não foi possível recuperar as chaves'}"
        )
        return (
            "❌ **Autenticação Necessária**\n\n"
            "Você precisa autorizar este agente antes de usá-lo:\n\n"
            "1. Procure o botão **'Autorizar'** na interface do AgentSpace\n"
            "2. Clique nele para iniciar o fluxo Google OAuth\n"
            "3. Faça login com sua conta do Google\n"
            "4. Conceda as permissões solicitadas\n"
            "5. Uma vez autorizado, tente sua solicitação novamente\n\n"
            "Esta autorização é necessária para garantir o acesso seguro aos recursos de pesquisa de documentos."
        )

    except requests.exceptions.RequestException as e:
        return (
            f"❌ **Erro de Conexão**\n\n"
            f"Falha ao conectar-se ao serviço de autenticação: {str(e)}\n"
            f"Por favor, verifique sua conexão com a internet e tente novamente."
        )

    except Exception as e:
        return (
            f"❌ **Erro Inesperado**\n\n"
            f"Ocorreu um erro inesperado durante a autenticação: {str(e)}\n"
            f"Por favor, tente novamente ou entre em contato com o suporte se o problema persistir."
        )


agente_raiz = LlmAgent(
    name="demonstracao_oauth",
    model=MODEL,
    description=(
        "Agente de autenticação OAuth que demonstra a integração com o AgentSpace"
    ),
    instruction=(
        "Você é um agente de autenticação que demonstra a integração OAuth com o AgentSpace. "
        "IMPORTANTE: Quando um usuário interagir com você pela primeira vez, SEMPRE use a ferramenta obter_info_usuario_e_dar_boas_vindas para autenticá-lo e fornecer uma mensagem de boas-vindas. "
        "Se um usuário encontrar erros de autenticação, guie-o através do processo de autorização no AgentSpace. "
        "Após a autenticação bem-sucedida, você pode conversar com o usuário sobre a implementação do OAuth."
    ),
    tools=[
        obter_info_usuario_e_dar_boas_vindas,
    ],
)


def configurar_oauth():
    """Configura as definições de OAuth para a aplicação no AgentSpace."""
    credentials, project_id = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    access_token = credentials.token

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT_ID,
    }

    auth_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_ID}/locations/{APP_REGION}/authorizations?authorizationId={AUTH_ID}"
    auth_data = {
        "name": f"projects/{PROJECT_ID}/locations/{APP_REGION}/authorizations/{AUTH_ID}",
        "serverSideOauth2": {
            "clientId": f"{OAUTH_CLIENT_ID}",
            "clientSecret": f"{OAUTH_CLIENT_SECRET}",
            "authorizationUri": "https://accounts.google.com/o/oauth2/v2/auth?client_id={OAUTH_CLIENT_ID}&response_type=code&access_type=offline&prompt=consent&scope=openid%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.profile%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform",
            "tokenUri": "https://oauth2.googleapis.com/token",
        },
    }

    response = requests.post(auth_url, headers=headers, data=json.dumps(auth_data))
    if response.status_code == 200:
        logger.info("OAuth configurado com sucesso.")
    else:
        logger.error(f"Falha ao configurar o OAuth: {response.text}")


def criar_agente_no_agentspace(reasoning_engine_id: str):
    """Cria o agente no AgentSpace."""
    credentials, project_id = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    access_token = credentials.token

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT_ID,
    }

    agent_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_ID}/locations/{APP_REGION}/collections/default_collection/engines/{APP_NAME}/assistants/default_assistant/agents"
    agent_data = {
        "displayName": "OAuth Agent",
        "description": "Agente que faz o teste do OAuth no agentspace",
        "icon": {
            "uri": "https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/smart_toy/default/24px.svg"
        },
        "adk_agent_definition": {
            "tool_settings": {
                "tool_description": "Agente para teste de Oauth no agentspace"
            },
            "provisioned_reasoning_engine": {
                "reasoning_engine": f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{reasoning_engine_id}"
            },
            "authorizations": [
                f"projects/{PROJECT_NUMBER}/locations/{APP_REGION}/authorizations/{AUTH_ID}"
            ],
        },
    }

    response = requests.post(agent_url, headers=headers, data=json.dumps(agent_data))
    if response.status_code == 200:
        logger.info("Agente criado com sucesso no AgentSpace.")
    else:
        logger.error(f"Falha ao criar o agente no AgentSpace: {response.text}")


def criar_recursos():
    """Cria o reasoning engine, configura o OAuth e cria o agente no AgentSpace."""
    logger.info("Iniciando o processo de criação de recursos...")
    remote_app = agent_engines.create(
        agent_engine=agente_raiz,
        requirements=[
            "google-cloud-aiplatform[adk,agent_engines]",
            "requests",
            "python-dotenv",
        ],
    )
    reasoning_engine_id = remote_app.resource_name.split("/")[-1]
    logger.info(f"ID do Reasoning Engine extraído: {reasoning_engine_id}")
    configurar_oauth()
    criar_agente_no_agentspace(reasoning_engine_id)
    logger.info("Processo de criação de recursos finalizado com sucesso.")


def deletar_recursos():
    """Deleta o agente do AgentSpace, a configuração OAuth e o reasoning engine."""
    logger.info("Iniciando o processo de exclusão de recursos...")
    try:
        # Obter credenciais
        credentials, project_id = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(Request())
        access_token = credentials.token

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Goog-User-Project": PROJECT_ID,
        }

        # 1. Listar agentes para encontrar o que será deletado
        list_agents_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_ID}/locations/{APP_REGION}/collections/default_collection/engines/{APP_NAME}/assistants/default_assistant/agents"
        response = requests.get(list_agents_url, headers=headers)
        response.raise_for_status()
        agents = response.json().get("agents", [])

        agent_to_delete = None
        reasoning_engine_id = None
        for agent in agents:
            if agent.get("displayName") == "OAuth Agent":
                agent_to_delete = agent
                reasoning_engine_full_path = (
                    agent.get("adkAgentDefinition", {})
                    .get("provisionedReasoningEngine", {})
                    .get("reasoningEngine")
                )
                if reasoning_engine_full_path:
                    reasoning_engine_id = reasoning_engine_full_path.split("/")[-1]
                break

        if not agent_to_delete:
            logger.warning(
                "Agente 'OAuth Agent' não encontrado no AgentSpace. Nada a ser deletado."
            )
            return

        agent_name = agent_to_delete["name"]
        logger.info(f"Agente encontrado para exclusão: {agent_name}")

        # 2. Deletar o agente do AgentSpace
        delete_agent_url = (
            f"https://discoveryengine.googleapis.com/v1alpha/{agent_name}"
        )
        response = requests.delete(delete_agent_url, headers=headers)
        if response.status_code == 200:
            logger.info(f"Agente {agent_name} deletado com sucesso do AgentSpace.")
        else:
            logger.error(f"Falha ao deletar o agente do AgentSpace: {response.text}")
            # Continua para deletar outros recursos mesmo em caso de falha

        # 3. Deletar a autorização OAuth
        delete_auth_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_ID}/locations/{APP_REGION}/authorizations/{AUTH_ID}"
        response = requests.delete(delete_auth_url, headers=headers)
        if response.status_code == 200:
            logger.info(f"Autorização OAuth '{AUTH_ID}' deletada com sucesso.")
        else:
            logger.error(f"Falha ao deletar a autorização OAuth: {response.text}")

        # 4. Deletar o Reasoning Engine
        if reasoning_engine_id:
            logger.info(f"Deletando o Reasoning Engine com ID: {reasoning_engine_id}")
            try:
                engine_to_delete = reasoning_engines.ReasoningEngine(
                    reasoning_engine_id
                )
                engine_to_delete.delete()
                logger.info(
                    f"Reasoning Engine '{reasoning_engine_id}' deletado com sucesso."
                )
            except Exception as e:
                logger.error(f"Falha ao deletar o Reasoning Engine: {e}")
        else:
            logger.warning(
                "Não foi possível encontrar o ID do Reasoning Engine para deletar."
            )

        logger.info("Processo de exclusão de recursos finalizado.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Ocorreu um erro na requisição da API: {e}")
    except Exception as e:
        logger.error(f"Ocorreu um erro inesperado durante a exclusão: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cria ou deleta recursos do AgentSpace para a demonstração de OAuth."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--create", action="store_true", help="Cria e implanta todos os recursos."
    )
    group.add_argument(
        "--delete", action="store_true", help="Deleta todos os recursos implantados."
    )

    args = parser.parse_args()

    if args.create:
        criar_recursos()
    elif args.delete:
        deletar_recursos()
