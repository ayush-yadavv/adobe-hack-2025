# This file imports all of the SQLAlchemy models.
# By importing them here, we make them available to SQLAlchemy's metadata
# and ensure that all relationships between tables can be correctly resolved
# when the application starts up.

from .collection import CollectionInDB as CollectionSchema
from .document import DocumentInDB as DocumentSchema
from .document_outline_item import DocumentOutlineItem
from .insight import InsightInDB as InsightSchema
from .podcast import PodcastInDB as PodcastSchema
from .recommendation import RecommendationSchema as RecommendationSchema
from .recommendation_item import RecommendationItemSchema as RecommendationItemSchema
