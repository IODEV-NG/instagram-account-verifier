"""Health check endpoints for API status and provider health."""


from fastapi import APIRouter

from app.schemas.response import HealthStatus, ProviderHealth

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus, summary="API Health Check")
async def health_check() -> HealthStatus:
    """Check API health status.

    Returns basic health information about the API service.
    """
    return HealthStatus(
        status="ok",
        version="0.1.0",
    )


@router.get(
    "/health/providers",
    response_model=list[ProviderHealth],
    summary="Provider Health Status",
)
async def provider_health() -> list[ProviderHealth]:
    """Check health status of all configured providers.

    Returns the status of each verification provider:
        - meta: Meta API provider status
        - public_web: Public web provider status
    """
    from app.config import get_settings
    from app.providers.base import MetaProvider, PublicWebProvider

    settings = get_settings()
    result: list[ProviderHealth] = []

    # Check Meta provider
    if settings.meta_configured:
        meta_provider = MetaProvider(settings)
        result.append(
            ProviderHealth(
                name=meta_provider.name,
                status="configured" if meta_provider.is_configured else "unconfigured",
            )
        )
    else:
        result.append(ProviderHealth(name="meta", status="unconfigured"))

    # Check Public Web provider
    if settings.public_web_enabled:
        public_web_provider = PublicWebProvider(settings)
        result.append(
            ProviderHealth(
                name=public_web_provider.name,
                status=(
                    "configured" if public_web_provider.is_configured else "disabled"
                ),
            )
        )
    else:
        result.append(ProviderHealth(name="public_web", status="disabled"))

    return result
