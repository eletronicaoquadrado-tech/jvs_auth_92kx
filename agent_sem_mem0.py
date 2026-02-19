from dotenv import load_dotenv # Carrega variáveis de ambiente de um arquivo .env

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    noise_cancellation, # Importa o módulo de cancelamento de ruído
     google # Importa o plugin do Google para modelos de linguagem
)
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION

load_dotenv()# Carrega as variáveis de ambiente do arquivo .env


class Assistant(Agent): # Define a classe Assistant que herda de Agent
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION, # Define as instruções do agente
            llm=google.beta.realtime.RealtimeModel( # Configura o modelo de linguagem em tempo real do Google
            voice="Charon", # Define a voz do agente
            temperature=0.6,# Define a temperatura para controle de criatividade
        ),
            
        )
        


async def entrypoint(ctx: agents.JobContext): # Função de entrada assíncrona para o agente
    session = AgentSession(
        
    )

    await session.start( 
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(# Configurações de entrada da sala
            video_enabled=True, # Habilita vídeo na sala
            noise_cancellation=noise_cancellation.BVC(),#@ Habilita o cancelamento de ruído usando o plugin BVC
        ),
    )

    await ctx.connect()

    await session.generate_reply( 
        instructions=SESSION_INSTRUCTION, # Instruções específicas para a sessão
    )


if __name__ == "__main__":# Ponto de entrada do script
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))# Executa o aplicativo de agente com a função de entrada definida
