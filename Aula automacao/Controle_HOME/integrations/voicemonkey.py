import requests
import os
import logging

logger = logging.getLogger(__name__)

class VoiceMonkey:
    def __init__(self, token=None, secret=None, access=None):
        # Tenta pegar as várias combinações de tokens
        self.access = access or os.getenv("VOICEMONKEY_ACCESS_TOKEN")
        self.secret = secret or os.getenv("VOICEMONKEY_SECRET_TOKEN")
        self.token = token or os.getenv("VOICEMONKEY_TOKEN")
        
        # Se tiver um token com "_", é provável que seja um token v2 composto ou Access_Secret do v1
        if self.token and "_" in self.token and not (self.access and self.secret):
            parts = self.token.split("_", 1)
            self.access = parts[0]
            self.secret = parts[1]

        if not (self.token or (self.access and self.secret)):
            logger.warning("VoiceMonkey: Nenhuma credencial encontrada. Verifique o seu arquivo .env")

        self.url_v1 = "https://api.voicemonkey.io/trigger"
        self.url_v2 = "https://api-v2.voicemonkey.io/trigger"

    def trigger_monkey(self, device_or_monkey: str) -> str:
        """
        Dispara um trigger no VoiceMonkey.
        Tenta a API v2 (monkey e device) primeiro; em caso de falha, faz fallback para a v1.
        """
        errors = []
        token_v2 = self.token or (
            f"{self.access}_{self.secret}" if self.access and self.secret else None
        )

        # 1. Tenta API v2 (prioritário)
        if token_v2:
            # Tenta como 'monkey' primeiro e depois como 'device' se falhar
            for param_name in ["monkey", "device"]:
                try:
                    params = {"token": token_v2, param_name: device_or_monkey}
                    response = requests.get(self.url_v2, params=params, timeout=10)
                    resp_json = response.json()

                    if response.status_code == 200 and resp_json.get("success"):
                        print(f"DEBUG: VoiceMonkey v2 ({param_name}) Sucesso para '{device_or_monkey}'")
                        return f"Comando '{device_or_monkey}' enviado com sucesso (v2 {param_name})."
                    
                    # Se for erro 400 e estivermos no 'monkey', tenta o próximo (device)
                    if response.status_code == 400 and param_name == "monkey":
                        continue

                    err_msg = resp_json.get("error", "unknown error")
                    print(f"DEBUG: VoiceMonkey v2 ({param_name}) Falha '{device_or_monkey}': {response.status_code} - {err_msg}")
                    errors.append(f"v2 {param_name}: {err_msg}")
                except Exception as e:
                    errors.append(f"v2 {param_name} exception: {str(e)}")

        # 2. Fallback para API v1 (se configurado)
        if self.access and self.secret:
            try:
                params = {
                    "access_token": self.access,
                    "secret_token": self.secret,
                    "monkey": device_or_monkey
                }
                response = requests.get(self.url_v1, params=params, timeout=10)
                resp_json = response.json()
                if response.status_code == 200 and (resp_json.get("status") == "success" or resp_json.get("success")):
                    print(f"DEBUG: VoiceMonkey v1 Sucesso para '{device_or_monkey}'")
                    return f"Comando '{device_or_monkey}' enviado com sucesso (v1)."
                errors.append(f"v1 error: {response.status_code}")
            except Exception as e:
                errors.append(f"v1 exception: {str(e)}")

        if not errors:
            return "Erro: Credenciais do VoiceMonkey ausentes ou token inválido."
        
        return f"Falha ao acionar '{device_or_monkey}'. Detalhes: {'; '.join(errors)}"
