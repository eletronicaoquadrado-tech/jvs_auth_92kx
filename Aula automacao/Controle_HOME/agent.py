from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext, llm
from livekit.plugins import noise_cancellation, google
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from mem0 import AsyncMemoryClient
import logging
import os
import asyncio
import webbrowser
import subprocess
from urllib.parse import quote_plus
import urllib.request as _urllib

try:
    import yt_dlp
    YT_DLP_DISPONIVEL = True
except ImportError:
    YT_DLP_DISPONIVEL = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_DISPONIVEL = True
except ImportError:
    PLAYWRIGHT_DISPONIVEL = False

from automacao_jarvis import JarvisControl


# ─────────────────────────────────────────
# VOICE MONKEY — Carregamento "lazy"
# ─────────────────────────────────────────
_voicemonkey = None

def get_voicemonkey():
    global _voicemonkey
    if _voicemonkey is None:
        from integrations.voicemonkey import VoiceMonkey
        _voicemonkey = VoiceMonkey()
    return _voicemonkey

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# CHROME + CDP
# ─────────────────────────────────────────

def _get_chrome_path():
    caminhos = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in caminhos:
        if os.path.exists(c):
            return c
    return None

CHROME_PATH = _get_chrome_path()
CDP_URL = "http://localhost:9222"

def _cdp_disponivel() -> bool:
    """Verifica se o Chrome já está rodando com depuração remota."""
    try:
        with _urllib.urlopen(f"{CDP_URL}/json/version", timeout=1) as r:
            return r.status == 200
    except:
        return False

async def _abrir_chrome_com_cdp(url: str = "about:blank"):
    """Abre o Chrome com porta de depuração (CDP) e navega para a URL."""
    if not CHROME_PATH:
        webbrowser.open(url)
        return False
    # Se o Chrome já está aberto COM cdp, só abre nova aba
    if _cdp_disponivel():
        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(CDP_URL)
                page = await browser.contexts[0].new_page()
                await page.goto(url)
                await browser.disconnect()
            return True
        except:
            pass
    # Fecha o Chrome e reabre com depuração
   # subprocess.run(["taskkill", "/f", "/im", "chrome.exe"], capture_output=True)
    await asyncio.sleep(1)
    subprocess.Popen([CHROME_PATH, f"--remote-debugging-port=9222", url])
    await asyncio.sleep(2.5)
    return _cdp_disponivel()


