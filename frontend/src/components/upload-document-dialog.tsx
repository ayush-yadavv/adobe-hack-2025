import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Dropzone, DropzoneEmptyState } from "@/components/ui/shadcn-io/dropzone";

interface UploadDocumentDialogProps {
  collectionId: string;
  onDocumentUploaded: () => void;
}

export function UploadDocumentDialog({
  collectionId,
  onDocumentUploaded,
}: UploadDocumentDialogProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const handleDrop = (acceptedFiles: File[]) => {
    setFiles(acceptedFiles);
  };

  const handleRemoveFile = (indexToRemove: number) => {
    setFiles((prevFiles) => prevFiles.filter((_, index) => index !== indexToRemove));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (files.length === 0) {
      toast.error("Please select at least one file to upload.");
      return;
    }

    setIsUploading(true);

    const formData = new FormData();
    files.forEach((file) => {
      formData.append("files", file);
    });

    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/documents/collections/${collectionId}/documents/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      toast.success(`${result.length} document(s) uploaded successfully!`);
      setIsOpen(false); // Close the dialog
      setFiles([]); // Clear selected files
      onDocumentUploaded(); // Notify parent to refresh documents
    } catch (error) {
      console.error("Error uploading document:", error);
      toast.error("Failed to upload document.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button
          className="flex flex-col items-center justify-center p-6 h-auto border-2 border-dashed rounded-lg cursor-pointer hover:bg-muted/50 transition-colors"
          onClick={() => setIsOpen(true)}
          variant="outline"
        >
          <Plus className="h-8 w-8 text-muted-foreground mb-2" />
          <p className="text-lg font-semibold text-muted-foreground">Upload Document</p>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Upload New Document</DialogTitle>
          <DialogDescription>
            Select document(s) to upload to this collection.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="col-span-4">
              <Dropzone
                onDrop={handleDrop}
                accept={{ 'application/pdf': ['.pdf'] }}
                maxFiles={null} // Allow multiple files
              >
                <DropzoneEmptyState />
              </Dropzone>
              {files.length > 0 && (
                <div className="mt-2 max-h-40 overflow-y-auto">
                  <p className="text-sm text-muted-foreground">Selected files:</p>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    {files.map((file, index) => (
                      <li key={index} className="flex items-center justify-between">
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
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isUploading}>
              {isUploading ? "Uploading..." : "Upload Document"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
