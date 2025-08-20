import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import React, { forwardRef } from "react";

export const NewCollectionCard = forwardRef<HTMLButtonElement>((props, ref) => {
  return (
    <Button
      ref={ref}
      className="flex flex-col items-center justify-center p-6 h-auto border-2 border-dashed rounded-lg cursor-pointer hover:bg-muted/50 transition-colors"
      {...props}
      variant="outline"
    >
      <Plus className="h-8 w-8 text-muted-foreground mb-2" />
      <p className="text-lg font-semibold text-muted-foreground">New Collection</p>
    </Button>
  );
});
