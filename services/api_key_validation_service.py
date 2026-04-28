import requests
from pydantic import BaseModel


class ApiKeyValidationRequest(BaseModel):
    raw_key: str


class ApiKeyValidationService:
    def __init__(self, api_key_service_url: str = "http://localhost:8080/validate"):
        self.api_key_service_url = api_key_service_url
    def validate(self,req: ApiKeyValidationRequest) -> bool:
        try:
            response = requests.post(
                url=self.api_key_service_url,
                json={"raw_key": req.raw_key},
                timeout=5,
            )
            response.raise_for_status()
            return response.json().get("valid", False)
        except requests.RequestException:
            return False