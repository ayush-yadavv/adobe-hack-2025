# AI-Powered Document Insights and Recommendations

This project is a comprehensive application designed to process documents, generate AI-driven insights, and provide personalized recommendations. It features a robust FastAPI backend API and a modern React frontend, orchestrated using Docker Compose for easy setup and deployment.

## Features

- **Document Processing:** Upload and process various document types (e.g., PDFs).
- **AI-Driven Insights:** Extract key information, summaries, and insights from documents using AI models.
- **Personalized Recommendations:** Generate recommendations based on document content and user interactions.
- **Collection Management:** Organize documents into collections.
- **Podcast Generation:** (Potentially) Convert document insights into audio podcasts.

### Important Note on Highlighting:

The document highlighting functionality is currently unreliable (approximately 80% failure rate). The system attempts fallbacks to text search and then annotations if direct highlighting fails. The "go to page" feature works correctly. The team is interested in exploring more robust highlighting methods.

## Architecture

The project is composed of two main services:

- **Backend (FastAPI):** A Python-based API that handles document processing, AI model interactions, data storage, and serves the API endpoints.
- **Frontend (React):** A modern web application built with React and TypeScript, providing a user interface for interacting with the backend services.

Both services are containerized using Docker and orchestrated with Docker Compose.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Installation and Running

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/ayush-yadavv/adobe-hack-2025.git
    cd adobe-hack-2025
    ```

2.  **Environment Variables:**
    Create a `.env` file in the root directory of the project (where `docker-compose.yml` is located) and add the necessary environment variables. At a minimum, you'll need:

    ```
    LLM_PROVIDER= # e.g., "google" or "openai"
    GEMINI_MODEL= # e.g., "gemini-pro" (if using Google LLM)
    TTS_PROVIDER= # e.g., "google" or "azure"
    AZURE_TTS_KEY= # Your Azure Text-to-Speech key (if using Azure TTS)
    AZURE_TTS_ENDPOINT= # Your Azure Text-to-Speech endpoint (if using Azure TTS)
    GOOGLE_APPLICATION_CREDENTIALS= # Path to your Google Cloud credentials JSON file (if using Google LLM/TTS)
    ```

    _Note: For `GOOGLE_APPLICATION_CREDENTIALS`, you might need to mount this file into the Docker container. For local development, you can place it in the `backend` directory and update the `docker-compose.yml` volume mount accordingly._

3.  **Frontend Environment Variables:**
    Create a `.env` file inside the `frontend` directory (e.g., `frontend/.env`) and add the `ADOBE_EMBED_API_KEY`. This key is used by the frontend to embed documents.

    ```
    ADOBE_EMBED_API_KEY=YOUR_ADOBE_EMBED_API_KEY
    ```

    _You can obtain your Adobe Embed API Key from Adobe's developer portal._

4.  **Build the Docker images:**
    This command will build the Docker images for both the frontend and backend services based on their respective `Dockerfile`s.

    ```bash
    docker-compose build
    ```

    takes 30 min max

5.  **Run the Docker containers:**
    This command will start both the backend and frontend services in detached mode (in the background).

    ```bash
    docker-compose up -d
    ```

6.  **Access the Application:**
    - **Frontend:** Open your web browser and navigate to `http://localhost:8080`
    - **Backend API:** The API will be available at `http://localhost:8000` (e.g., `http://localhost:8000/docs` for OpenAPI documentation).

## Backend

The backend is built with FastAPI and handles all the core logic of the application.

### Technologies Used

- **FastAPI:** High-performance web framework for building APIs with Python.
- **Uvicorn:** ASGI server.
- **SQLAlchemy:** ORM for database interactions (using SQLite by default).
- **PyMuPDF:** For PDF parsing.
- **Sentence Transformers & FAISS:** For machine learning models related to insights and recommendations.
- **Requests, Google Cloud Text-to-Speech, pydub:** For optional LLM/TTS integrations and audio manipulation.

### Key Features

- RESTful API for document and collection management.
- Integration with AI models for insight generation.
- Recommendation engine.
- Modular and scalable architecture.

### API Documentation

Once the backend is running, you can access the interactive API documentation (Swagger UI) at `http://localhost:8000/docs`.

## Frontend

The frontend is a modern web application providing the user interface.

### Technologies Used

- **React:** JavaScript library for building user interfaces.
- **TypeScript:** Superset of JavaScript that adds static typing.
- **Vite:** Fast build tool for modern web projects.
- **Shadcn/ui:** Reusable UI components.
- **Tailwind CSS:** Utility-first CSS framework.
- **React Query:** For data fetching and state management.
- **React Router DOM:** For client-side routing.

### Key Features

- User-friendly interface for uploading and viewing documents.
- Display of AI-generated insights.
- Management of document collections.
- Responsive design.

## Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'feat: Add new feature'`).
5.  Push to the branch (`git push origin feature/your-feature-name`).
6.  Open a Pull Request.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
