import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { FolderPlus, Plus, Upload, Trash2, Loader2 } from "lucide-react"; // Import Loader2
import { useCallback, useState, useEffect } from "react"; // Added useEffect
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

import { Collection } from "@/types";

interface UploadZoneProps {
  collections?: Collection[];
  onUpload?: (
    files: File[],
    collectionId?: string,
    newCollectionName?: string
  ) => void;
  isHomepageDropzone?: boolean;
  // New prop for external upload handling
  externalUploadHandler?: (
    files: File[],
    collectionId?: string,
    newCollectionName?: string
  ) => Promise<void>;
  // New prop to pre-select a collection (useful for ReaderPage)
  preSelectedCollectionId?: string;
  onUploadSuccess?: () => void; // New prop for success callback
  className?: string; // New prop
}

export function UploadZone({
  collections = [],
  onUpload,
  isHomepageDropzone = false,
  externalUploadHandler,
  preSelectedCollectionId,
  onUploadSuccess, // Destructure new prop
  className, // Destructure new prop
}: UploadZoneProps) {
  const navigate = useNavigate();
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [newCollectionName, setNewCollectionName] = useState("");
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>(
    preSelectedCollectionId || ""
  );
  const [showDialog, setShowDialog] = useState(false);
  const [isUploading, setIsUploading] = useState(false); // New state for loading indicator

  // Update selectedCollectionId if preSelectedCollectionId changes
  useEffect(() => {
    if (preSelectedCollectionId) {
      setSelectedCollectionId(preSelectedCollectionId);
    }
  }, [preSelectedCollectionId]);


  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragIn = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragOut = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files).filter(
      (file) => file.type === "application/pdf"
    );

    if (files.length === 0) {
      toast.error("Please upload only PDF files");
      return;
    }

    setSelectedFiles(files);
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []).filter(
      (file) => file.type === "application/pdf"
    );

    if (files.length === 0) {
      toast.error("Please upload only PDF files");
      return;
    }

    setSelectedFiles(files);
  };

  // Unified upload handler
  const executeUpload = async (
    files: File[],
    collectionId?: string,
    newCollectionName?: string
  ) => {
    setIsUploading(true); // Set loading state
    try {
      if (externalUploadHandler) {
        await externalUploadHandler(files, collectionId, newCollectionName);
      } else {
        // Original internal upload logic (for homepage or default behavior)
        const formData = new FormData();
        files.forEach((file) => {
          formData.append("files", file);
        });

        try {
          const url = collectionId
            ? `http://localhost:8000/api/v1/documents/upload?collection_id=${collectionId}`
            : newCollectionName
            ? `http://localhost:8000/api/v1/documents/upload?new_collection_name=${newCollectionName}`
            : `http://localhost:8000/api/v1/documents/upload`; // Fallback to default if no ID/name

          const response = await fetch(url, {
            method: "POST",
            body: formData,
          });

          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const result = await response.json();
          toast.success(
            `Uploaded ${result.documents.length} document(s)!`
          );
          // Navigate to the new collection's page if a new collection was created
          if (result.collection && result.collection.id) {
            navigate(`/collections/${result.collection.id}`);
          }
        } catch (error) {
          console.error("Error uploading document:", error);
          toast.error("Failed to upload document.");
        }
      }
    } finally {
      setIsUploading(false); // Clear loading state
      setSelectedFiles([]); // Clear selected files after upload attempt
      setNewCollectionName(""); // Clear new collection name
      setShowDialog(false); // Close dialog after upload
      if (onUploadSuccess) {
        onUploadSuccess();
      }
      if (onUpload) { // Call the original onUpload prop if it exists
        onUpload(files, collectionId, newCollectionName);
      }
    }
  };

  const handleUploadToDefaultCollection = async () => {
    if (selectedFiles.length === 0) return;
    await executeUpload(selectedFiles);
  };

  const handleAddToExisting = async () => {
    if (!selectedCollectionId || selectedFiles.length === 0) return;
    await executeUpload(selectedFiles, selectedCollectionId);
  };

  const handleCreateNew = async () => {
    if (!newCollectionName.trim() || selectedFiles.length === 0) return;
    await executeUpload(selectedFiles, undefined, newCollectionName.trim());
  };

  const handleRemoveFile = (indexToRemove: number) => {
    setSelectedFiles((prevFiles) =>
      prevFiles.filter((_, index) => index !== indexToRemove)
    );
  };

  const isActive = selectedFiles.length > 0;

  return (
    <div className={cn("space-y-4", className)}> {/* Apply className to outermost div */}
      <Card
        className={cn(
          "border-2 border-dashed transition-all duration-200 max-w-md mx-auto", // Added max-w-md and mx-auto for centering
          isDragOver
            ? "border-primary bg-primary/5 shadow-lg"
            : "border-border hover:border-primary/50",
          isActive && "ring-2 ring-primary/20"
        )}
        onDragEnter={handleDragIn}
        onDragLeave={handleDragOut}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <Upload
            className={cn(
              "h-12 w-12 mb-4 transition-colors",
              isDragOver ? "text-primary" : "text-muted-foreground"
            )}
          />
          <h3 className="text-lg font-semibold mb-2">
            {isDragOver ? "Drop your PDFs here!" : "Upload PDF Documents"}
          </h3>
          <p className="text-muted-foreground mb-4">
            Drag and drop your PDF files here, or click to browse
          </p>
          <input
            type="file"
            multiple
            accept=".pdf"
            onChange={handleFileInput}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload">
            <Button variant="outline" asChild>
              <span className="cursor-pointer">
                <Plus className="h-4 w-4 mr-2" />
                Browse Files
              </span>
            </Button>
          </label>

          {selectedFiles.length > 0 && (
            <div className="mt-4 p-3 bg-muted rounded-md w-full max-w-sm mx-auto max-h-40 overflow-y-auto">
              <p className="text-sm font-medium mb-2">
                {selectedFiles.length} PDF{selectedFiles.length !== 1 ? "s" : ""} selected:
              </p>
              <ul className="space-y-1">
                {selectedFiles.map((file, index) => (
                  <li key={file.name + index} className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{file.name}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleRemoveFile(index)}
                      className="text-red-500 hover:text-red-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {isActive && (
        <div className="flex gap-3 justify-center">
          {isHomepageDropzone ? (
            <Button onClick={handleUploadToDefaultCollection} disabled={isUploading}> {/* Disable button when uploading */}
              {isUploading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Upload className="h-4 w-4 mr-2" />
              )}
              {isUploading ? "Uploading..." : "Upload to Default Collection"}
            </Button>
          ) : preSelectedCollectionId ? ( // New condition for ReaderPage context
            <Button onClick={() => executeUpload(selectedFiles, preSelectedCollectionId)} disabled={isUploading}> {/* Disable button when uploading */}
              {isUploading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Upload className="h-4 w-4 mr-2" />
              )}
              {isUploading ? "Uploading..." : "Upload to Current Collection"}
            </Button>
          ) : (
            <>
              {collections.length > 0 && (
                <div className="flex items-center gap-2">
                  <Select
                    value={selectedCollectionId}
                    onValueChange={setSelectedCollectionId}
                    disabled={isUploading} // Disable select when uploading
                  >
                    <SelectTrigger className="w-48">
                      <SelectValue placeholder="Select collection" />
                    </SelectTrigger>
                    <SelectContent>
                      {collections.map((collection) => (
                        <SelectItem key={collection.id} value={collection.id}>
                          {collection.name || 'Untitled Collection'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    onClick={handleAddToExisting}
                    disabled={!selectedCollectionId || isUploading} // Disable button when uploading
                  >
                    {isUploading ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Plus className="h-4 w-4 mr-2" />
                    )}
                    {isUploading ? "Uploading..." : "Add to Existing"}
                  </Button>
                </div>
              )}

              <Dialog open={showDialog} onOpenChange={setShowDialog}> {/* Keep dialog open state for internal control */}
                <DialogTrigger asChild>
                  <Button variant="outline" disabled={isUploading}> {/* Disable button when uploading */}
                    {isUploading ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <FolderPlus className="h-4 w-4 mr-2" />
                    )}
                    {isUploading ? "Uploading..." : "Create New Collection"}
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create New Collection</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <Input
                      placeholder="Collection name"
                      value={newCollectionName}
                      onChange={(e) => setNewCollectionName(e.target.value)}
                      onKeyPress={(e) => e.key === "Enter" && handleCreateNew()}
                      disabled={isUploading} // Disable input when uploading
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        onClick={() => setShowDialog(false)}
                        disabled={isUploading} // Disable button when uploading
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={handleCreateNew}
                        disabled={!newCollectionName.trim() || isUploading} // Disable button when uploading
                      >
                        {isUploading ? (
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <Upload className="h-4 w-4 mr-2" />
                        )}
                        {isUploading ? "Uploading..." : "Create & Upload"}
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </>
          )}
        </div>
      )}
    </div>
  );
}