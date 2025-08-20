import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Collection } from "@/types"; // Import Collection from types
import { FolderOpen, MoreHorizontal, Trash2, FileText, Headphones, Edit } from "lucide-react";
import React from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";
import { UpdateCollectionDialog } from "./update-collection-dialog";

interface CollectionCardProps {
  collection: Collection;
  onSelectCollection: (collection: Collection) => void;
  onDeleteCollection: (collectionId: string) => void;
  onCollectionUpdated: () => void; // New prop for refreshing collections
}

export function CollectionCard({
  collection,
  onSelectCollection,
  onDeleteCollection,
  onCollectionUpdated,
}: CollectionCardProps) {
  const navigate = useNavigate();

  return (
    <Card
      className="border border-border/50 bg-card/80 backdrop-blur-sm cursor-pointer"
      onClick={() => onSelectCollection(collection)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FolderOpen className="h-5 w-5 text-primary" />
            <div className="cursor-pointer">
              <CardTitle className="text-lg font-semibold">
                {collection.name || 'Untitled Collection'}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {collection.total_docs} document
                {collection.total_docs !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}> {/* Stop propagation here */}
                <span className="sr-only">Open menu</span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <UpdateCollectionDialog
                collection={collection}
                onCollectionUpdated={onCollectionUpdated}
              >
                <DropdownMenuItem onSelect={(e) => { e.preventDefault(); e.stopPropagation(); }} onClick={(e) => e.stopPropagation()}> {/* Prevent dropdown from closing immediately and stop propagation */}
                  <Edit className="mr-2 h-4 w-4" /> Update
                </DropdownMenuItem>
              </UpdateCollectionDialog>
              <DropdownMenuItem
                onSelect={(e) => {
                  e.stopPropagation(); // Prevent event from bubbling up to the Card's onClick
                  onDeleteCollection(collection.id);
                }}
                onClick={(e) => e.stopPropagation()}
                className="text-red-600 focus:text-red-600"
              >
                <Trash2 className="mr-2 h-4 w-4" /> Delete
              </DropdownMenuItem>
              {collection.latestInsightId && (
                <DropdownMenuItem onSelect={(e) => { e.stopPropagation(); navigate(`/insight/${collection.latestInsightId}`); }} onClick={(e) => e.stopPropagation()}>
                  <FileText className="mr-2 h-4 w-4" /> View Insight
                </DropdownMenuItem>
              )}
              {collection.latestPodcastId && (
                <DropdownMenuItem onSelect={(e) => { e.stopPropagation(); navigate(`/podcast/${collection.latestPodcastId}`); }} onClick={(e) => e.stopPropagation()}>
                  <Headphones className="mr-2 h-4 w-4" /> View Podcast
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent className="pb-4">
        {collection.description && (
          <p className="text-sm text-muted-foreground mb-2">
            {collection.description}
          </p>
        )}
        {collection.tags && collection.tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {collection.tags.map((tag, index) => (
              <Badge key={index} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}