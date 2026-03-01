import os
import shutil
import webbrowser
import zipfile
import subprocess
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import screen_brightness_control as sbc

class JarvisControl:
    def __init__(self):
        self.shortcuts = {
            "youtube": "https://www.youtube.com",
            "github": "https://www.github.com",
            "chatgpt": "https://chat.openai.com",
            "google": "https://www.google.com"
        }

    # --- Manipulação de Arquivos e Pastas ---

    def cria_pasta(self, caminho):
        try:
            os.makedirs(caminho, exist_ok=True)
            return f"Pasta criada com sucesso em: {caminho}"
        except Exception as e:
            return f"Erro ao criar pasta: {str(e)}"

    def deletar_arquivo(self, caminho):
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
                return f"Arquivo {caminho} deletado."
            elif os.path.isdir(caminho):
                shutil.rmtree(caminho)
                return f"Diretório {caminho} deletado."
            else:
                return "Caminho não encontrado."
        except Exception as e:
            return f"Erro ao deletar item: {str(e)}"

    def limpar_diretorio(self, caminho):
        try:
            if os.path.exists(caminho):
                for item in os.listdir(caminho):
                    item_path = os.path.join(caminho, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                return f"Diretório {caminho} limpo."
            return "Diretório não encontrado."
        except Exception as e:
            return f"Erro ao limpar diretório: {str(e)}"

    def mover_item(self, origem, destino):
        try:
            shutil.move(origem, destino)
            return f"Item movido de {origem} para {destino}."
        except Exception as e:
            return f"Erro ao mover item: {str(e)}"

    def copiar_item(self, origem, destino):
        try:
            if os.path.isdir(origem):
                shutil.copytree(origem, destino)
            else:
                shutil.copy2(origem, destino)
            return f"Item copiado de {origem} para {destino}."
        except Exception as e:
            return f"Erro ao copiar item: {str(e)}"

    def renomear_item(self, caminho, novo_nome):
        try:
            diretorio = os.path.dirname(caminho)
            novo_caminho = os.path.join(diretorio, novo_nome)
            os.rename(caminho, novo_caminho)
            return f"Item renomeado para {novo_nome}."
        except Exception as e:
            return f"Erro ao renomear item: {str(e)}"

    def organizar_pasta(self, caminho):
        try:
            extensoes = {
                'Imagens': ['.jpg', '.jpeg', '.png', '.gif', '.bmp'],
                'Documentos': ['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.pptx'],
                'Videos': ['.mp4', '.mkv', '.avi', '.mov'],
                'Musicas': ['.mp3', '.wav', '.flac'],
                'Compactados': ['.zip', '.rar', '.7z'],
                'Executaveis': ['.exe', '.msi']
            }

            for item in os.listdir(caminho):
                item_path = os.path.join(caminho, item)
                if os.path.isfile(item_path):
                    ext = os.path.splitext(item)[1].lower()
                    movido = False
                    for pasta, exts in extensoes.items():
                        if ext in exts:
                            pasta_destino = os.path.join(caminho, pasta)
                            os.makedirs(pasta_destino, exist_ok=True)
                            shutil.move(item_path, os.path.join(pasta_destino, item))
                            movido = True
                            break
                    if not movido:
                        pasta_outros = os.path.join(caminho, 'Outros')
                        os.makedirs(pasta_outros, exist_ok=True)
                        shutil.move(item_path, os.path.join(pasta_outros, item))
            return "Pasta organizada com sucesso."
        except Exception as e:
            return f"Erro ao organizar pasta: {str(e)}"

    def compactar_pasta(self, caminho):
        try:
            nome_zip = caminho + ".zip"
            shutil.make_archive(caminho, 'zip', caminho)
            return f"Pasta compactada em: {nome_zip}"
        except Exception as e:
            return f"Erro ao compactar pasta: {str(e)}"

    # --- Controle de Sistema ---

    def controle_volume(self, nivel):
        """Define o volume entre 0 e 100"""
        try:
            nivel = max(0, min(100, int(nivel)))
            import comtypes
            comtypes.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            # O pycaw usa escala de 0.0 a 1.0 (ou decibéis)
            volume.SetMasterVolumeLevelScalar(nivel / 100, None)
            return f"Volume ajustado para {nivel}%."
        except Exception as e:
            return f"Erro ao ajustar volume: {str(e)}"

    def controle_brilho(self, nivel):
        """Define o brilho entre 0 e 100"""
        try:
            nivel = max(0, min(100, int(nivel)))
            sbc.set_brightness(nivel)
            return f"Brilho ajustado para {nivel}%."
        except Exception as e:
            return f"Erro ao ajustar brilho: {str(e)}"

    def abrir_aplicativo(self, nome_app):
        """Abre um aplicativo no sistema pelo nome."""
        try:
            apps = {
                "bloco de notas": "notepad.exe",
                "calculadora": "calc.exe",
                "paint": "mspaint.exe",
                "cmd": "cmd.exe",
                "navegador": "start msedge",
                "word": "start winword",
                "excel": "start excel",
                "powerpoint": "start powerpnt",
                "explorador de arquivos": "explorer.exe",
                "configuracoes": "start ms-settings:"
            }
            comando = apps.get(nome_app.lower())
            if comando:
                if comando.startswith("start "):
                    # Extrai o nome do executável depois de 'start '
                    executavel = comando.replace("start ", "", 1).strip()
                    try:
                        os.startfile(executavel)
                    except FileNotFoundError:
                        # Se startfile falhar (ex: ms-settings:), tentamos o subprocess de forma detachada
                        subprocess.Popen(['cmd', '/c', 'start', '', executavel], shell=True)
                else:
                    # Aplicativos normais (.exe)
                    subprocess.Popen(comando, shell=False)
                return f"Abrindo o aplicativo {nome_app}."
            else:
                # Tenta abrir pelo nome diretamente usando startfile ou fallback com shell
                try:
                    os.startfile(nome_app)
                except Exception:
                    subprocess.Popen(['cmd', '/c', 'start', '', nome_app], shell=True)
                return f"Tentando abrir o aplicativo {nome_app}."
        except Exception as e:
            return f"Erro ao abrir aplicativo: {str(e)}"

    def atalhos_navegacao(self, site):
        try:
            url = self.shortcuts.get(site.lower())
            if url:
                os.startfile(url)
                return f"Abrindo {site}."
            return "Site não cadastrado nos atalhos."
        except Exception as e:
            return f"Erro ao abrir site: {str(e)}"

    def pesquisar_no_google(self, termo):
        try:
            import urllib.parse
            termo_url = urllib.parse.quote_plus(termo)
            url = f"https://www.google.com/search?q={termo_url}"
            os.startfile(url)
            return f"Pesquisando por {termo} no Google."
        except Exception as e:
            return f"Erro ao pesquisar: {str(e)}"

    def energia_pc(self, acao):
        try:
            if acao == "desligar":
                os.system("shutdown /s /t 1")
                return "Desligando o computador."
            elif acao == "reiniciar":
                os.system("shutdown /r /t 1")
                return "Reiniciando o computador."
            elif acao == "bloquear":
                # Rundll32 para bloquear no Windows
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
                return "Computador bloqueado."
            return "Ação de energia inválida."
        except Exception as e:
            return f"Erro ao executar comando de energia: {str(e)}"

if __name__ == "__main__":
    # Teste rápido de caminhos dinâmicos
    user_home = os.path.expanduser('~')
    print(f"Home do usuário detectada: {user_home}")
    jarvis = JarvisControl()
    # jarvis.atalhos_navegacao("github")
