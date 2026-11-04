from enum import Enum


class EntityType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    ASSETS = "Assets"
    GEOGRAPHIC = "GeographicTies"
    DIGITAL = "DigitalTrail"
    EVENT = "Event"
    DOCUMENT = "Document"
    UNKNOWN = "Unknown"


class OrganizationType(str, Enum):
    COMPANY = "Company"
    NGO = "NGO"
    PARTY = "Party"
    ASSOCIATION = "Association"
    INSTITUTION = "Institution"
    UNKNOWN = "Unknown"


class DigitalTrailType(str, Enum):
    SOCIALPROFILE = "SocialProfile"
    NEWS = "News"
    ARTICLES = "Articles"
    UNKNOWN = "Unknown"


class SourceType(str, Enum):
    OFFICIAL_REGISTRY = "Official_Registry"
    COURT_DOCUMENT = "Court_Document"
    GOVERNMENT_DOCUMENT = "Government_Document"
    INVESTIGATIVE_ARTICLE = "Investigative_Article"
    NEWS_ARTICLE = "News_Article"
    SOCIAL_MEDIA_POST = "Social_Media_Post"
    LEAKED_DOCUMENT = "Leaked_Document"
    ARCHIVED_WEBPAGE = "Archived_Webpage"
    UNKNOWN = "Unknown"


class ClaimStatus(str, Enum):
    UNVERIFIED = "Unverified"
    REPORTED = "Reported"
    ALLEGED = "Alleged"
    INFERRED = "Inferred"
    VERIFIED = "Verified"
    DISPUTED = "Disputed"
    RETRACTED = "Retracted"


class ClaimType(str, Enum):
    RELATIONSHIP = "Relationship"
    FACT = "Fact"
    INFERENCE = "Inference"
    ANOMALY = "Anomaly"
    HYPOTHESIS = "Hypothesis"


class Predicate(str, Enum):
    OWNS = "Owns"
    CONTROLS = "Controls"
    SHAREHOLDER_IN = "Shareholder_In"
    DIRECTOR_OF = "Director_Of"
    FOUNDED = "Founded"

    REPRESENTS = "Represents"
    DEFENDANT_IN = "Defendant_In"
    PLAINTIFF_IN = "Plaintiff_In"
    INVESTIGATED_IN = "Investigated_In"

    BIDDER_IN = "Bidder_In"
    WON_CONTRACT = "Won_Contract"
    SUBCONTRACTED_TO = "Subcontracted_To"

    MENTIONS = "Mentions"
    ALLEGES = "Alleges"
    REPORTS_ON = "Reports_On"

    BASED_IN = "Based_In"
    REGISTERED_AT = "Registered_At"

    OWNS_ACCOUNT = "Owns_Account"
    PUBLISHED = "Published"
