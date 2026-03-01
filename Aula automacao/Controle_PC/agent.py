from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext, llm
from livekit.plugins import noise_cancellation, google
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from mem0 import AsyncMemoryClient
import logging
import os

from automacao_jarvis import JarvisControl

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# AGENTE
# ==========================================

class Assistant(Agent, llm.ToolContext):
    def __init__(self, chat_ctx: ChatContext = None):

        llm.ToolContext.__init__(self, [])

        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                voice="Charon",
                temperature=0.6,
            ),
            chat_ctx=chat_ctx,
        )

        self.jarvis_control = JarvisControl()

    # ================================
    # FERRAMENTAS
    # ================================

    @agents.function_tool
    async def criar_pasta(self, caminho: str):
        """Cria uma nova pasta no caminho especificado."""
        return self.jarvis_control.criar_pasta(caminho)

    @agents.function_tool
    async def deletar_item(self, caminho: str):
        """Deleta um arquivo ou diretório no caminho especificado."""
        return self.jarvis_control.deletar_arquivo(caminho)

    @agents.function_tool
    async def limpar_diretorio(self, caminho: str):
        """Remove todos os arquivos e pastas de um diretório sem deletar o diretório em si."""
        return self.jarvis_control.limpar_diretorio(caminho)

    @agents.function_tool
    async def mover_item(self, origem: str, destino: str):
        """Move um arquivo ou pasta de uma origem para um destino."""
        return self.jarvis_control.mover_item(origem, destino)

    @agents.function_tool
    async def copiar_item(self, origem: str, destino: str):
        """Copia um arquivo ou pasta de uma origem para um destino."""
        return self.jarvis_control.copiar_item(origem, destino)

    @agents.function_tool
    async def renomear_item(self, caminho: str, novo_nome: str):
        """Renomeia um arquivo ou pasta existente."""
        return self.jarvis_control.renomear_item(caminho, novo_nome)

    @agents.function_tool
    async def organizar_pasta(self, caminho: str):
        """Organiza os arquivos de uma pasta separando-os por tipo (Imagens, Documentos, etc)."""
        return self.jarvis_control.organizar_pasta(caminho)

    @agents.function_tool
    async def compactar_pasta(self, caminho: str):
        """Compacta uma pasta no formato ZIP."""
        return self.jarvis_control.compactar_pasta(caminho)

    @agents.function_tool
    async def controle_volume(self, nivel: int):
        """Ajusta o volume do sistema do computador (nivel de 0 a 100)."""
        return self.jarvis_control.controle_volume(nivel)

    @agents.function_tool
    async def controle_brilho(self, nivel: int):
        """Ajusta o brilho da tela do computador (nivel de 0 a 100)."""
        return self.jarvis_control.controle_brilho(nivel)

    @agents.function_tool
    async def atalhos_navegacao(self, site: str):
        """Abre sites cadastrados nos atalhos (ex: youtube, github, chatgpt, google)."""
        return self.jarvis_control.atalhos_navegacao(site)

    @agents.function_tool
    async def pesquisar_no_google(self, termo: str):
        """Pesquisa um termo no Google no navegador padrão."""
        return self.jarvis_control.pesquisar_no_google(termo)

    @agents.function_tool
    async def energia_pc(self, acao: str):
        """Gerencia a energia do computador (acoes permitidas: desligar, reiniciar, bloquear)."""
        return self.jarvis_control.energia_pc(acao)

    @agents.function_tool
    async def abrir_aplicativo(self, nome_app: str):
        """Abre aplicativos no computador pelo nome (ex: bloco de notas, calculadora, cmd, navegador, word)."""
        return self.jarvis_control.abrir_aplicativo(nome_app)


# ==========================================
# ENTRYPOINT
# ==========================================

async def entrypoint(ctx: agents.JobContext):

    mem0 = AsyncMemoryClient()
    user_id = "PedroLucas"

    # ==================================
    # CARREGAR MEMÓRIA
    # ==================================

    initial_ctx = ChatContext()
    memory_text = ""

    try:
        results = await mem0.get_all(user_id=user_id)
        logger.info(f"Memórias carregadas: {len(results) if results else 0}")
    except Exception as e:
        logger.warning(f"Erro ao carregar memória: {e}")
        results = []

    if results:
        memories = [
            result.get("memory")
            for result in results
            if isinstance(result, dict) and result.get("memory")
        ]

        if memories:
            memory_text = "\n".join(f"- {m}" for m in memories)

            initial_ctx.add_message(
                role="assistant",
                content=f"""
O nome do usuário é {user_id}.
Aqui estão informações importantes sobre ele:
{memory_text}
Use essas informações naturalmente durante a conversa.
"""
            )

    await ctx.connect()

    session = AgentSession()
    agent = Assistant(chat_ctx=initial_ctx)

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # ==================================
    # SALVAR MEMÓRIA NO ENCERRAMENTO
    # ==================================

    async def shutdown_hook():
        try:
            messages = []

            for item in session._agent.chat_ctx.items:
                if not hasattr(item, "content") or not item.content:
                    continue

                if item.role in ["user", "assistant"]:
                    content_str = (
                        "".join(item.content)
                        if isinstance(item.content, list)
                        else str(item.content)
                    )

                    messages.append(
                        {
                            "role": item.role,
                            "content": content_str.strip(),
                        }
                    )

            if messages:
                await mem0.add(messages, user_id=user_id)
                logger.info("Memória salva com sucesso.")

        except Exception as e:
            logger.warning(f"Erro ao salvar memória: {e}")

    ctx.add_shutdown_callback(shutdown_hook)

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION
        + "\nCumprimente o usuário de forma breve, confiante e natural."
    )


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint)
    )