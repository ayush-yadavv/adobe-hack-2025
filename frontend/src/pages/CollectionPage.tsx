import React, { useEffect, useState, useCallback } from 'react';
import { CollectionCard } from '@/components/collection-card';
import { Input } from '@/components/ui/input';
import { Search, Plus, ArrowLeft } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Collection } from '@/types'; // Import Collection from types
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { CreateCollectionDialog } from '@/components/create-collection-dialog';
import { NewCollectionCard } from '@/components/new-collection-card';

const CollectionPage: React.FC = () => {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('name'); // 'name' or 'createdDate'
  const [filterBy, setFilterBy] = useState('all'); // 'all', 'hasInsight', 'hasPodcast'
  const navigate = useNavigate();

  const fetchCollections = useCallback(async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/collections`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data: Collection[] = await response.json();
      console.log('Fetched collections:', data);
      setCollections(data);
    } catch (error) {
      console.error('Error fetching collections:', error);
      toast.error('Failed to load collections.');
    }
  }, []);

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  const sortedAndFilteredCollections = React.useMemo(() => {
    let currentCollections = [...collections];

    // Apply filterBy
    if (filterBy === 'hasInsight') {
      currentCollections = currentCollections.filter(collection => collection.latestInsightId !== null);
    } else if (filterBy === 'hasPodcast') {
      currentCollections = currentCollections.filter(collection => collection.latestPodcastId !== null);
    }

    // Apply sortBy
    currentCollections.sort((a, b) => {
      if (sortBy === 'name') {
        return a.name.localeCompare(b.name);
      } else if (sortBy === 'createdDate') {
        // Assuming createdAt is a string that can be converted to Date
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      }
      return 0;
    });

    // Apply searchTerm filter
    return currentCollections.filter(collection =>
      (collection.name || '').toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [collections, searchTerm, sortBy, filterBy]);

  const handleDeleteCollection = async (collectionId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/collections/${collectionId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      toast.success('Collection deleted successfully!');
      fetchCollections(); // Refresh the list of collections
    } catch (error) {
      console.error('Error deleting collection:', error);
      toast.error('Failed to delete collection.');
    }
  };

  return (
    <div className="min-h-screen flex flex-col px-8 py-4">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => navigate('/')}
        className="mb-2"
      >
        <ArrowLeft className="h-6 w-6" />
      </Button>
      <h1 className="text-3xl font-bold mb-6 mt-8">Library</h1>

      <div className="flex items-center gap-4 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search collections..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">Sort By: {sortBy === 'name' ? 'Name' : 'Date Created'}</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setSortBy('name')}>Name (A-Z)</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setSortBy('createdDate')}>Date Created (Newest)</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">Filter By: {filterBy === 'all' ? 'All' : filterBy === 'hasInsight' ? 'Has Insight' : 'Has Podcast'}</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setFilterBy('all')}>All</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFilterBy('hasInsight')}>Has Insight</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFilterBy('hasPodcast')}>Has Podcast</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        
      </div>

      {sortedAndFilteredCollections.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <CreateCollectionDialog onCollectionCreated={fetchCollections}>
            <NewCollectionCard />
          </CreateCollectionDialog>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <CreateCollectionDialog onCollectionCreated={fetchCollections}>
            <NewCollectionCard />
          </CreateCollectionDialog>
          {sortedAndFilteredCollections.map((collection) => (
            <CollectionCard
              key={collection.id}
              collection={collection}
              onSelectCollection={(selectedCollection) => {
                // Check if the selected collection still exists in the current state
                const exists = collections.some(c => c.id === selectedCollection.id);
                if (exists) {
                  navigate(`/collections/${selectedCollection.id}`);
                } else {
                  // Optionally, show a toast or log a message if the collection is not found
                  console.warn("Attempted to navigate to a non-existent collection.");
                }
              }}
              onDeleteCollection={handleDeleteCollection}
              onCollectionUpdated={fetchCollections}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default CollectionPage;
