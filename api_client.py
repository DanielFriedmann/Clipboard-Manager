import httpx

from service.config import HOST, PORT

BASE_URL = f"http://{HOST}:{PORT}"
TIMEOUT = 5.0          # Sekunden pro Anfrage, danach gilt der Service als nicht erreichbar
HEALTH_TIMEOUT = 0.5   # kurze Prüfung beim Start


class ServiceUnavailable(Exception):
    # keine Verbindung oder keine Antwort in der erlaubten Zeit
    pass


class ApiError(Exception):
    # der Service hat geantwortet, aber mit einem Fehler (4xx oder 5xx)
    def __init__(self, status, detail):
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


class ApiClient:
    # Schlanker Zugang zum Entry-Service: Token, Timeout und Fehler an einer Stelle

    def __init__(self, token, client=None):
        # client kann im Test ein TestClient sein, sonst eine echte Verbindung
        self._client = client or httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
        self._headers = {"Authorization": f"Bearer {token}"}

    def request(self, method, path, **kwargs):
        try:
            response = self._client.request(method, path, headers=self._headers, **kwargs)
        except httpx.TransportError as error:
            # Verbindung abgelehnt, abgebrochen oder Zeit überschritten
            raise ServiceUnavailable(str(error)) from error

        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = response.text
            raise ApiError(response.status_code, detail)

        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)

    def health(self):
        # True, wenn der Service läuft; ohne Token, mit kurzer Wartezeit
        try:
            response = self._client.get("/health", timeout=HEALTH_TIMEOUT)
            return response.status_code == 200 and response.json().get("status") == "ok"
        except (httpx.TransportError, ValueError):
            return False

    def close(self):
        self._client.close()