# ─────────────────────────────────────────
# AGENTE
# ─────────────────────────────────────────

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


    # ────────────────────────────────
    # MÍDIA E WEB
    # ────────────────────────────────

    @agents.function_tool
    async def pesquisar_na_web(self, consulta: str, tipo: str = "google"):
        """
        Faz uma busca ou abre o YouTube.
        tipo = 'google' → busca no Google
        tipo = 'youtube' → abre a busca no YouTube (não inicia um vídeo automaticamente)
        tipo = 'url' → abre a URL diretamente
        """
        try:
            if tipo.lower() == "youtube":
                # Abre a BUSCA no YouTube, não um vídeo aleatório
                url = f"https://www.youtube.com/results?search_query={quote_plus(consulta)}"
                await _abrir_chrome_com_cdp(url)
                return f"Abrindo busca do YouTube por '{consulta}'."

            elif tipo.lower() == "url":
                await _abrir_chrome_com_cdp(consulta)
                return f"Abrindo: {consulta}"

            else: # google (padrão)
                url = f"https://www.google.com/search?q={quote_plus(consulta)}"
                await _abrir_chrome_com_cdp(url)
                return f"Pesquisando '{consulta}' no Google."
        except Exception as e:
            return f"Erro na pesquisa: {e}"

    @agents.function_tool
    async def pausar_retomar_youtube(self):
        """Pausa ou retoma o vídeo do YouTube que estiver tocando no Chrome."""
        try:
            # Estratégia 1: Keyboard shortcut via pygetwindow (mais confiável)
            try:
                import pygetwindow as gw
                import pyautogui
                import time

                # Procura janelas do Chrome que contenham "YouTube"
                janelas_yt = [w for w in gw.getAllWindows()
                              if "youtube" in w.title.lower() and w.visible]

                if janelas_yt:
                    janela = janelas_yt[0]
                    janela.activate()   # traz o Chrome para frente
                    time.sleep(0.4)     # aguarda o foco
                    pyautogui.press("k")  # 'K' = play/pause no YouTube
                    return "Play/Pause alternado no YouTube ✓"
            except ImportError:
                pass  # pygetwindow/pyautogui não instalados, tenta CDP

            # Estratégia 2: CDP (só funciona se Chrome foi aberto com --remote-debugging-port)
            if PLAYWRIGHT_DISPONIVEL and _cdp_disponivel():
                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(CDP_URL)
                    for ctx in browser.contexts:
                        for page in ctx.pages:
                            if "youtube.com/watch" in page.url:
                                await page.evaluate(
                                    "const v = document.querySelector('video'); if(v) { v.paused ? v.play() : v.pause(); }"
                                )
                                await browser.disconnect()
                                return "Play/Pause alternado via CDP ✓"
                    await browser.disconnect()
                return "Nenhum vídeo do YouTube encontrado no Chrome."

            return ("Não foi possível controlar o YouTube. "
                    "Instale pygetwindow e pyautogui: pip install pygetwindow pyautogui")
        except Exception as e:
            return f"Erro no controle de mídia: {e}"

    @agents.function_tool
    async def fechar_programa(self, programa: str):
        """Fecha um programa pelo nome (ex: 'chrome', 'notepad')."""
        exe = programa if programa.lower().endswith(".exe") else f"{programa}.exe"
        res = subprocess.run(["taskkill", "/f", "/im", exe], capture_output=True)
        if res.returncode == 0:
            return f"Programa '{programa}' fechado com sucesso."
        return f"Não foi possível fechar '{programa}'. Verifique o nome do processo."

    @agents.function_tool
    async def abrir_programa(self, comando: str):
        """Abre um programa ou executável pelo nome ou caminho (ex: 'notepad', 'calc')."""
        try:
            subprocess.Popen(comando, shell=True)
            return f"'{comando}' aberto."
        except Exception as e:
            return f"Erro ao abrir '{comando}': {e}"

    # ────────────────────────────────
    # ARQUIVOS E PASTAS
    # ────────────────────────────────

    @agents.function_tool
    async def criar_pasta(self, caminho: str):
        """
        Cria uma pasta. Exemplos de comandos válidos:
        - 'Projetos' → cria na Área de Trabalho
        - 'Projetos/Python' → cria subpasta na Área de Trabalho
        - 'Desktop/Projetos' → equivale a Área de Trabalho
        NÃO inclua 'C:/' ou caminhos absolutos, apenas o nome da pasta.
        """
        return self.jarvis_control.cria_pasta(caminho)

    @agents.function_tool
    async def deletar_item(self, caminho: str):
        """Deleta um arquivo ou pasta pelo nome ou caminho."""
        return self.jarvis_control.deletar_arquivo(caminho)

    @agents.function_tool
    async def limpar_diretorio(self, caminho: str):
        """Remove todo o conteúdo de uma pasta, sem deletar a pasta em si."""
        return self.jarvis_control.limpar_diretorio(caminho)

    @agents.function_tool
    async def mover_item(self, origem: str, destino: str):
        """Move um arquivo ou pasta de origem para destino."""
        return self.jarvis_control.mover_item(origem, destino)

    @agents.function_tool
    async def copiar_item(self, origem: str, destino: str):
        """Copia um arquivo ou pasta para um novo local."""
        return self.jarvis_control.copiar_item(origem, destino)

    @agents.function_tool
    async def renomear_item(self, caminho: str, novo_nome: str):
        """Renomeia um arquivo ou pasta."""
        return self.jarvis_control.renomear_item(caminho, novo_nome)

    @agents.function_tool
    async def organizar_pasta(self, caminho: str):
        """Organiza os arquivos de uma pasta por tipo (Imagens, Documentos, etc.)."""
        return self.jarvis_control.organizar_pasta(caminho)

    @agents.function_tool
    async def compactar_pasta(self, caminho: str):
        """Compacta uma pasta em um arquivo .zip."""
        return self.jarvis_control.compactar_pasta(caminho)

    @agents.function_tool
    async def abrir_pasta(self, nome_pasta: str):
        """Abre uma pasta no Explorador de Arquivos pelo nome."""
        return self.jarvis_control.abrir_pasta(nome_pasta)

    @agents.function_tool
    async def buscar_e_abrir_arquivo(self, nome_arquivo: str):
        """Busca um arquivo por nome e o abre automaticamente."""
        return self.jarvis_control.buscar_e_abrir_arquivo(nome_arquivo)

    # ────────────────────────────────
    # SISTEMA
    # ────────────────────────────────

    @agents.function_tool
    async def controle_volume(self, nivel: int):
        """Ajusta o volume do sistema de 0 a 100."""
        return self.jarvis_control.controle_volume(nivel)

    @agents.function_tool
    async def controle_brilho(self, nivel: int):
        """Ajusta o brilho da tela de 0 a 100."""
        return self.jarvis_control.controle_brilho(nivel)

    @agents.function_tool
    async def energia_pc(self, acao: str):
        """Controla a energia do PC. Ações: 'desligar', 'reiniciar', 'bloquear'."""
        return self.jarvis_control.energia_pc(acao)

    @agents.function_tool
    async def abrir_aplicativo(self, nome_app: str):
        """Abre aplicativos conhecidos pelo nome (ex: 'chrome', 'vscode', 'calculadora')."""
        return self.jarvis_control.abrir_aplicativo(nome_app)

    # ────────────────────────────────
    # CASA INTELIGENTE (Voice Monkey)
    # ────────────────────────────────

    @agents.function_tool
    async def controlar_casa(self, dispositivo: str, acao: str = "ligar") -> str:
        """
        Controla dispositivos inteligentes da casa (luzes, ventilador, ar-condicionado, etc.)
        via Voice Monkey + Alexa.
        Use quando o usuário pedir para ligar ou desligar algo em casa.

        Args:
            dispositivo: Nome do dispositivo (ex: 'ventilador', 'luz', 'ar', 'tomada')
            acao: O que fazer — 'ligar' (padrão) ou 'desligar'
        """
        vm   = get_voicemonkey()
        base = dispositivo.lower().replace(" ", "")
        acao = acao.lower().strip()

        base_msg = "ligar" if acao == "ligar" else "desligar"
        print(f"DEBUG: controlar_casa chamado para {dispositivo} com acao {acao}")
        logger.info(f"Tentando {base_msg} dispositivo: {dispositivo}")

        # Filtra as variações baseadas na ação pretendida
        if acao == "ligar":
            variacoes = [f"ligar-{base}", f"ligar{base}", base, f"{base}-on", f"{base}-ligar", f"ligar_{base}"]
        else:
            variacoes = [f"desligar-{base}", f"desligar{base}", f"{base}-off", f"{base}-desligar", f"desligar_{base}"]

        # Tenta as variações na ordem
        for tentativa in variacoes:
            logger.debug(f"VoiceMonkey: tentando ID '{tentativa}'...")
            resultado = await asyncio.to_thread(vm.trigger_monkey, tentativa)
            if "sucesso" in resultado:
                return f"Comando '{acao}' para '{dispositivo}' executado com sucesso (ID: {tentativa})."

        return (
            f"Não consegui {acao} o {dispositivo}. "
            f"Tentei os IDs: {', '.join(variacoes)}. "
            f"Verifique se o Monkey existe no painel do Voice Monkey."
        )


