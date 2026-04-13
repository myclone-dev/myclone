"""
Vercel Domain Service - Integration with Vercel's Domain API

Handles adding, verifying, and removing custom domains from the Vercel project.
Uses Vercel's REST API: https://vercel.com/docs/rest-api

This is similar to what Delphi does for their standalone integration:
1. User provides domain (e.g., chat.example.com)
2. We call Vercel API to add domain to project
3. Vercel returns DNS records needed for verification
4. User adds DNS records at their registrar
5. We call Vercel to verify the domain
6. Vercel provisions SSL automatically
7. Domain becomes active and routes to our app
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from shared.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DomainConfig:
    """Domain configuration from Vercel API"""

    name: str  # Domain name (e.g., chat.example.com)
    apex_name: str  # Root domain (e.g., example.com)
    project_id: str  # Vercel project ID
    redirect: Optional[str]  # Redirect target if configured
    redirect_status_code: Optional[int]  # Redirect status code
    git_branch: Optional[str]  # Git branch deployment
    updated_at: int  # Last update timestamp
    created_at: int  # Creation timestamp
    verified: bool  # Whether domain is verified
    verification: List[Dict[str, Any]]  # Verification records needed


@dataclass
class DomainVerificationRecord:
    """DNS record required for domain verification"""

    type: str  # TXT, A, CNAME, etc.
    name: str  # Record name (e.g., _vercel)
    value: str  # Record value


class VercelDomainService:
    """
    Service for managing custom domains via Vercel API

    Environment variables required:
    - VERCEL_API_TOKEN: Bearer token for Vercel API authentication
    - VERCEL_PROJECT_ID: Project ID where domains will be added
    - VERCEL_TEAM_ID: Team ID (optional, for team projects)
    """

    # Vercel's anycast IP for apex domains (IPv4)
    VERCEL_IP = "76.76.21.21"
    # Vercel's anycast IPv6 for apex domains (recommended AAAA)
    VERCEL_IPV6 = "2a06:98c1:3121::3"
    # Vercel's CNAME target for subdomains
    VERCEL_CNAME = "cname.vercel-dns.com"

    def __init__(
        self,
        api_token: Optional[str] = None,
        project_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ):
        """
        Initialize Vercel Domain Service

        Args:
            api_token: Vercel API bearer token
            project_id: Vercel project ID
            team_id: Vercel team ID (optional)
        """
        # Use direct attribute access to avoid credential exposure in error traces
        self.api_token = api_token or settings.vercel_api_token
        self.project_id = project_id or settings.vercel_project_id
        self.team_id = team_id or settings.vercel_team_id
        self.base_url = "https://api.vercel.com"

    def is_configured(self) -> bool:
        """Check if Vercel integration is configured"""
        return bool(self.api_token and self.project_id)

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _get_params(self) -> Dict[str, str]:
        """Get common query parameters"""
        params = {}
        if self.team_id:
            params["teamId"] = self.team_id
        return params

    def _is_apex_domain(self, domain: str) -> bool:
        """Check if domain is an apex (root) domain"""
        parts = domain.lower().strip().split(".")
        return len(parts) == 2

    def get_routing_record(self, domain: str) -> Dict[str, str]:
        """
        Get the primary routing DNS record for a domain.
        For apex domains, Vercel recommends adding both A (IPv4) and AAAA (IPv6).
        We return the primary record here (A for apex, CNAME for subdomains).
        A companion AAAA record is exposed via get_additional_routing_records().

        Args:
            domain: Domain name

        Returns:
            DNS record dict with type, name, value
        """
        if self._is_apex_domain(domain):
            return {
                "type": "A",
                "name": "@",
                "value": self.VERCEL_IP,
            }
        else:
            return {
                "type": "CNAME",
                "name": domain.split(".")[0],  # Subdomain part
                "value": self.VERCEL_CNAME,
            }

    async def add_domain(self, domain: str) -> Dict[str, Any]:
        """
        Add a domain to the Vercel project

        Args:
            domain: Full domain name (e.g., 'chat.example.com')

        Returns:
            Response dict with domain info and verification records

        Raises:
            Exception: If API call fails
        """
        if not self.is_configured():
            raise ValueError("Vercel integration is not configured")

        url = f"{self.base_url}/v10/projects/{self.project_id}/domains"
        params = self._get_params()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    json={"name": domain.lower().strip()},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Domain added to Vercel: {domain}")
                    logger.debug(f"Vercel API response for {domain}: {data}")

                    # Get verification records from Vercel response
                    verification_records = data.get("verification", [])

                    # If Vercel didn't return verification records, generate standard TXT record
                    # This ensures we always show users what DNS records they need to add
                    if not verification_records:
                        # Generate standard Vercel TXT verification record
                        verification_records = [
                            {
                                "type": "TXT",
                                "domain": f"_vercel.{domain}",
                                "value": f"vc-domain-verify={domain},{data.get('name', domain)}",
                                "reason": "pending_domain_verification",
                            }
                        ]
                        logger.info(
                            f"Generated fallback verification record for {domain} (Vercel returned empty)"
                        )

                    # Routing guidance (include AAAA for apex domains to avoid 'DNS Change Recommended')
                    routing_record = self.get_routing_record(domain)
                    additional_records: List[Dict[str, str]] = []
                    if self._is_apex_domain(domain):
                        additional_records.append(
                            {
                                "type": "AAAA",
                                "name": "@",
                                "value": self.VERCEL_IPV6,
                            }
                        )

                    # Format response with verification and routing records
                    return {
                        "success": True,
                        "domain": data.get("name"),
                        "apex_name": data.get("apexName"),
                        "verified": data.get("verified", False),
                        "verification_records": verification_records,
                        "routing_record": routing_record,
                        "additional_routing_records": additional_records,
                    }

                elif response.status_code == 409:
                    # Domain already exists
                    error_data = response.json()
                    error_code = error_data.get("error", {}).get("code", "")

                    if error_code == "domain_already_in_use":
                        logger.warning(f"Domain already in use: {domain}")
                        return {
                            "success": False,
                            "error": "domain_already_in_use",
                            "message": "This domain is already in use by another Vercel project",
                        }
                    elif error_code == "domain_already_exists":
                        # Domain already added to this project, get its config
                        logger.info(f"Domain already exists in project: {domain}")
                        return await self.get_domain(domain)

                    return {
                        "success": False,
                        "error": error_code,
                        "message": error_data.get("error", {}).get("message", "Domain conflict"),
                    }

                elif response.status_code == 400:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "Invalid domain")
                    logger.error(f"Invalid domain format: {domain} - {error_message}")
                    return {
                        "success": False,
                        "error": "invalid_domain",
                        "message": error_message,
                    }

                elif response.status_code == 403:
                    logger.error(f"Permission denied adding domain: {domain}")
                    return {
                        "success": False,
                        "error": "permission_denied",
                        "message": "Permission denied. Check Vercel API token permissions.",
                    }

                else:
                    error_text = response.text
                    logger.error(
                        f"Failed to add domain {domain}: {response.status_code} - {error_text}"
                    )
                    return {
                        "success": False,
                        "error": "api_error",
                        "message": f"Vercel API error: {response.status_code}",
                    }

            except httpx.TimeoutException:
                logger.error(f"Timeout adding domain to Vercel: {domain}")
                return {
                    "success": False,
                    "error": "timeout",
                    "message": "Request to Vercel timed out",
                }
            except Exception as e:
                logger.error(f"Error adding domain to Vercel: {domain} - {e}")
                return {
                    "success": False,
                    "error": "unknown",
                    "message": str(e),
                }

    async def get_domain(self, domain: str) -> Dict[str, Any]:
        """
        Get domain configuration and status (project-scoped details)
        Note: 'verified' here indicates ownership, not full DNS configuration.
        """
        if not self.is_configured():
            raise ValueError("Vercel integration is not configured")

        url = f"{self.base_url}/v9/projects/{self.project_id}/domains/{domain}"
        params = self._get_params()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    routing_record = self.get_routing_record(domain)
                    additional_records: List[Dict[str, str]] = []
                    if self._is_apex_domain(domain):
                        additional_records.append(
                            {
                                "type": "AAAA",
                                "name": "@",
                                "value": self.VERCEL_IPV6,
                            }
                        )

                    return {
                        "success": True,
                        "domain": data.get("name"),
                        "apex_name": data.get("apexName"),
                        # Ownership verified flag from Vercel
                        "verified": data.get("verified", False),
                        "verification_records": data.get("verification", []),
                        "routing_record": routing_record,
                        "additional_routing_records": additional_records,
                    }

                elif response.status_code == 404:
                    return {
                        "success": False,
                        "error": "not_found",
                        "message": "Domain not found in project",
                    }

                else:
                    return {
                        "success": False,
                        "error": "api_error",
                        "message": f"Vercel API error: {response.status_code}",
                    }

            except Exception as e:
                logger.error(f"Error getting domain from Vercel: {domain} - {e}")
                return {
                    "success": False,
                    "error": "unknown",
                    "message": str(e),
                }

    async def is_domain_configured(self, domain: str) -> Dict[str, Any]:
        """
        Check full DNS configuration using Vercel domain config endpoint.
        Returns dict with 'configured' bool and optional 'message'.
        """
        if not self.is_configured():
            raise ValueError("Vercel integration is not configured")

        url = f"{self.base_url}/v9/domains/{domain}/config"
        params = self._get_params()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    configured = bool(data.get("configured"))
                    # Vercel often provides helpful info under 'misconfigured' or 'records'
                    msg = None
                    if not configured:
                        missing = []
                        for key in ("aRecords", "aaaaRecords", "cnameRecords"):
                            vals = data.get(key) or []
                            if isinstance(vals, list) and vals:
                                missing.append(key)
                        if missing:
                            msg = "Missing DNS records: " + ", ".join(missing)
                    return {"success": True, "configured": configured, "message": msg}
                elif response.status_code == 404:
                    return {"success": False, "configured": False, "message": "Domain not found"}
                else:
                    return {
                        "success": False,
                        "configured": False,
                        "message": f"Vercel API error: {response.status_code}",
                    }
            except Exception as e:
                logger.error(f"Error checking domain config for {domain}: {e}")
                return {"success": False, "configured": False, "message": str(e)}

    async def verify_domain(self, domain: str) -> Dict[str, Any]:
        """
        Verify domain ownership and full configuration (check DNS records)

        This method:
        1. Calls Vercel's /verify endpoint to trigger verification
        2. Then calls get_domain to check actual configuration status
        3. Only returns verified=True if both ownership is verified AND no pending records remain

        Args:
            domain: Full domain name

        Returns:
            Verification result dict with 'verified' only True when fully configured
        """
        if not self.is_configured():
            raise ValueError("Vercel integration is not configured")

        url = f"{self.base_url}/v9/projects/{self.project_id}/domains/{domain}/verify"
        params = self._get_params()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    verify_data = response.json()
                    ownership_verified = verify_data.get("verified", False)
                    pending_records = verify_data.get("verification", [])

                    logger.info(
                        f"Domain verification result: {domain} - ownership_verified={ownership_verified}, "
                        f"pending_records={len(pending_records)}"
                    )

                    # IMPORTANT: Vercel's /verify endpoint returns verified=True when TXT record
                    # is found (ownership verified), but domain might still have pending
                    # A/CNAME records. We need to check if there are NO remaining verification
                    # records for the domain to be fully configured.

                    # If verify returned pending records, domain is not fully configured
                    if pending_records:
                        # Build helpful message about what's missing
                        missing_types = [r.get("type", "Unknown") for r in pending_records]
                        missing_msg = f"Missing DNS records: {', '.join(missing_types)}"

                        return {
                            "success": True,
                            "verified": False,  # Not fully verified yet
                            "ownership_verified": ownership_verified,
                            "domain": verify_data.get("name"),
                            "verification_records": pending_records,
                            "message": missing_msg,
                        }

                    # If no pending records from /verify, double-check with get_domain
                    # to ensure domain is truly ready
                    domain_config = await self.get_domain(domain)

                    if domain_config.get("success"):
                        config_verified = domain_config.get("verified", False)
                        config_pending = domain_config.get("verification_records", [])

                        logger.info(
                            f"Domain config check: {domain} - config_verified={config_verified}, "
                            f"config_pending={len(config_pending)}, ownership_verified={ownership_verified}"
                        )

                        # If there are pending records, domain is not fully configured
                        if config_pending:
                            missing_types = [r.get("type", "Unknown") for r in config_pending]
                            missing_msg = f"Missing DNS records: {', '.join(missing_types)}"
                            return {
                                "success": True,
                                "verified": False,
                                "ownership_verified": ownership_verified,
                                "domain": verify_data.get("name"),
                                "verification_records": config_pending,
                                "message": missing_msg,
                            }

                        # Only fully verified if BOTH:
                        # 1. Vercel's /verify endpoint returned verified=True (TXT record found)
                        # 2. Vercel's get_domain endpoint returned verified=True (fully configured)
                        # 3. No pending verification records
                        fully_verified = ownership_verified and config_verified

                        if not fully_verified:
                            # Domain is not fully configured but no pending records reported
                            # This can happen if DNS hasn't propagated or config is incomplete
                            return {
                                "success": True,
                                "verified": False,
                                "ownership_verified": ownership_verified,
                                "domain": verify_data.get("name"),
                                "verification_records": [],
                                "message": "Domain configuration incomplete. DNS may still be propagating.",
                            }

                        logger.info(f"Domain fully verified: {domain} - verified={fully_verified}")

                        return {
                            "success": True,
                            "verified": True,
                            "ownership_verified": ownership_verified,
                            "domain": verify_data.get("name"),
                            "verification_records": [],
                        }
                    else:
                        # get_domain failed, be conservative
                        return {
                            "success": True,
                            "verified": False,
                            "ownership_verified": ownership_verified,
                            "domain": verify_data.get("name"),
                            "verification_records": pending_records,
                            "message": "Could not confirm full domain configuration",
                        }

                elif response.status_code == 404:
                    return {
                        "success": False,
                        "verified": False,
                        "error": "not_found",
                        "message": "Domain not found in project",
                    }

                else:
                    error_data = response.json() if response.text else {}
                    return {
                        "success": False,
                        "verified": False,
                        "error": "api_error",
                        "message": error_data.get("error", {}).get(
                            "message", f"Vercel API error: {response.status_code}"
                        ),
                    }

            except Exception as e:
                logger.error(f"Error verifying domain with Vercel: {domain} - {e}")
                return {
                    "success": False,
                    "verified": False,
                    "error": "unknown",
                    "message": str(e),
                }

    async def remove_domain(self, domain: str) -> Dict[str, Any]:
        """
        Remove a domain from the Vercel project

        Args:
            domain: Full domain name

        Returns:
            Result dict
        """
        if not self.is_configured():
            raise ValueError("Vercel integration is not configured")

        url = f"{self.base_url}/v9/projects/{self.project_id}/domains/{domain}"
        params = self._get_params()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                if response.status_code in (200, 204):
                    logger.info(f"Domain removed from Vercel: {domain}")
                    return {
                        "success": True,
                        "message": "Domain removed successfully",
                    }

                elif response.status_code == 404:
                    return {
                        "success": True,
                        "message": "Domain was not found (already removed)",
                    }

                else:
                    error_text = response.text
                    logger.error(
                        f"Failed to remove domain {domain}: {response.status_code} - {error_text}"
                    )
                    return {
                        "success": False,
                        "error": "api_error",
                        "message": f"Vercel API error: {response.status_code}",
                    }

            except Exception as e:
                logger.error(f"Error removing domain from Vercel: {domain} - {e}")
                return {
                    "success": False,
                    "error": "unknown",
                    "message": str(e),
                }

    async def get_domain_config(self, domain: str) -> Dict[str, Any]:
        """
        Get full domain configuration including SSL status

        Args:
            domain: Full domain name

        Returns:
            Full domain configuration dict
        """
        if not self.is_configured():
            raise ValueError("Vercel integration is not configured")

        # First get domain status from project
        domain_result = await self.get_domain(domain)

        if not domain_result.get("success"):
            return domain_result

        # Check if domain is verified
        if domain_result.get("verified"):
            # Domain is verified, check SSL status
            # Vercel automatically provisions SSL, we can assume it's ready
            # if the domain is verified
            return {
                **domain_result,
                "ssl_ready": True,
                "status": "active",
            }
        else:
            return {
                **domain_result,
                "ssl_ready": False,
                "status": "pending_verification",
            }


# Factory function for creating service instance
def get_vercel_domain_service() -> VercelDomainService:
    """Get a configured VercelDomainService instance"""
    # Use direct attribute access to avoid credential exposure in error traces
    return VercelDomainService(
        api_token=settings.vercel_api_token,
        project_id=settings.vercel_project_id,
        team_id=settings.vercel_team_id,
    )
