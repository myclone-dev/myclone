"""
Pydantic schemas for the application

This module contains all Pydantic models used for data validation,
serialization, and API contracts.
"""

from .knowledge_library import (
    AttachKnowledgeRequest,
    AvailableKnowledgeSource,
    AvailableKnowledgeSourcesResponse,
    DeleteKnowledgeSourceResponse,
    DocumentKnowledgeSource,
    KnowledgeLibraryResponse,
    KnowledgeSourceAttachment,
    KnowledgeSourceBase,
    LinkedInKnowledgeSource,
    PersonaCreateWithKnowledge,
    PersonaKnowledgeResponse,
    PersonaKnowledgeSource,
    PersonaUpdateWithKnowledge,
    PersonaWithKnowledgeResponse,
    ReIngestKnowledgeSourceResponse,
    TwitterKnowledgeSource,
    UserPersonasResponse,
    WebsiteKnowledgeSource,
    YouTubeKnowledgeSource,
)
from .livekit import (
    LiveKitDispatchMetadata,
    PatternMetadata,
    PersonaMetadata,
    PersonaPromptMetadata,
)
from .scraping import (  # LinkedIn; Twitter; Website
    LinkedInData,
    LinkedInExperience,
    LinkedInPost,
    LinkedInProfileData,
    TwitterData,
    TwitterProfileData,
    TwitterTweet,
    WebsiteData,
    WebsiteMetadata,
    WebsitePage,
)
from .stripe import (
    AccessValidationResponse,
    AccountTypeEnum,
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    CreatePersonaCheckoutRequest,
    EnablePersonaMonetizationRequest,
    PersonaAccessPurchaseResponse,
    PersonaPricingResponse,
    PersonaPricingWithAccessResponse,
    PlatformStripeSubscriptionResponse,
    PricingModelEnum,
    PurchaseStatusEnum,
    StripeCustomerResponse,
    StripeWebhookEventResponse,
    UpdatePersonaPricingRequest,
    VisitorSignupRequest,
    WebhookEventSummary,
)
from .tier import (
    SubscriptionCreateRequest,
    SubscriptionStatusEnum,
    SubscriptionUpgradeRequest,
    TierPlanResponse,
    UserSubscriptionResponse,
    UserUsageCacheResponse,
    UserUsageWithLimitsResponse,
)

__all__ = [
    # LiveKit schemas
    "PersonaMetadata",
    "PatternMetadata",
    "LiveKitDispatchMetadata",
    "PersonaPromptMetadata",
    # Tier and subscription schemas
    "SubscriptionStatusEnum",
    "TierPlanResponse",
    "UserSubscriptionResponse",
    "UserUsageCacheResponse",
    "UserUsageWithLimitsResponse",
    "SubscriptionUpgradeRequest",
    "SubscriptionCreateRequest",
    # Stripe schemas - Enums
    "AccountTypeEnum",
    "PricingModelEnum",
    "PurchaseStatusEnum",
    # Stripe schemas - Responses
    "StripeCustomerResponse",
    "PlatformStripeSubscriptionResponse",
    "PersonaPricingResponse",
    "PersonaAccessPurchaseResponse",
    "StripeWebhookEventResponse",
    "CheckoutSessionResponse",
    "AccessValidationResponse",
    "PersonaPricingWithAccessResponse",
    "WebhookEventSummary",
    # Stripe schemas - Requests
    "CreateCheckoutSessionRequest",
    "EnablePersonaMonetizationRequest",
    "UpdatePersonaPricingRequest",
    "CreatePersonaCheckoutRequest",
    "VisitorSignupRequest",
    # Scraping schemas - LinkedIn
    "LinkedInProfileData",
    "LinkedInExperience",
    "LinkedInPost",
    "LinkedInData",
    # Scraping schemas - Twitter
    "TwitterProfileData",
    "TwitterTweet",
    "TwitterData",
    # Scraping schemas - Website
    "WebsiteMetadata",
    "WebsitePage",
    "WebsiteData",
    # Knowledge Library schemas
    "KnowledgeSourceBase",
    "LinkedInKnowledgeSource",
    "TwitterKnowledgeSource",
    "WebsiteKnowledgeSource",
    "DocumentKnowledgeSource",
    "YouTubeKnowledgeSource",
    "KnowledgeLibraryResponse",
    "PersonaKnowledgeSource",
    "PersonaKnowledgeResponse",
    "AvailableKnowledgeSource",
    "AvailableKnowledgeSourcesResponse",
    "KnowledgeSourceAttachment",
    "AttachKnowledgeRequest",
    "PersonaCreateWithKnowledge",
    "PersonaUpdateWithKnowledge",
    "PersonaWithKnowledgeResponse",
    "UserPersonasResponse",
    "DeleteKnowledgeSourceResponse",
    "ReIngestKnowledgeSourceResponse",
]