# ─────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────

async def entrypoint(ctx: agents.JobContext):

    mem0_client = AsyncMemoryClient()
    user_id = "PedroLucas"

    await ctx.connect()

    session = AgentSession()
    agent = Assistant(chat_ctx=ChatContext())

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # ── Carregar Memória de Longo Prazo ─────────────────
    # NOTA: Na API v2 do Mem0, user_id vai dentro de 'filters'
    try:
        logger.info(f"[Mem0] Carregando memórias para '{user_id}'...")
        response = await mem0_client.search(
            query="histórico, preferências e informações pessoais do usuário",
            filters={"user_id": user_id},
            limit=20,
        )
        # O retorno da v2 pode ser dict com "results" ou lista direta
        if isinstance(response, dict):
            results = response.get("results", [])
        elif isinstance(response, list):
            results = response
        else:
            results = []

        logger.info(f"[Mem0] {len(results)} memórias encontradas.")

        if results:
            memorias = []
            for r in results:
                texto = None
                if isinstance(r, dict):
                    texto = r.get("memory") or r.get("text") or r.get("content")
                if texto:
                    memorias.append(f"- {texto}")

            if memorias:
                bloco = "\n".join(memorias)
                ctx_copia = agent.chat_ctx.copy()
                ctx_copia.add_message(
                    role="assistant",
                    content=f"[Memória carregada — informações sobre o usuário]\n{bloco}"
                )
                await agent.update_chat_ctx(ctx_copia)
                logger.info(f"[Mem0] {len(memorias)} memórias injetadas no contexto.")
    except Exception as e:
        logger.error(f"[Mem0] Erro ao carregar memória: {e}")

    # ── Salvar Memória ao Desligar ───────────────────────
    async def shutdown_hook():
        try:
            msgs = []
            for item in session._agent.chat_ctx.items:
                if not hasattr(item, "content") or not item.content:
                    continue
                if item.role not in ("user", "assistant"):
                    continue
                conteudo = "".join(item.content) if isinstance(item.content, list) else str(item.content)
                conteudo = conteudo.strip()
                if conteudo:
                    msgs.append({"role": item.role, "content": conteudo})
            if msgs:
                await mem0_client.add(msgs, user_id=user_id)
                logger.info(f"[Mem0] {len(msgs)} mensagens salvas na memória.")
        except Exception as e:
            logger.warning(f"[Mem0] Erro ao salvar memória: {e}")

    ctx.add_shutdown_callback(shutdown_hook)

    # Injeta a instrução inicial para o agente se apresentar
    await session.generate_reply(
        instructions=SESSION_INSTRUCTION + "\nCumprimente o usuário de forma natural e confiante. Pergunte como pode ajudar hoje."
    )

    # Aguarda o encerramento do worker de forma segura
    # (Removido o exit imediato para permitir interação contínua no console)


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))