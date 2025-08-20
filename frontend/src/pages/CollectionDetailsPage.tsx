import { DocumentCard } from "@/components/document-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { UpdateCollectionDialog } from "@/components/update-collection-dialog";
import { UploadDocumentDialog } from "@/components/upload-document-dialog";
import { Collection, Document } from "@/types";
import { ArrowLeft, Edit, FileText, Plus, Search } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

const CollectionDetailsPage: React.FC = () => {
  const { collectionId } = useParams<{ collectionId: string }>();
  const [collection, setCollection] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("docName"); // 'docName' or 'createdAt'
  const [filterBy, setFilterBy] = useState("all"); // 'all', 'hasInsight', 'hasPodcast'
  const navigate = useNavigate();

  const fetchCollectionDetails = useCallback(async () => {
    if (!collectionId) return;
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/collections/${collectionId}`
      );
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data: Collection = await response.json();
      setCollection(data);
    } catch (error) {
      console.error("Error fetching collection details:", error);
      toast.error("Failed to load collection details.");
    }
  }, [collectionId]);

  const fetchDocuments = useCallback(async () => {
    if (!collectionId) return;
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/documents/collections/${collectionId}/documents`
      );
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data: Document[] = await response.json();
      setDocuments(data);
    } catch (error) {
      console.error("Error fetching documents:", error);
      toast.error("Failed to load documents.");
    }
  }, [collectionId]);

  useEffect(() => {
    fetchCollectionDetails();
    fetchDocuments();

    const handleFocus = () => {
      fetchCollectionDetails();
      fetchDocuments();
    };

    window.addEventListener("focus", handleFocus);

    return () => {
      window.removeEventListener("focus", handleFocus);
    };
  }, [fetchCollectionDetails, fetchDocuments]);

  const sortedAndFilteredDocuments = React.useMemo(() => {
    let currentDocuments = [...documents];

    // Apply filterBy
    if (filterBy === "hasInsight") {
      currentDocuments = currentDocuments.filter(
        (doc) => doc.latestInsightId !== null
      );
    } else if (filterBy === "hasPodcast") {
      currentDocuments = currentDocuments.filter(
        (doc) => doc.latestPodcastId !== null
      );
    }

    // Apply sortBy
    currentDocuments.sort((a, b) => {
      if (sortBy === "docName") {
        return a.docName.localeCompare(b.docName);
      } else if (sortBy === "createdAt") {
        return (
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
      }
      return 0;
    });

    // Apply searchTerm filter
    return currentDocuments.filter((doc) =>
      doc.docName.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [documents, searchTerm, sortBy, filterBy]);

  const handleDeleteDocument = async (documentId: string) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/documents/${documentId}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      toast.success("Document deleted successfully!");
      fetchDocuments(); // Refresh the list of documents
      fetchCollectionDetails(); // Refresh collection details to update total_docs
    } catch (error) {
      console.error("Error deleting document:", error);
      toast.error("Failed to delete document.");
    }
  };

  if (!collection) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        Loading collection...
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col px-8 py-4 ">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => navigate("/collections")}
        className="mb-2"
      >
        <ArrowLeft className="h-6 w-6" />
      </Button>
      {/* Collection Header */}
      <div className="mb-6 mt-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-3xl font-bold">
              {collection.name || "Untitled Collection"}
            </h1>
            <UpdateCollectionDialog
              collection={collection}
              onCollectionUpdated={fetchCollectionDetails}
            >
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => e.stopPropagation()}
              >
                <Edit className="h-5 w-5" />
              </Button>
            </UpdateCollectionDialog>
          </div>
          {collection.tags && collection.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {collection.tags.map((tag, index) => (
                <Badge key={index} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>
        {collection.description && (
          <p className="text-muted-foreground mt-2">{collection.description}</p>
        )}
      </div>

      {/* Search, Filter, Sort for Documents */}
      <div className="flex items-center gap-4 mb-6">
        <Card className="p-2 border flex items-center gap-1 text-sm text-muted-foreground">
          <FileText className="h-4 w-4" /> Documents: {collection.total_docs}
        </Card>
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search documents..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">
              Sort By: {sortBy === "docName" ? "Name" : "Date Uploaded"}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setSortBy("docName")}>
              Name (A-Z)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setSortBy("createdAt")}>
              Date Uploaded (Newest)
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">
              Filter By:{" "}
              {filterBy === "all"
                ? "All"
                : filterBy === "hasInsight"
                ? "Has Insight"
                : "Has Podcast"}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setFilterBy("all")}>
              All
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFilterBy("hasInsight")}>
              Has Insight
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFilterBy("hasPodcast")}>
              Has Podcast
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Document Grid */}
      {sortedAndFilteredDocuments.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <UploadDocumentDialog collectionId={collectionId as string} onDocumentUploaded={() => { fetchDocuments(); fetchCollectionDetails(); }}>
            <Card className="flex flex-col items-center justify-center p-6 text-center border-2 border-dashed hover:border-primary transition-colors cursor-pointer h-full">
              <Plus className="h-16 w-16 text-muted-foreground mb-4" />
              <p className="text-lg font-semibold text-muted-foreground">Upload New Document</p>
            </Card>
          </UploadDocumentDialog>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <UploadDocumentDialog collectionId={collectionId as string} onDocumentUploaded={() => { fetchDocuments(); fetchCollectionDetails(); }}>
            <Card className="flex flex-col items-center justify-center p-6 text-center border-2 border-dashed hover:border-primary transition-colors cursor-pointer h-full">
              <Plus className="h-16 w-16 text-muted-foreground mb-4" />
              <p className="text-lg font-semibold text-muted-foreground">Upload New Document</p>
            </Card>
          </UploadDocumentDialog>
          {sortedAndFilteredDocuments.map((document) => (
            <DocumentCard key={document.id} document={document} onDocumentDeleted={handleDeleteDocument} collectionId={collectionId as string} />
          ))}
        </div>
      )}
    </div>
  );
};

export default CollectionDetailsPage;
