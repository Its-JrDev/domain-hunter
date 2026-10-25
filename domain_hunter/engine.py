"""Motor de verificación de disponibilidad de dominios.
Combina DNS asíncrono, RDAP oficial (RFC 7480/9082) y WHOIS socket TCP.
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator

import dns.asyncresolver
import httpx


@dataclass
class DomainResult:
    domain: str
    tld: str
    status: str  # "available", "taken", "unknown", "error"
    dns_active: bool = False
    registrar: str | None = None
    created_date: str | None = None
    expiry_date: str | None = None
    nameservers: list[str] = field(default_factory=list)
    status_codes: list[str] = field(default_factory=list)
    notes: str = ""
    is_favorite: bool = False

    @property
    def is_available(self) -> bool:
        return self.status == "available"

    @property
    def is_taken(self) -> bool:
        return self.status == "taken"

    @property
    def display_status(self) -> str:
        if self.status == "available":
            return "✓ DISPONIBLE"
        elif self.status == "taken":
            return "✗ OCUPADO"
        elif self.status == "unknown":
            return "? INDETERMINADO"
        else:
            return "⚠ ERROR"


# Servidores WHOIS conocidos para TLDs clave
KNOWN_WHOIS_SERVERS: dict[str, str] = {
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "org": "whois.pir.org",
    "io": "whois.nic.io",
    "ai": "whois.nic.ai",
    "co": "whois.nic.co",
    "dev": "whois.nic.google",
    "app": "whois.nic.google",
    "xyz": "whois.nic.xyz",
    "es": "whois.nic.es",
    "me": "whois.nic.me",
    "lat": "whois.nic.lat",
    "mx": "whois.nic.mx",
    "cl": "whois.nic.cl",
    "tech": "whois.nic.tech",
    "online": "whois.nic.online",
}

AVAILABLE_INDICATORS = (
    "no match",
    "not found",
    "domain not found",
    "no data found",
    "status: free",
    "status: available",
    "not registered",
    "object not found",
    "no entries found",
    "domain status: available",
    "is available",
    "nothing found",
)


class DomainEngine:
    def __init__(self, timeout: float = 5.0, user_agent: str | None = None) -> None:
        self.timeout = timeout
        self.user_agent = user_agent or "DomainHunter/1.0 (TUI Domain Tool; https://github.com/jr/domain-hunter)"
        self._resolver: dns.asyncresolver.Resolver | None = None

    def _get_resolver(self) -> dns.asyncresolver.Resolver:
        if self._resolver is None:
            self._resolver = dns.asyncresolver.Resolver()
            self._resolver.timeout = 2.0
            self._resolver.lifetime = 3.0
            # Usar DNS públicos rápidos para consistencia
            self._resolver.nameservers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
        return self._resolver

    async def check_dns(self, domain: str) -> tuple[bool, list[str]]:
        """Verifica rápidamente si el dominio responde a NS o SOA en DNS."""
        resolver = self._get_resolver()
        nameservers: list[str] = []
        try:
            ans = await resolver.resolve(domain, "NS")
            nameservers = [str(r).rstrip(".").lower() for r in ans]
            if nameservers:
                return True, nameservers
        except Exception:
            pass

        try:
            ans_soa = await resolver.resolve(domain, "SOA")
            if ans_soa:
                return True, []
        except Exception:
            pass

        return False, []

    def _parse_rdap_data(self, data: dict[str, Any], result: DomainResult) -> None:
        """Extrae registrador, fechas y servidores de la respuesta RDAP."""
        # Registrar
        entities = data.get("entities", [])
        for ent in entities:
            roles = ent.get("roles", [])
            if "registrar" in roles:
                vcard = ent.get("vcardArray", [])
                if len(vcard) > 1 and isinstance(vcard[1], list):
                    for item in vcard[1]:
                        if isinstance(item, list) and len(item) > 3 and item[0] == "fn":
                            result.registrar = str(item[3])
                            break
                if not result.registrar and "handle" in ent:
                    result.registrar = str(ent.get("handle"))

        # Fechas de eventos
        events = data.get("events", [])
        for ev in events:
            action = ev.get("eventAction")
            date_str = ev.get("eventDate", "")
            if date_str:
                try:
                    # Truncar o formatear fecha ISO
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    fmt = dt.strftime("%Y-%m-%d")
                except Exception:
                    fmt = date_str[:10]

                if action == "registration":
                    result.created_date = fmt
                elif action == "expiration":
                    result.expiry_date = fmt

        # Nameservers
        ns_list = data.get("nameservers", [])
        for ns in ns_list:
            ldh = ns.get("ldhName")
            if ldh and ldh.lower() not in result.nameservers:
                result.nameservers.append(ldh.lower())

        # Status
        statuses = data.get("status", [])
        if isinstance(statuses, list):
            result.status_codes = [str(s) for s in statuses]

    async def check_rdap(self, domain: str, client: httpx.AsyncClient) -> tuple[str, dict[str, Any]]:
        """Consulta RDAP oficial vía HTTPS."""
        url = f"https://rdap.org/domain/{domain}"
        try:
            resp = await client.get(url, timeout=self.timeout)
            if resp.status_code == 404:
                return "available", {}
            elif resp.status_code == 200:
                try:
                    return "taken", resp.json()
                except Exception:
                    return "taken", {}
            elif resp.status_code in (400, 429, 500, 502, 503, 504):
                return "fallback", {}
            else:
                return "unknown", {}
        except httpx.HTTPError:
            return "fallback", {}
        except Exception:
            return "fallback", {}

    def _sync_whois_socket(self, domain: str, tld: str) -> str:
        """Consulta directa por socket al puerto 43."""
        server = KNOWN_WHOIS_SERVERS.get(tld, "whois.iana.org")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((server, 43))
            query = f"{domain}\r\n"
            s.send(query.encode("utf-8"))
            chunks = []
            while True:
                data = s.recv(4096)
                if not data:
                    break
                chunks.append(data)
            s.close()
            return b"".join(chunks).decode("utf-8", errors="ignore")
        except Exception as e:
            return f"Socket error: {e}"

    async def check_whois_socket(self, domain: str, tld: str) -> tuple[str, str]:
        """Consulta asíncrona mediante socket de WHOIS."""
        loop = asyncio.get_running_loop()
        raw_text = await loop.run_in_executor(None, self._sync_whois_socket, domain, tld)
        lower = raw_text.lower()
        if any(ind in lower for ind in AVAILABLE_INDICATORS):
            return "available", raw_text
        if "socket error" in lower:
            return "unknown", raw_text
        return "taken", raw_text

    async def check_domain(
        self, domain: str, client: httpx.AsyncClient | None = None
    ) -> DomainResult:
        """Verifica exhaustivamente el dominio usando DNS + RDAP + WHOIS."""
        domain = domain.strip().lower()
        parts = domain.split(".")
        tld = parts[-1] if len(parts) > 1 else ""

        result = DomainResult(domain=domain, tld=tld, status="unknown")

        # 1. DNS Pre-check rápido
        dns_active, ns_list = await self.check_dns(domain)
        result.dns_active = dns_active
        if ns_list:
            result.nameservers.extend(ns_list)

        # 2. RDAP Query
        owns_client = False
        if client is None:
            client = httpx.AsyncClient(
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
            )
            owns_client = True

        try:
            rdap_status, rdap_data = await self.check_rdap(domain, client)
            if rdap_status == "available":
                # Si RDAP da 404 pero DNS tenía NS activos, se valida si es un error de delegación
                if dns_active:
                    result.status = "taken"
                    result.notes = "Activo en DNS"
                else:
                    result.status = "available"
                return result

            elif rdap_status == "taken":
                result.status = "taken"
                self._parse_rdap_data(rdap_data, result)
                return result

            # 3. Fallback a socket WHOIS si RDAP no resolvió claramente
            whois_status, raw_whois = await self.check_whois_socket(domain, tld)
            if whois_status == "available":
                result.status = "available"
            elif whois_status == "taken":
                result.status = "taken"
                result.notes = "Confirmado por WHOIS socket"
            else:
                if dns_active:
                    result.status = "taken"
                    result.notes = "DNS activo (WHOIS indeterminado)"
                else:
                    result.status = "unknown"
                    result.notes = "Servicio WHOIS no respondió"

        except Exception as e:
            result.status = "error"
            result.notes = str(e)
        finally:
            if owns_client:
                await client.aclose()

        return result

    async def check_domains_stream(
        self,
        domains: list[str],
        max_concurrency: int = 10,
    ) -> AsyncGenerator[DomainResult, None]:
        """Verifica una lista de dominios en streaming asíncrono con control de concurrencia."""
        sem = asyncio.Semaphore(max_concurrency)
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        ) as client:

            async def _worker(dom: str) -> DomainResult:
                async with sem:
                    return await self.check_domain(dom, client)

            tasks = [asyncio.create_task(_worker(dom)) for dom in domains]
            for fut in asyncio.as_completed(tasks):
                res = await fut
                yield res
