# Source type constants
SOURCE_TYPE_TWITTER = "twitter"
SOURCE_TYPE_LINKEDIN = "linkedin"
SOURCE_TYPE_WEBSITE = "website"
SOURCE_TYPE_PDF = "pdf"
SOURCE_TYPE_DOCUMENT = "document"
SOURCE_TYPE_GITHUB = "github"
SOURCE_TYPE_MEDIUM = "medium"
SOURCE_TYPE_YOUTUBE = "youtube"

# Core source types actively used for scraping/ingestion (matches ScrapingJob model)
# Use this for: scraping job creation, ingestion routes, basic filtering
SOURCE_TYPES = [
    SOURCE_TYPE_LINKEDIN,
    SOURCE_TYPE_TWITTER,
    SOURCE_TYPE_WEBSITE,
    SOURCE_TYPE_PDF,
    SOURCE_TYPE_DOCUMENT,
]

# All possible source types including future integrations (matches PersonaDataSource model)
# Use this for: persona data source configuration, comprehensive filtering, status checks
ALL_SOURCE_TYPES = [
    SOURCE_TYPE_LINKEDIN,
    SOURCE_TYPE_TWITTER,
    SOURCE_TYPE_WEBSITE,
    SOURCE_TYPE_PDF,
    SOURCE_TYPE_DOCUMENT,
    SOURCE_TYPE_GITHUB,
    SOURCE_TYPE_MEDIUM,
    SOURCE_TYPE_YOUTUBE,
]

# Content types
CONTENT_TYPE_PROFILE = "profile"
CONTENT_TYPE_TWEET = "tweet"
CONTENT_TYPE_POST = "post"
CONTENT_TYPE_HOMEPAGE = "homepage"
CONTENT_TYPE_PAGE = "page"
CONTENT_TYPE_TRANSCRIPT = "transcript"
CONTENT_TYPE_PDF = "pdf_document"

# Source type categories
SOURCE_CATEGORY_SOCIAL_MEDIA = "social_media"
SOURCE_CATEGORY_INTERVIEW = "interview"
SOURCE_CATEGORY_DOCUMENT = "document"

# Other constants
TWITTER_PROFILE_SOURCE = "twitter_profile"
INTERVIEW_TRANSCRIPT_SOURCE = "interview_transcript"
