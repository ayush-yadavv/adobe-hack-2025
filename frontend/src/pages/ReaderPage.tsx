import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"; // Import Dialog components
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { UploadZone } from "@/components/upload-zone"; // Import UploadZone
import { cn } from "@/lib/utils"; // Import cn for conditional class merging
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Search,
  Trash2,
  Upload,
  User,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Collection, Document, RecommendationItem } from "../types";

interface UploadZoneProps {
  collections: Collection[];
  preSelectedCollectionId?: string;
  externalUploadHandler: (
    files: File[],
    collectionId?: string,
    newCollectionName?: string
  ) => Promise<void>;
  onUploadSuccess?: () => void; // New prop for success callback
  className?: string;
}

// Define your Adobe Client ID here
const ADOBE_EMBED_API_KEY = import.meta.env.ADOBE_EMBED_API_KEY;

declare global {
  interface Window {
    AdobeDC: {
      View: new (options: { clientId: string; divId: string }) => {
        previewFile: (filePromise: unknown, viewerOptions: unknown) => void;
        destroy: () => void;
      };
    };
  }
}

export default function ReaderPage() {
  const { collectionId, documentId } = useParams<{
    collectionId: string;
    documentId: string;
  }>();
  const navigate = useNavigate();

  const [collection, setCollection] = useState<Collection | null>(null);
  const [documentsInCollection, setDocumentsInCollection] = useState<
    Document[]
  >([]);
  const [openTabs, setOpenTabs] = useState<
    { id: string; title: string; docUrl: string }[]
  >([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [isAdobeSDKReady, setIsAdobeSDKReady] = useState(false); // New state
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false); // State for upload dialog
  const [isLeftSidebarCollapsed, setIsLeftSidebarCollapsed] = useState(false); // State for left sidebar collapse
  const [showSearchBar, setShowSearchBar] = useState(false); // State for search bar visibility
  const [searchQuery, setSearchQuery] = useState(""); // State for search query
  const [isPersonaRecommendationDialogOpen, setIsPersonaRecommendationDialogOpen] = useState(false);
  const [personaInput, setPersonaInput] = useState("");
  const [jobToBeDoneInput, setJobToBeDoneInput] = useState("");
  const [isGeneratingPersonaRecommendations, setIsGeneratingPersonaRecommendations] = useState(false);
  const [selectedText, setSelectedText] = useState<string | null>(null); // State for selected text
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>(
    []
  ); // State for recommendations
  const [includeInsights, setIncludeInsights] = useState(false);
  const [minDuration, setMinDuration] = useState(120);
  const [maxDuration, setMaxDuration] = useState(240);
  const [isGeneratingPodcast, setIsGeneratingPodcast] = useState(false);
  const [generatedPodcast, setGeneratedPodcast] = useState<any>(null);
  const [rightSidebarActiveTab, setRightSidebarActiveTab] = useState<"recommendations" | "podcast" | "insights">("insights");
  const [showPodcastTabButton, setShowPodcastTabButton] = useState(false);
  const [showRecommendationsTabButton, setShowRecommendationsTabButton] = useState(false);

  const [selectedRecommendationId, setSelectedRecommendationId] = useState<string | null>(null); // New state for selected recommendation
  const [insightsData, setInsightsData] = useState<Insight[]>([]);
  const [isInsightsLoading, setIsInsightsLoading] = useState(false);
  const [isRecommendationsLoading, setIsRecommendationsLoading] = useState(false);

  interface Insight {
    type: string;
    data: string;
    priority: number;
  }

  const adobeDCViewInstancesRef = useRef<
    Map<string, { view: Window["AdobeDC"]["View"]; apis: any; adobeViewer: any }>
  >(new Map()); // Change to Map

  // Function to re-fetch documents for the current collection
  const refreshDocumentsInCollection = useCallback(async (): Promise<
    Document[]
  > => {
    if (!collectionId) return []; // Return empty array if no collectionId
    try {
      const documentsResponse = await fetch(
        `http://localhost:8000/api/v1/documents/collections/${collectionId}/documents`
      );
      if (!documentsResponse.ok) {
        throw new Error(`HTTP error! status: ${documentsResponse.status}`);
      }
      const documentsData: Document[] = await documentsResponse.json();
      setDocumentsInCollection(documentsData);
      return documentsData; // Return the fetched data
    } catch (error) {
      console.error("Error refreshing documents:", error);
      toast.error("Failed to refresh documents.");
      return []; // Return empty array on error
    }
  }, [collectionId]); // Add collectionId to dependencies

  // Effect to load collection metadata
  useEffect(() => {
    if (!collectionId) {
      navigate("/");
      return;
    }

    const fetchCollection = async () => {
      try {
        const collectionResponse = await fetch(
          `http://localhost:8000/api/v1/collections/${collectionId}`
        );
        if (!collectionResponse.ok) {
          throw new Error(`HTTP error! status: ${collectionResponse.status}`);
        }
        const collectionData: Collection = await collectionResponse.json();
        setCollection(collectionData);
      } catch (error) {
        console.error("Error fetching collection metadata:", error);
        toast.error("Error fetching collection metadata.");
        navigate("/");
      }
    };

    fetchCollection();
  }, [collectionId, navigate]);

  // Effect to load documents in the collection
  useEffect(() => {
    if (!collectionId || !documentId) {
      return;
    }

    const fetchAndSetDocuments = async () => {
      const fetchedDocuments = await refreshDocumentsInCollection(); // Get returned data

      // Find the initial document to open from the fetched documents
      const initialDocument = fetchedDocuments.find(
        // Use fetchedDocuments
        (doc) => doc.id === documentId
      );

      if (initialDocument) {
        setOpenTabs([
          {
            id: initialDocument.id,
            title:
              initialDocument.docTitle === "Untitled Document"
                ? initialDocument.docName
                : initialDocument.docTitle, // Use docName for "Untitled Document"
            docUrl: initialDocument.docUrl,
          },
        ]);
        setActiveTab(initialDocument.id);
      } else {
        toast.error("Document not found in collection.");
        navigate(`/collections/${collectionId}`);
      }
    };

    fetchAndSetDocuments();
  }, [collectionId, documentId, navigate, refreshDocumentsInCollection]);

  // Effect to load Adobe PDF Embed API script and set SDK ready state
  useEffect(() => {
    const script = window.document.createElement("script");
    script.src = "https://documentcloud.adobe.com/view-sdk/main.js";
    script.async = true;
    script.onload = () => {
      let attempts = 0;
      const maxAttempts = 30; // Try for up to 3 seconds (30 * 100ms)
      const interval = setInterval(() => {
        if (window.AdobeDC) {
          clearInterval(interval);
          console.log("window.AdobeDC is now available.");
          setIsAdobeSDKReady(true); // Set SDK ready state
        } else {
          attempts++;
          if (attempts >= maxAttempts) {
            clearInterval(interval);
            console.error(
              "window.AdobeDC not available after multiple attempts. Aborting initialization."
            );
          }
        }
      }, 100);
    };
    window.document.body.appendChild(script);

    return () => {
      if (window.document.body.contains(script)) {
        window.document.body.removeChild(script);
      }
    };
  }, []); // Empty dependency array: runs once on mount

  // Effect to initialize AdobeDC View and preview PDF when SDK is ready and activeTab changes
  useEffect(() => {
    if (isAdobeSDKReady && activeTab) {
      const currentDoc = openTabs.find((tab) => tab.id === activeTab);
      if (currentDoc && currentDoc.docUrl) {
        const viewerDivId = `adobe-dc-view-${currentDoc.id}`; // Unique divId
        const adobeDiv = document.getElementById(viewerDivId);

        if (adobeDiv) {
          const viewerData = adobeDCViewInstancesRef.current.get(currentDoc.id);
          let adobeDCViewInstance: Window["AdobeDC"]["View"];

          if (!viewerData || !viewerData.view) {
            // Initialize viewer for this tab if it's not already initialized
            adobeDCViewInstance = new window.AdobeDC.View({
              clientId: ADOBE_EMBED_API_KEY,
              divId: viewerDivId, // Use unique divId
            });
            // Store the view instance temporarily to get APIs
            adobeDCViewInstancesRef.current.set(currentDoc.id, {
              view: adobeDCViewInstance,
              apis: null,
            });
            console.log(`AdobeDC View initialized for ${currentDoc.id}.`);
          } else {
            adobeDCViewInstance = viewerData.view;
          }

          console.log("Attempting to preview PDF with URL:", currentDoc.docUrl);
          const previewOptions = {
            embedMode: "SIZED_CONTAINER",
            defaultViewMode: "FIT_WIDTH",
            enableSearchAPIs: true, // Enable Search APIs
            enableAnnotationAPIs: true, // Enable Annotation APIs
          };
          console.log("Adobe preview options:", previewOptions);
          const previewFilePromise = adobeDCViewInstance.previewFile(
            {
              content: {
                location: {
                  url: currentDoc.docUrl,
                },
              },
              metaData: {
                fileName: currentDoc.title,
                id: currentDoc.id, // Add document ID for annotations
              },
            },
            previewOptions
          );

          previewFilePromise
            .then((adobeViewer) => {
              console.log(
                "previewFilePromise resolved. adobeViewer:",
                adobeViewer
              );
              // Store adobeViewer directly
              adobeDCViewInstancesRef.current.set(currentDoc.id, {
                view: adobeDCViewInstance, // Keep the view instance
                apis: null, // Will be updated below
                adobeViewer: adobeViewer, // Store the adobeViewer object
              });

              adobeViewer
                .getAPIs()
                .then((apis: any) => {
                  console.log("getAPIs resolved. apis:", apis);
                  // Update the stored entry with the apis object
                  const currentViewerData = adobeDCViewInstancesRef.current.get(
                    currentDoc.id
                  );
                  if (currentViewerData) {
                    adobeDCViewInstancesRef.current.set(currentDoc.id, {
                      ...currentViewerData,
                      apis,
                    });
                  }

                  // Register event listener for text selection
                  adobeDCViewInstance.registerCallback(
                    window.AdobeDC.View.Enum.CallbackType.EVENT_LISTENER,
                    (event: any) => {
                      if (event.type === "PREVIEW_SELECTION_END") {
                        console.log(
                          "PREVIEW_SELECTION_END event triggered.",
                          event
                        );
                        apis
                          .getSelectedContent()
                          .then((result: any) => {
                            console.log("Selected text:", result);
                            setSelectedText(result.data);
                            setShowRecommendationsTabButton(true);
                            setRightSidebarActiveTab("recommendations");
                          })
                          .catch((error: any) =>
                            console.error(
                              "Error getting selected content:",
                              error
                            )
                          );
                      }
                    },
                    { enableFilePreviewEvents: true }
                  );
                })
                .catch((error: any) =>
                  console.error("Error getting APIs:", error)
                );
            })
            .catch((error: any) =>
              console.error("Error previewing file:", error)
            );
        } else {
          console.error(
            `Viewer div ${viewerDivId} not found for activeTab:`,
            activeTab
          );
        }
      } else {
        console.warn(
          "No current document or docUrl found for activeTab:",
          activeTab,
          currentDoc
        );
      }
    } else {
      console.warn(
        "activeTab is null or Adobe SDK not ready. Waiting for SDK.",
        activeTab,
        isAdobeSDKReady
      );
    }
  }, [activeTab, openTabs, isAdobeSDKReady]); // Depends on activeTab and SDK ready state

  const openDocumentInTab = useCallback(
    (doc: Document) => {
      const existingTab = openTabs.find((tab) => tab.id === doc.id);
      if (!existingTab) {
        setOpenTabs((prev) => [
          {
            id: doc.id,
            title:
              doc.docTitle === "Untitled Document" ? doc.docName : doc.docTitle, // Use docName for "Untitled Document"
            docUrl: doc.docUrl,
          },
          ...prev,
        ]);
      }
      setActiveTab(doc.id);
    },
    [openTabs, setActiveTab]
  );

  const removeDocumentFromCollection = async (docId: string) => {
    // This would typically involve an API call to delete the document from the collection
    // For now, we'll just update the local state
    setDocumentsInCollection((prev) => prev.filter((doc) => doc.id !== docId));
    closeTab(docId); // Also close the tab if it's open
    toast.success("Document removed from collection (local update only).");
  };

  const closeTab = (id: string) => {
    setOpenTabs((tabs) => {
      const updatedTabs = tabs.filter((tab) => tab.id !== id);
      // Destroy the AdobeDC.View instance for the closed tab
      const viewerData = adobeDCViewInstancesRef.current.get(id);
      if (
        viewerData &&
        viewerData.view &&
        typeof viewerData.view.destroy === "function"
      ) {
        // Check if destroy method exists on the view instance
        viewerData.view.destroy(); // Destroy the viewer instance
        console.log(`AdobeDC View destroyed for ${id}.`);
      }
      adobeDCViewInstancesRef.current.delete(id); // Remove from map

      if (activeTab === id && updatedTabs.length > 0) {
        setActiveTab(updatedTabs[0].id);
      } else if (activeTab === id && updatedTabs.length === 0) {
        setActiveTab(null);
      }
      return updatedTabs;
    });
  };

  const handleRecommendationClick = useCallback(
    (recommendation: RecommendationItem) => {
      const { doc_id, pageNumber, snippetText, quadPoints } = recommendation;

      // Set the selected recommendation ID
      setSelectedRecommendationId(recommendation.recommendation_id);

      const docToOpen = documentsInCollection.find((doc) => doc.id === doc_id);

      if (docToOpen) {
        openDocumentInTab(docToOpen);

        // Retrieve the stored apis directly
        const viewerData = adobeDCViewInstancesRef.current.get(doc_id);
        if (viewerData && viewerData.adobeViewer) { // Check for adobeViewer
          const adobeViewerInstance = viewerData.adobeViewer; // Get the stored adobeViewer
          viewerData.apis
            .gotoLocation(pageNumber) // gotoLocation is on apis
            .then(() => {
              console.log(`Navigated to page ${pageNumber}`);

              if (quadPoints && quadPoints.length > 0) {
                const annotations = quadPoints.map((qp, index) => ({
                  id: `highlight-${doc_id}-${pageNumber}-${index}`,
                  type: "highlight",
                  pageIndex: pageNumber - 1, // Adobe SDK is 0-indexed
                  quadPoints: qp,
                  color: [255, 255, 0], // Yellow highlight
                  target: {
                    source: doc_id, // Assuming doc_id is used as the document ID in metaData
                  },
                }));

                console.log("Attempting to add annotations:", annotations);

                adobeViewerInstance.getAnnotationManager() // <--- Changed to adobeViewerInstance
                  .then((annotationManager: any) => {
                    annotationManager.addAnnotations(annotations)
                      .then(() => console.log("Highlights added successfully!"))
                      .catch((error: any) => {
                        console.error("Error adding highlights:", error);
                        if (error.message && error.message.includes('APIs not allowed on this PDF.')) {
                          toast.info(`Highlighting not available for this document. Snippet: "${snippetText}"`);
                          toast.error("Highlighting is not allowed on this PDF due to document restrictions.");
                        } else {
                          toast.error("Failed to add highlights.");
                        }
                      });
                  })
                  .catch((error: any) =>
                    console.error("Error getting annotation manager:", error)
                  );
              }
            })
            .catch((error: any) =>
              console.error("Error navigating to page:", error)
            );
        } else {
          console.error(
            `AdobeDC Viewer instance not found for document ${doc_id}. Document might not be loaded yet.`
          );
          toast.error("Viewer not ready for this document. Please try again.");
        }
      } else {
        toast.error("Recommended document not found in this collection.");
      }
    },
    [documentsInCollection, openDocumentInTab, adobeDCViewInstancesRef]
  );

  const handleGeneratePodcast = useCallback(async () => {
    if (!selectedRecommendationId) {
      toast.error("No recommendation selected to generate podcast from.");
      return;
    }

    setIsGeneratingPodcast(true);
    setGeneratedPodcast(null); // Clear previous podcast data

    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/podcasts/generate/from-recommendation/${selectedRecommendationId}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            include_insights: includeInsights,
            min_duration_seconds: minDuration,
            max_duration_seconds: maxDuration,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        console.error("Error generating podcast:", errorData);
        throw new Error(
          `Failed to generate podcast: ${errorData.detail || response.statusText}`
        );
      }

      const podcastData = await response.json();
      setGeneratedPodcast(podcastData);
      toast.success("Podcast generated successfully!");
    } catch (error: any) {
      console.error("Error generating podcast:", error);
      toast.error(error.message || "An unknown error occurred during podcast generation.");
    } finally {
      setIsGeneratingPodcast(false);
    }
  }, [selectedRecommendationId, includeInsights, minDuration, maxDuration]);

  const handleGetPersonaRecommendations = useCallback(async () => {
    if (!personaInput || !jobToBeDoneInput || !collectionId) {
      toast.error("Please enter both persona and job-to-be-done.");
      return;
    }

    setIsGeneratingPersonaRecommendations(true); // Set loading state

    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/recommendations/persona-based`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            persona: personaInput,
            job_to_be_done: jobToBeDoneInput,
            collection_ids: [collectionId],
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        console.error("Backend error response:", errorData);
        throw new Error(
          `HTTP error! status: ${response.status}, details: ${JSON.stringify(
            errorData
          )}`
        );
      }

      const result = await response.json();
      console.log("Backend response for persona recommendations:", result);
      const mappedRecommendations = (result.items || []).map((item: any) => ({
        ...item,
        title: item.section_title,
        explanation: `${item.document_title} (Page: ${item.page_number})`,
        pageNumber: item.page_number,
        snippetText: item.snippet_text,
        quadPoints: item.quad_points,
      }));
      setRecommendations(mappedRecommendations);
      if (result.recommendation_id) {
        setSelectedRecommendationId(result.recommendation_id);
        console.log("selectedRecommendationId set to:", result.recommendation_id);
      } else {
        setSelectedRecommendationId(null);
        console.log("selectedRecommendationId set to null (no recommendation_id in backend response).");
      }
      toast.success("Persona-based recommendations generated!");
      setIsPersonaRecommendationDialogOpen(false); // Close the dialog
      setPersonaInput(""); // Clear input fields
      setJobToBeDoneInput(""); // Clear input fields
    } catch (error) {
      console.error("Error fetching persona-based recommendations:", error);
      toast.error("Failed to fetch persona-based recommendations.");
      setRecommendations([]);
    } finally {
      setIsGeneratingPersonaRecommendations(false); // Reset loading state
    }
  }, [personaInput, jobToBeDoneInput, collectionId, setRecommendations, setSelectedRecommendationId, setShowRecommendationsTabButton, setRightSidebarActiveTab]);

  // Handle upload from UploadZone
  const handleReaderPageUpload = useCallback(
    async (files: File[], collectionIdFromUploadZone?: string) => {
      console.log(
        "handleReaderPageUpload called with collectionIdFromUploadZone:",
        collectionIdFromUploadZone
      );
      if (!collectionIdFromUploadZone) {
        // Ensure collectionId is present for ReaderPage context
        toast.error("Collection ID is missing for upload.");
        return;
      }

      const formData = new FormData();
      files.forEach((file) => {
        formData.append("files", file);
      });

      try {
        const response = await fetch(
          `http://localhost:8000/api/v1/documents/collections/${collectionIdFromUploadZone}/documents/upload`,
          {
            method: "POST",
            body: formData,
          }
        );

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result: Document[] = await response.json();
        toast.success(
          `Uploaded ${result.length} document(s) to ${
            collection?.name || "collection"
          }!`
        );
        await refreshDocumentsInCollection(); // Refresh documents in sidebar
        // Optionally open the first uploaded document in a new tab
        if (result.length > 0) {
          openDocumentInTab(result[0]);
        }
      } catch (error) {
        console.error("Error uploading document:", error);
        toast.error("Failed to upload document.");
      }
    },
    [collection?.name, openDocumentInTab, refreshDocumentsInCollection]
  );

  // Function to fetch text-based recommendations
  const fetchRecommendations = useCallback(async () => {
    if (!selectedText || !collectionId) {
      setRecommendations([]);
      return;
    }

    setIsRecommendationsLoading(true); // Set loading to true

    try {
      console.log("Sending recommendation request with:", {
        selected_text: selectedText,
        collection_ids: [collectionId],
      });
      const response = await fetch(
        `http://localhost:8000/api/v1/recommendations/text-based`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            selected_text: selectedText,
            collection_ids: [collectionId], // Assuming recommendations are for the current collection
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        console.error("Backend error response:", errorData);
        throw new Error(
          `HTTP error! status: ${response.status}, details: ${JSON.stringify(
            errorData
          )}`
        );
      }

      const result = await response.json();
      // Map the items to include 'title' and 'explanation' for rendering
      const mappedRecommendations = (result.items || []).map((item: any) => ({
        ...item,
        title: item.section_title,
        explanation: `${item.document_title} (Page: ${item.page_number})`, // Map page_number from backend to pageNumber
        pageNumber: item.page_number, // Map page_number from backend to pageNumber
        snippetText: item.snippet_text, // Map snippet_text from backend to snippetText
        quadPoints: item.quad_points, // Map quad_points from backend to quadPoints
        snippet_explanation: item.snippet_explanation, // Map snippet_explanation
      }));
      setRecommendations(mappedRecommendations);
      if (result.recommendation_id) {
        setSelectedRecommendationId(result.recommendation_id);
      } else {
        setSelectedRecommendationId(null);
      }
      if (mappedRecommendations.length > 0) {
        setShowRecommendationsTabButton(true);
        setRightSidebarActiveTab("recommendations"); // Switch to recommendations tab
      } else {
        setShowRecommendationsTabButton(false);
      }
      console.log("Recommendations:", result);
    } catch (error) {
      console.error("Error fetching recommendations:", error);
      toast.error("Failed to fetch recommendations.");
      setRecommendations([]);
    } finally {
      setIsRecommendationsLoading(false); // Set loading to false
    }
  }, [selectedText, collectionId]);

  // Effect to fetch recommendations when selectedText changes
  useEffect(() => {
    fetchRecommendations();
  }, [selectedText, fetchRecommendations]);

  // Effect to fetch insights when collectionId changes
  useEffect(() => {
    if (!collectionId) return;

    const fetchInsights = async () => {
      setIsInsightsLoading(true);
      try {
        const response = await fetch(`http://localhost:8000/api/v1/insights/generate?col_id=${collectionId}`);
        console.log("Insights API response status:", response.status);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
        console.log("Insights API response data:", result);
        setInsightsData(result.insights_data || []);
      } catch (error) {
        console.error("Error fetching insights:", error);
        toast.error("Failed to fetch insights.");
        setInsightsData([]);
      } finally {
        setIsInsightsLoading(false);
      }
    };

    fetchInsights();
  }, [collectionId]);

  if (!collection) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
        Loading collection and documents...
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background text-foreground relative">
      {console.log("Current rightSidebarActiveTab:", rightSidebarActiveTab)}
      {" "}
      {/* Added relative to main div */}
      {/* Left Sidebar */}
      <div
        className={cn(
          "flex-shrink-0 border-r border-border flex flex-col transition-all duration-300",
          isLeftSidebarCollapsed ? "w-[32px]" : "w-80"
        )}
      >
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between relative">
          {!isLeftSidebarCollapsed && (
            <div className="flex flex-col mr-auto">
              {" "}
              {/* Group back button and text */}
              <Button
                variant="ghost"
                onClick={() => navigate(-1)}
                className="mb-2"
              >
                <ArrowLeft className="h-4 w-4 mr-2" /> Back
              </Button>
              <h2 className="text-lg font-semibold">
                {collection.name || "Untitled Collection"}
              </h2>
              <p className="text-sm text-muted-foreground">
                {documentsInCollection.length} Documents
              </p>
            </div>
          )}
          <div
            className={cn(
              "flex items-center space-x-2",
              isLeftSidebarCollapsed
                ? "flex-col space-x-0 space-y-2 w-full"
                : "absolute bottom-2 right-2"
            )}
          >
            {" "}
            {/* Icons for filter, sort, search, upload */}
            <Dialog
              open={isPersonaRecommendationDialogOpen}
              onOpenChange={setIsPersonaRecommendationDialogOpen}
            >
              <DialogTrigger asChild>
                <Button variant="ghost" size="icon">
                  <User className="h-5 w-5" />
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Get Persona-Based Recommendations</DialogTitle>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid grid-cols-4 items-center gap-4">
                    <label htmlFor="persona" className="text-right">
                      Persona
                    </label>
                    <Input
                      id="persona"
                      value={personaInput}
                      onChange={(e) => setPersonaInput(e.target.value)}
                      className="col-span-3"
                      disabled={isGeneratingPersonaRecommendations}
                    />
                  </div>
                  <div className="grid grid-cols-4 items-center gap-4">
                    <label htmlFor="job-to-be-done" className="text-right">
                      Job-to-be-done
                    </label>
                    <Input
                      id="job-to-be-done"
                      value={jobToBeDoneInput}
                      onChange={(e) => setJobToBeDoneInput(e.target.value)}
                      className="col-span-3"
                      disabled={isGeneratingPersonaRecommendations}
                    />
                  </div>
                </div>
                <Button
                  onClick={handleGetPersonaRecommendations}
                  disabled={isGeneratingPersonaRecommendations}
                >
                  {isGeneratingPersonaRecommendations ? "Getting Recommendations..." : "Get Recommendations"}
                </Button>
              </DialogContent>
            </Dialog>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => {
                setShowSearchBar(!showSearchBar);
                setIsLeftSidebarCollapsed(false);
              }}
            >
              <Search className="h-5 w-5" />
            </Button>
          </div>
        </div>{" "}
        {/* Closing tag for the header div */}
        {!isLeftSidebarCollapsed && (
          <>
            {showSearchBar && (
              <div className="p-2 border-b border-border">
                <Input
                  placeholder="Search documents..."
                  className="w-full"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            )}

            {/* Document List */}
            <ScrollArea className="flex-1 px-2 mt-4">
              {documentsInCollection
                .filter((doc) =>
                  doc.docName.toLowerCase().includes(searchQuery.toLowerCase())
                )
                .map((doc) => {
                  console.log("Document in sidebar:", {
                    id: doc.id,
                    docName: doc.docName,
                    docTitle: doc.docTitle,
                  });
                  return (
                    <Card
                      key={doc.id}
                      className="mb-2 cursor-pointer"
                      onClick={() => openDocumentInTab(doc)}
                    >
                      <CardContent className="flex justify-between items-center py-3 px-4">
                        <div>
                          <p className="text-sm font-medium">
                            {doc.docTitle === "Untitled Document"
                              ? doc.docName
                              : doc.docTitle}
                          </p>
                        </div>
                        {openTabs.some(tab => tab.id === doc.id) ? (
                          <Badge variant="secondary" className="ml-2">
                            Opened
                          </Badge>
                        ) : null}
                      </CardContent>
                    </Card>
                  );
                })}
            </ScrollArea>

            {/* Upload Button */}
            <div className="p-4 border-t border-border">
              <Dialog
                open={isUploadDialogOpen}
                onOpenChange={setIsUploadDialogOpen}
              >
                <DialogTrigger asChild>
                  <Button variant="outline" className="w-full">
                    Upload Document
                  </Button>
                </DialogTrigger>
                <DialogContent className="overflow-y-auto">
                  {" "}
                  {/* Removed sm:max-w-lg */}
                  <DialogHeader>
                    <DialogTitle>Upload Documents to Collection</DialogTitle>
                  </DialogHeader>
                  <UploadZone
                    collections={[collection]} // Pass current collection
                    preSelectedCollectionId={collection.id} // Pre-select current collection
                    externalUploadHandler={handleReaderPageUpload} // Pass the new handler
                    onUploadSuccess={() => setIsUploadDialogOpen(false)} // Close dialog on success
                    className="w-full" // Add w-full to constrain UploadZone
                  />
                </DialogContent>
              </Dialog>
            </div>
          </>
        )}
      </div>
      
      {/* Main Viewer */}
      <div className="flex-1 flex flex-col bg-muted/40 min-w-0 relative">
        {/* Document Tabs */}
        <div className="flex space-x-2 p-2 border-b border-border overflow-x-auto w-full tab-scrollbar">
          {openTabs.map((tab) => (
            <div
              key={tab.id}
              className={cn(
                "flex items-center px-3 py-1 rounded-md text-sm cursor-pointer flex-shrink-0",
                activeTab === tab.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              )}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="min-w-0 max-w-[150px] whitespace-nowrap overflow-hidden text-ellipsis">
                {tab.title}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeTab(tab.id);
                }}
                className="ml-2 text-muted-foreground hover:text-destructive"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        {/* Toggle Button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsLeftSidebarCollapsed(!isLeftSidebarCollapsed)}
          className={cn(
            "absolute z-10 bg-background rounded-full shadow-md",
            "left-0", // Always left-0 relative to Main Viewer
            "top-[50px]" // Approximate height of tab bar + some margin
          )}
        >
          {isLeftSidebarCollapsed ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </Button>

        {/* Viewer Placeholder */}
        <div className="flex-1 flex items-center justify-center text-muted-foreground relative overflow-hidden">
          {openTabs.map((tab) => (
            <div
              key={tab.id}
              id={`adobe-dc-view-${tab.id}`}
              className="w-full h-full absolute top-0 left-0"
              style={{ display: activeTab === tab.id ? "block" : "none" }}
            ></div>
          ))}
          {!activeTab && "Select a document to view"}
        </div>
      </div>
      {/* Right Sidebar */}
      <div className="w-80 flex-shrink-0 border-l border-border flex flex-col">
        <div className="p-4 border-b border-border flex overflow-x-auto whitespace-nowrap gap-2 tab-scrollbar">
          <Button
            variant={rightSidebarActiveTab === "insights" ? "secondary" : "ghost"}
            onClick={() => setRightSidebarActiveTab("insights")}
            className="flex-shrink-0"
          >
            Insights
          </Button>
          {showRecommendationsTabButton && (
            <Button
              variant={rightSidebarActiveTab === "recommendations" ? "secondary" : "ghost"}
              onClick={() => setRightSidebarActiveTab("recommendations")}
              className="flex-shrink-0"
            >
              Recommendations
            </Button>
          )}
          {showPodcastTabButton && (
            <Button
              variant={rightSidebarActiveTab === "podcast" ? "secondary" : "ghost"}
              onClick={() => setRightSidebarActiveTab("podcast")}
              className="flex-shrink-0"
            >
              Podcast
            </Button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto">
          {(() => {
            switch (rightSidebarActiveTab) {
              case "recommendations":
                return (
                  <div className="flex-1 overflow-y-auto">
                    {recommendations.length > 0 && (
                      <div className="p-4 border-b border-border"> {/* Changed border-t to border-b */}
                        {console.log("selectedRecommendationId before Generate Podcast button:", selectedRecommendationId)}
                        <Button
                          className="w-full"
                          size="lg"
                          onClick={() => {
                            setRightSidebarActiveTab("podcast");
                            setShowPodcastTabButton(true);
                          }}
                          disabled={!selectedRecommendationId} // Disable if no recommendation is selected
                        >
                          Generate Podcast
                        </Button>
                      </div>
                    )}
                    <ScrollArea className="flex-1 p-4">
                      {isRecommendationsLoading ? (
                        <p className="text-sm text-muted-foreground">Loading recommendations...</p>
                      ) : recommendations.length > 0 ? (
                        <Accordion type="single" collapsible className="w-full">
                          {recommendations.map((rec, index) => (
                            <AccordionItem value={rec.item_id} key={index} className="mb-2 border rounded-md">
                              <AccordionTrigger
                                className="py-3 px-4 text-left hover:no-underline"
                              >
                                <div
                                  onClick={(e) => {
                                    e.stopPropagation(); // Prevent Accordion from toggling
                                    handleRecommendationClick(rec);
                                  }}
                                  className="flex flex-col flex-grow cursor-pointer"
                                >
                                  <p className="text-sm font-medium">{rec.title}</p>
                                  <p className="text-xs text-muted-foreground">
                                    {rec.explanation}
                                  </p>
                                </div>
                              </AccordionTrigger>
                              <AccordionContent className="px-4 pb-3 text-sm text-muted-foreground">
                                <p className="font-semibold mb-1">Explanation:</p>
                                <p className="mb-2">{rec.snippet_explanation}</p>
                                <p className="font-semibold mb-1">Snippet:</p>
                                <p>{rec.snippetText}</p>
                              </AccordionContent>
                            </AccordionItem>
                          ))}
                        </Accordion>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No recommendations yet. Select text in a document to get
                          recommendations.
                        </p>
                      )}
                    </ScrollArea>
                  </div>
                );
              case "podcast":
                return (
                  <div className="flex-1 p-4 flex flex-col space-y-4">
                    <h3 className="text-lg font-semibold">Generate Podcast</h3>

                    {selectedRecommendationId ? (
                      <>
                        <div className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            id="includeInsights"
                            checked={includeInsights}
                            onChange={(e) => setIncludeInsights(e.target.checked)}
                            className="h-4 w-4"
                          />
                          <label htmlFor="includeInsights" className="text-sm font-medium">
                            Include Insights
                          </label>
                        </div>

                        <div>
                          <label htmlFor="minDuration" className="text-sm font-medium block mb-1">
                            Min Duration (seconds)
                          </label>
                          <Input
                            id="minDuration"
                            type="number"
                            value={minDuration}
                            onChange={(e) => setMinDuration(Number(e.target.value))}
                            min="30"
                            max="600"
                          />
                        </div>

                        <div>
                          <label htmlFor="maxDuration" className="text-sm font-medium block mb-1">
                            Max Duration (seconds)
                          </label>
                          <Input
                            id="maxDuration"
                            type="number"
                            value={maxDuration}
                            onChange={(e) => setMaxDuration(Number(e.target.value))}
                            min="30"
                            max="600"
                          />
                        </div>

                        <Button
                          onClick={handleGeneratePodcast}
                          disabled={isGeneratingPodcast}
                          className="w-full"
                        >
                          {isGeneratingPodcast ? "Generating..." : "Generate Podcast"}
                        </Button>

                        {generatedPodcast && (
                          <Card className="mt-4">
                            <CardContent className="p-4">
                              <h4 className="text-md font-semibold mb-2">Generated Podcast</h4>
                              <p className="text-sm mb-2">{generatedPodcast.shortDescription}</p>
                              {generatedPodcast.audioUrl && (
                                <audio controls src={generatedPodcast.audioUrl} className="w-full mb-2">
                                  Your browser does not support the audio element.
                                </audio>
                              )}
                              {generatedPodcast.transcript && generatedPodcast.transcript.length > 0 && (
                                <div>
                                  <h5 className="text-sm font-medium mb-1">Transcript:</h5>
                                  <ScrollArea className="h-32 border rounded-md p-2 text-xs">
                                    {generatedPodcast.transcript.map((line: any, idx: number) => (
                                      <p key={idx}><strong>{line.speaker}:</strong> {line.dialogue}</p>
                                    ))}
                                  </ScrollArea>
                                </div>
                              )}
                            </CardContent>
                          </Card>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Select a recommendation to generate a podcast.
                      </p>
                    )}
                  </div>
                );
              case "insights":
                return (
                  <ScrollArea className="flex-1 p-4">
                    {isInsightsLoading ? (
                      <p className="text-sm text-muted-foreground">Loading insights...</p>
                    ) : insightsData.length > 0 ? (
                      insightsData.map((insight, index) => (
                        <Card key={index} className="mb-2">
                          <CardContent className="py-3 px-4 flex items-start space-x-2">
                            {/* Placeholder Icon - Replace with actual icon based on insight type if needed */}
                            <span className="text-primary mt-1">
                              💡
                            </span>
                            <div>
                              <p className="text-sm font-bold">{insight.type}</p>
                              <p className="text-sm text-muted-foreground">{insight.data}</p>
                            </div>
                          </CardContent>
                        </Card>
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No insights available for this collection.
                      </p>
                    )}
                  </ScrollArea>
                );
              default:
                return null;
            }
          })()}
        </div>
      </div>
    </div>
  );
}
