export enum ProcessingStatus {
  Pending = "Pending",
  Success = "Success",
  Failed = "Failed",
}

export interface DocumentOutlineItem {
  level: string;
  section_id: string;
  documentId: string;
  text: string;
  annotation: string | null;
  page: number;
}

export interface Document {
  docTitle: string | null;
  id: string;
  collectionId: string;
  docName: string;
  docSizeKB: number | null;
  total_pages: number | null;
  docType: string | null;
  docUrl: string | null;
  createdAt: string;
  updatedAt: string | null;
  latestInsightId: string | null;
  latestPodcastId: string | null;
  isProcessed: ProcessingStatus;
  isEmbeddingCreated: ProcessingStatus;
  outline: DocumentOutlineItem[];
}

export interface Collection {
  id: string;
  name: string | null;
  description: string | null;
  tags: string[] | null;
  createdAt: string;
  updatedAt: string | null;
  total_docs: number;
  latestInsightId: string | null;
  latestPodcastId: string | null;
  pdfs: Document[]; // This is a frontend-specific aggregation, not directly from CollectionInDB
}

export interface UploadResponseData {
  collection: Collection | null;
  documents: Document[];
}

export enum InsightType {
  KeyInsights = "Key insights",
  DidYouKnow = "Did you know?",
  ContradictionsCounterpoints = "Contradictions / counterpoints",
  InspirationsConnectionsAcrossDocs = "Inspirations or connections across docs",
  GenerationError = "generation_error",
}

export interface InsightItem {
  type: InsightType;
  data: string;
  priority: number;
}

export interface Insight {
  insightId: string;
  sourceType: string;
  sourceId: string;
  insights_data: InsightItem[];
  generatedAt: string;
}

export interface PodcastSegment {
  speaker: string;
  dialogue: string;
  words: number;
  order: number;
}

export interface Podcast {
  sourceType: string;
  sourceId: string;
  podcastId: string;
  status: string; // Consider making this an enum if backend defines one
  audioUrl: string | null;
  durationSeconds: number | null;
  generatedAt: string;
  shortDescription: string | null;
  transcript: PodcastSegment[] | null;
}

export interface PodcastGenerateRequest {
  include_insights?: boolean;
  min_duration_seconds?: number | null;
  max_duration_seconds?: number | null;
}

export interface AnalysisRequest {
  persona?: string | null;
  job_to_be_done?: string | null;
  collection_ids: string[];
}

export interface TextBasedRecommendationRequest {
  selected_text: string;
  collection_ids: string[];
}

export interface RecommendationItem {
  item_id: string;
  recommendation_id: string;
  document_title: string;
  doc_id: string;
  section_title: string;
  pageNumber: number; // Assuming this comes from the backend or is derived
  snippetText: string; // Assuming this comes from the backend or is derived
  // Properties added for frontend rendering
  title: string;
  explanation: string;
  quadPoints: number[][] | null;
}
