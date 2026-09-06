"""
Cliente de exchange de apuestas. Se opera contra un exchange (Betfair) y no
contra una casa de apuestas tradicional, precisamente para evitar el
"banhammer" descrito en prompt.md: el exchange cobra comisión por transacción
y no le importa si el bot gana.

Mientras no haya credenciales reales de Betfair configuradas (BETFAIR_APP_KEY,
BETFAIR_USERNAME, BETFAIR_PASSWORD, BETFAIR_CERT_PATH), `get_exchange_client()`
retorna un `PaperExchangeClient` que simula ejecuciones en memoria/BD para
poder desarrollar y probar el resto del pipeline sin arriesgar dinero real.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

import requests
from django.conf import settings

BETFAIR_IDENTITY_URL = "https://identitysso-cert.betfair.com/api/certlogin"
BETFAIR_API_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"


class ExchangeError(Exception):
    pass


@dataclass
class MarketPrice:
    market_id: str
    mercado: str  # ej. "1X2", "OVER_UNDER_2.5"
    seleccion: str
    precio_back: Decimal
    precio_lay: Decimal | None
    volumen_disponible: Decimal | None


@dataclass
class OrderResult:
    bet_id: str
    estado: str  # "MATCHED", "PENDING", "REJECTED"
    precio_igualado: Decimal | None = None
    monto_igualado: Decimal | None = None


class ExchangeClient(ABC):
    @abstractmethod
    def get_market_odds(self, market_id: str) -> list[MarketPrice]:
        ...

    @abstractmethod
    def place_order(
        self, market_id: str, seleccion: str, precio: Decimal, stake: Decimal, lado: str = "BACK"
    ) -> OrderResult:
        ...

    @abstractmethod
    def get_account_balance(self) -> Decimal:
        ...


class BetfairExchangeClient(ExchangeClient):
    """
    Implementación real vía Betfair Exchange API (JSON-RPC).
    Requiere: Application Key + certificado SSL para login no interactivo.
    Docs: https://developer.betfair.com/en/get-started/
    """

    def __init__(self):
        self.app_key = settings.BETFAIR_APP_KEY
        self.username = settings.BETFAIR_USERNAME
        self.password = settings.BETFAIR_PASSWORD
        self.cert_path = settings.BETFAIR_CERT_PATH

        if not all([self.app_key, self.username, self.password, self.cert_path]):
            raise ExchangeError(
                "Credenciales de Betfair incompletas. Configura BETFAIR_APP_KEY, "
                "BETFAIR_USERNAME, BETFAIR_PASSWORD y BETFAIR_CERT_PATH."
            )

        self._session_token: str | None = None

    def _login(self) -> str:
        response = requests.post(
            BETFAIR_IDENTITY_URL,
            cert=self.cert_path,
            headers={"X-Application": self.app_key},
            data={"username": self.username, "password": self.password},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("loginStatus") != "SUCCESS":
            raise ExchangeError(f"Login de Betfair fallido: {payload.get('loginStatus')}")

        self._session_token = payload["sessionToken"]
        return self._session_token

    def _rpc(self, method: str, params: dict) -> dict:
        if not self._session_token:
            self._login()

        response = requests.post(
            BETFAIR_API_URL,
            headers={
                "X-Application": self.app_key,
                "X-Authentication": self._session_token,
                "Content-Type": "application/json",
            },
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        if "error" in payload:
            raise ExchangeError(str(payload["error"]))

        return payload["result"]

    def get_market_odds(self, market_id: str) -> list[MarketPrice]:
        # NOTA: cada marketId de Betfair es UN solo mercado (ej. solo 1X2, o
        # solo Over/Under 2.5) -- a diferencia de api-football, no vienen
        # mezclados. Mientras no haya credenciales reales, esto asume 1X2;
        # soportar Over/Under real de Betfair implica guardar el
        # betfair_market_id de cada mercado por separado en metricas_avanzadas.
        result = self._rpc(
            "SportsAPING/v1.0/listMarketBook",
            {"marketIds": [market_id], "priceProjection": {"priceData": ["EX_BEST_OFFERS"]}},
        )
        precios = []
        for market in result:
            for runner in market.get("runners", []):
                ex = runner.get("ex", {})
                back = ex.get("availableToBack", [{}])[0]
                lay = ex.get("availableToLay", [{}])[0]
                precios.append(
                    MarketPrice(
                        market_id=market_id,
                        mercado="1X2",
                        seleccion=str(runner["selectionId"]),
                        precio_back=Decimal(str(back.get("price", 0))),
                        precio_lay=Decimal(str(lay["price"])) if lay.get("price") else None,
                        volumen_disponible=Decimal(str(back.get("size", 0))),
                    )
                )
        return precios

    def place_order(
        self, market_id: str, seleccion: str, precio: Decimal, stake: Decimal, lado: str = "BACK"
    ) -> OrderResult:
        result = self._rpc(
            "SportsAPING/v1.0/placeOrders",
            {
                "marketId": market_id,
                "instructions": [
                    {
                        "selectionId": int(seleccion),
                        "side": lado,
                        "orderType": "LIMIT",
                        "limitOrder": {
                            "size": float(stake),
                            "price": float(precio),
                            "persistenceType": "LAPSE",
                        },
                    }
                ],
            },
        )
        report = result["instructionReports"][0]
        return OrderResult(
            bet_id=report.get("betId", ""),
            estado=report["status"],
            precio_igualado=Decimal(str(report.get("averagePriceMatched", 0)) or 0) or None,
            monto_igualado=Decimal(str(report.get("sizeMatched", 0)) or 0) or None,
        )

    def get_account_balance(self) -> Decimal:
        result = self._rpc("AccountAPING/v1.0/getAccountFunds", {})
        return Decimal(str(result.get("availableToBetBalance", 0)))


class PaperExchangeClient(ExchangeClient):
    """
    Exchange simulado en memoria: usa las últimas cuotas guardadas en
    HistorialCuotas y "ejecuta" órdenes instantáneamente al precio pedido.
    Permite desarrollar y hacer backtesting/paper-trading del bot completo
    sin credenciales de Betfair.
    """

    def __init__(self, balance_inicial: Decimal | None = None):
        self._balance = (
            balance_inicial
            if balance_inicial is not None
            else Decimal(str(settings.PAPER_BANKROLL))
        )

    def get_market_odds(self, market_id: str) -> list[MarketPrice]:
        from django.db.models import Max

        from db_models.models import HistorialCuotas

        # Puede haber varios mercados (1X2, Over/Under 2.5, Over/Under 3.5, ...)
        # mezclados en el historial de este partido -- se toma la captura más
        # reciente de cada (mercado, selección), no simplemente las últimas N
        # filas (eso mezclaría snapshots viejos y nuevos de distintos mercados).
        combinaciones = HistorialCuotas.objects.filter(partido_id=market_id).values(
            "mercado", "seleccion"
        ).annotate(ultimo=Max("capturado_en"))

        registros = [
            HistorialCuotas.objects.filter(
                partido_id=market_id,
                mercado=c["mercado"],
                seleccion=c["seleccion"],
                capturado_en=c["ultimo"],
            ).first()
            for c in combinaciones
        ]

        return [
            MarketPrice(
                market_id=market_id,
                mercado=r.mercado,
                seleccion=r.seleccion,
                precio_back=r.cuota_back,
                precio_lay=r.cuota_lay,
                volumen_disponible=r.volumen_disponible,
            )
            for r in registros
            if r is not None
        ]

    def place_order(
        self, market_id: str, seleccion: str, precio: Decimal, stake: Decimal, lado: str = "BACK"
    ) -> OrderResult:
        if stake > self._balance:
            return OrderResult(bet_id="", estado="REJECTED")

        self._balance -= stake
        return OrderResult(
            bet_id=f"PAPER-{uuid.uuid4().hex[:12]}",
            estado="MATCHED",
            precio_igualado=precio,
            monto_igualado=stake,
        )

    def get_account_balance(self) -> Decimal:
        return self._balance


def get_exchange_client() -> ExchangeClient:
    """Factory: usa Betfair real si hay credenciales, si no cae a paper trading."""
    if all(
        [
            settings.BETFAIR_APP_KEY,
            settings.BETFAIR_USERNAME,
            settings.BETFAIR_PASSWORD,
            settings.BETFAIR_CERT_PATH,
        ]
    ):
        return BetfairExchangeClient()
    return PaperExchangeClient()
