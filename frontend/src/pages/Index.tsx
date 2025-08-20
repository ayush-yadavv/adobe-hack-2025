import { Routes, Route } from "react-router-dom";
import HomePage from "./HomePage";
import ReaderPage from "./ReaderPage";
import CollectionDetailsPage from "./CollectionDetailsPage";

const Index = () => {
  return (
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/collections/:collectionId" element={<CollectionDetailsPage />} />
        <Route path="/collections/:collectionId/document/:documentId" element={<ReaderPage />} />
      </Routes>
  );
};

export default Index;
