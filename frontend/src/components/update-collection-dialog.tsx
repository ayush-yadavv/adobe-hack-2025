import React, { useState, useEffect } from "react";
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
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Collection } from "@/types";

interface UpdateCollectionDialogProps {
  collection: Collection;
  onCollectionUpdated: () => void;
  children: React.ReactNode; // To allow the trigger to be passed as a child
}

export function UpdateCollectionDialog({
  collection,
  onCollectionUpdated,
  children,
}: UpdateCollectionDialogProps) {
  const [name, setName] = useState(collection.name);
  const [description, setDescription] = useState(collection.description || "");
  const [tags, setTags] = useState(collection.tags?.join(", ") || "");
  const [isOpen, setIsOpen] = useState(false);

  // Update state when the collection prop changes (e.g., if the dialog is reused for different collections)
  useEffect(() => {
    setName(collection.name);
    setDescription(collection.description || "");
    setTags(collection.tags?.join(", ") || "");
  }, [collection]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const updatedCollection = {
      name,
      description: description || null,
      tags: tags.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0),
    };

    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/collections/${collection.id}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(updatedCollection),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      toast.success(`Collection "${result.name}" updated successfully!`);
      setIsOpen(false); // Close the dialog
      onCollectionUpdated(); // Notify parent to refresh collections
    } catch (error) {
      console.error("Error updating collection:", error);
      toast.error("Failed to update collection.");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Update Collection</DialogTitle>
          <DialogDescription>
            Edit the details for your collection.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="name" className="text-right">
                Name
              </Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="col-span-3"
                required
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="description" className="text-right">
                Description
              </Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="col-span-3"
                placeholder="Optional description for your collection"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="tags" className="text-right">
                Tags
              </Label>
              <Input
                id="tags"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                className="col-span-3"
                placeholder="Comma-separated tags (e.g., research, AI)"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit">Save Changes</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
