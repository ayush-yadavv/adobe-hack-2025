import { BackgroundLines } from "@/components/ui/background-lines";
import { CollectionCard } from "@/components/collection-card";
import { CreateCollectionDialog } from "@/components/create-collection-dialog";
import { ThemeToggle } from "@/components/theme-toggle";
import TypewriterEffectSmoothDemo from "@/components/typewriter-effect-demo";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { Plus, Search, UploadCloud } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Collection, Document, UploadResponseData } from "../types";
import { UploadZone } from "@/components/upload-zone"; // Keep UploadZone
import { useNavigate } from "react-router-dom"; // Import useNavigate



const HomePage: React.FC = () => { // Removed onSelectCollection from props
  const navigate = useNavigate(); // Initialize useNavigate
  const [isUploading, setIsUploading] = useState(false);

  // LibraryPage states
  const [collections, setCollections] = useState<Collection[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [showWelcomeBack, setShowWelcomeBack] = useState(false);

  // From previous HomePage.tsx
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const response = await fetch("http://localhost:8000/");
        if (response.ok) {
          console.log("Backend is reachable:", await response.json());
        } else {
          console.error(
            "Backend root not reachable:",
            response.status,
            response.statusText
          );
        }
      } catch (error) {
        console.error("Error checking backend:", error);
      }
    };
    checkBackend();
  }, []);

  // From LibraryPage.tsx - Effect to handle initial load or new uploads
  useEffect(() => {
    // Load data from localStorage on mount
    const savedData = localStorage.getItem("pdf-viewer-data");
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        if (parsed.collections && parsed.collections.length > 0) {
          setShowWelcomeBack(true);
          // Don't auto-load yet, wait for user choice or handle via continue session
        }
      } catch (error) {
        console.error("Error loading saved data:", error);
      }
    }
  }, []);

  // From LibraryPage.tsx - Save collections to localStorage whenever they change
  useEffect(() => {
    if (collections.length > 0) {
      saveToLocalStorage(collections);
    }
  }, [collections]);

  // From LibraryPage.tsx
  const saveToLocalStorage = (collectionsData: Collection[]) => {
    localStorage.setItem(
      "pdf-viewer-data",
      JSON.stringify({
        collections: collectionsData,
        lastUpdated: new Date().toISOString(),
      })
    );
  };

  // From LibraryPage.tsx
  const handleContinueSession = () => {
    const savedData = localStorage.getItem("pdf-viewer-data");
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        if (parsed.collections) {
          const restoredCollections = parsed.collections.map((col: unknown) => {
            const collection = col as Collection;
            return {
              ...collection,
              pdfs: collection.pdfs.map((doc: unknown) => {
                const document = doc as Document;
                return {
                  ...document,
                  createdAt: document.createdAt,
                };
              }),
            };
          });
          setCollections(restoredCollections);
          toast.success("Session restored successfully!");
        }
      } catch (error) {
        console.error("Error restoring session:", error);
        toast.error("Error restoring session");
      }
    }
    setShowWelcomeBack(false);
  };

  // From LibraryPage.tsx
  const handleClearSession = () => {
    const savedData = localStorage.getItem("pdf-viewer-data");
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        localStorage.setItem(
          "pdf-viewer-data",
          JSON.stringify({
            collections: parsed.collections || [],
            lastUpdated: new Date().toISOString(),
          })
        );
      } catch (error) {
        console.error("Error clearing session:", error);
      }
    }
    setShowWelcomeBack(false);
    toast.success("Session preferences cleared (collections preserved)");
  };

  // From LibraryPage.tsx
  const handleDeleteCollection = (collectionId: string) => {
    const updatedCollections = collections.filter((c) => c.id !== collectionId);
    setCollections(updatedCollections);
    saveToLocalStorage(updatedCollections);
    toast.success("Collection deleted");
  };

  // From LibraryPage.tsx
  const handleDeletePDF = (collectionId: string, pdfId: string) => {
    const updatedCollections = collections.map((collection) =>
      collection.id === collectionId
        ? {
            ...collection,
            pdfs: collection.pdfs.filter((pdf) => pdf.id !== pdfId),
          }
        : collection
    );
    setCollections(updatedCollections);
    saveToLocalStorage(updatedCollections);
    toast.success("PDF removed from collection");
  };

  // From LibraryPage.tsx
  const handleAddPDFs = (collectionId: string) => {
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.accept = ".pdf";
    input.onchange = (e) => {
      const files = Array.from((e.target as HTMLInputElement).files || []);
      if (files.length > 0) {
        toast.info(
          "Adding PDFs is currently handled via the Home page upload."
        );
      }
    };
    input.click();
  };

  // From LibraryPage.tsx
  const filteredCollections = collections.filter((collection) =>
    (collection.name || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <BackgroundLines className="min-h-screen flex flex-col relative">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm p-4 relative z-10">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <TypewriterEffectSmoothDemo />
          <ThemeToggle />
        </div>
      </header>

      {/* Main Content - Hero Section & Upload */}
      <main className="flex-1 flex items-center justify-center p-4 relative z-10">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-8 w-full">
          {/* Hero Section (Left Aligned) */}
          <div className="flex flex-col items-center md:items-start text-center md:text-left space-y-4 md:w-1/2">
            <h1 className="text-5xl font-bold leading-tight">
              Unlock Knowledge from Your PDFs with AI
            </h1>
            <p className="text-lg text-muted-foreground max-w-md">
              Upload, organize, and gain AI-powered insights from your PDF documents. Create collections, generate insights, and transform your learning experience.
            </p>
            <Button size="lg" onClick={() => navigate("/collections")}>
              Explore Collections
            </Button>
          </div>

          {/* Upload Section (Right Aligned) */}
          <Card className="w-full md:w-1/2 max-w-md">
            <CardContent className="p-6 space-y-6">
              

              <UploadZone isHomepageDropzone={true} />
            </CardContent>
          </Card>
        </div>
      </main>
    </BackgroundLines>
  );
};

export default HomePage;

