import os
from pathlib import Path
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

class FileTokenStorage:
    """Single-operator token store. Replace with encrypted DB/KMS storage for multi-user production."""
    def __init__(self, token_file: str):
        self.token_file=Path(token_file)
        stem = self.token_file.stem
        client_stem = stem.removesuffix("_token") + "_client"
        self.client_file=self.token_file.with_name(client_stem + self.token_file.suffix)
    async def get_tokens(self):
        return OAuthToken.model_validate_json(self.token_file.read_text()) if self.token_file.exists() else None
    async def set_tokens(self,tokens):
        self.token_file.parent.mkdir(parents=True,exist_ok=True); self.token_file.write_text(tokens.model_dump_json(indent=2)); os.chmod(self.token_file,0o600)
    async def get_client_info(self):
        return OAuthClientInformationFull.model_validate_json(self.client_file.read_text()) if self.client_file.exists() else None
    async def set_client_info(self,info):
        self.client_file.parent.mkdir(parents=True,exist_ok=True); self.client_file.write_text(info.model_dump_json(indent=2)); os.chmod(self.client_file,0o600)
