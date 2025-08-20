import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Document } from "@/types";
import {
  Download,
  FileText,
  Headphones,
  MoreHorizontal,
  Trash2,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

interface DocumentCardProps {
  document: Document;
  onDocumentDeleted: (documentId: string) => void;
  collectionId: string;
}

export function DocumentCard({
  document,
  onDocumentDeleted,
  collectionId,
}: DocumentCardProps) {
  const navigate = useNavigate();

  const handleDownload = () => {
    // Implement download logic here, assuming document.docUrl is a direct download link
    if (document.docUrl) {
      window.open(document.docUrl, "_blank");
    } else {
      toast.error("Document URL not available for download.");
    }
  };

  return (
    <Card
      className="border border-border/50 bg-card/80 backdrop-blur-sm cursor-pointer"
      onClick={() => navigate(`/collections/${collectionId}/${document.id}`)}
    >
      <CardHeader className="p-4 relative"> {/* Added relative */}
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <FileText className="h-16 w-16 text-primary" />
            <div className="mr-10 mb-10">
              <div className="flex items-center gap-2"> {/* New div for title and badge */}
                <CardTitle className="text-lg font-semibold">
                  {document.docTitle === "Untitled Document" ? document.docName : document.docTitle}
                </CardTitle>
              </div>
              <CardDescription className="text-sm text-muted-foreground">
                {document.docName}
              </CardDescription>
              <div className="text-sm text-muted-foreground">
                {document.docSizeKB !== null ? `${document.docSizeKB} KB` : 'N/A'} - {document.total_pages !== null ? `${document.total_pages} Pages` : 'N/A'}
              </div>
            </div>
          </div>
        </div>
        {/* Absolute positioned elements */}
        <div className="absolute top-2 right-2"> {/* Wrapper for More button */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}> {/* Stop propagation here */}
                <span className="sr-only">Open menu</span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={(e) => { e.stopPropagation(); handleDownload(); }} onClick={(e) => e.stopPropagation()}> {/* Stop propagation here */}
                <Download className="mr-2 h-4 w-4" /> Download
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={(e) => { e.stopPropagation(); onDocumentDeleted(document.id); }} onClick={(e) => e.stopPropagation()}
                className="text-red-600 focus:text-red-600"
              >
                <Trash2 className="mr-2 h-4 w-4" /> Delete
              </DropdownMenuItem>
              {document.latestInsightId && (
                <DropdownMenuItem onSelect={(e) => { e.stopPropagation(); navigate(`/insight/${document.latestInsightId}`); }} onClick={(e) => e.stopPropagation()}> {/* Stop propagation here */}
                  <FileText className="mr-2 h-4 w-4" /> View Insight
                </DropdownMenuItem>
              )}
              {document.latestPodcastId && (
                <DropdownMenuItem onSelect={(e) => { e.stopPropagation(); navigate(`/podcast/${document.latestPodcastId}`); }} onClick={(e) => e.stopPropagation()}> {/* Stop propagation here */}
                  <Headphones className="mr-2 h-4 w-4" /> View Podcast
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        {document.docType === "application/pdf" && (
          <div className="absolute bottom-2 right-4"> {/* Wrapper for PDF Badge */}
            <Badge variant="secondary">PDF</Badge>
          </div>
        )}
      </CardHeader>
      <CardContent>
        {/* Any other content for the card body can go here if needed */}
      </CardContent>
    </Card>
  );
}
