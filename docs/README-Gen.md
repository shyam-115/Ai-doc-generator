# ai-doc-gen-i2t6qfb4

## Project Overview

`ai-doc-gen-i2t6qfb4` is a full-stack application designed for AI-powered document generation. It provides a robust backend for handling document processing, user authentication, and file storage, coupled with a modern frontend for user interaction. The project aims to streamline the creation and management of various document types by leveraging AI capabilities, offering a comprehensive solution for automated content generation and secure asset management.

## Tech Stack

This project utilizes a modern JavaScript-centric tech stack, divided into a backend API and a frontend client.

**Languages:**
*   JavaScript
*   HTML
*   CSS
*   JSON
*   Markdown

**Backend:**
*   **Node.js:** JavaScript runtime environment.
*   **Express.js (Inferred):** Web application framework for building RESTful APIs.
*   **Database (Inferred):** Likely a NoSQL (e.g., MongoDB) or SQL database, managed via `connectDB`.
*   **Cloudinary:** Cloud-based media management service for storing and serving uploaded files.
*   **Configuration Management:** Utilizes a `config` module for environment variable handling.
*   **Authentication:** Implements token-based authentication with `genAccessAndRefreshToken`.

**Frontend:**
*   **Vite:** Next-generation frontend tooling for fast development.
*   **React/Vue/Svelte (Inferred):** A modern JavaScript framework/library for building user interfaces, given the `vite.config.js` and `src` structure.

## Prerequisites

Before setting up the project, ensure you have the following installed:

*   **Node.js**: Version 18.x or higher.
    *   [Download Node.js](https://nodejs.org/)
*   **npm** or **Yarn**: Package manager (npm comes with Node.js).
    *   To install Yarn: `npm install -g yarn`
*   **Git**: For cloning the repository.
    *   [Download Git](https://git-scm.com/downloads)

Additionally, you will need accounts and API keys for:
*   **Cloudinary**: For file uploads and storage.
*   **Database**: Connection URI for your chosen database (e.g., MongoDB Atlas, PostgreSQL).

## Installation

Follow these steps to set up and run the project locally.

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/ai-doc-gen-i2t6qfb4.git
cd ai-doc-gen-i2t6qfb4
```

### 2. Backend Setup

Navigate to the `back-end` directory and install dependencies.

```bash
cd back-end
npm install # or yarn install
```

Create a `.env` file in the `back-end` directory based on a `.env.example` (if provided, otherwise create manually) and populate it with your environment variables.

```env
PORT=8000
MONGODB_URI="your_mongodb_connection_string"
CORS_ORIGIN="http://localhost:5173" # Or your frontend URL
ACCESS_TOKEN_SECRET="your_access_token_secret"
REFRESH_TOKEN_SECRET="your_refresh_token_secret"
ACCESS_TOKEN_EXPIRY="1h"
REFRESH_TOKEN_EXPIRY="10d"
CLOUDINARY_CLOUD_NAME="your_cloudinary_cloud_name"
CLOUDINARY_API_KEY="your_cloudinary_api_key"
CLOUDINARY_API_SECRET="your_cloudinary_api_secret"
```

### 3. Frontend Setup

Navigate to the `front-end` directory and install dependencies.

```bash
cd ../front-end
npm install # or yarn install
```

Create a `.env` file in the `front-end` directory (e.g., `.env.local` for Vite) and populate it with your environment variables, primarily the backend API URL.

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Usage

### 1. Start the Backend Server

From the `back-end` directory:

```bash
npm run dev # Or 'node src/index.js' if no dev script is configured
```

The backend server will typically run on `http://localhost:8000` (or the port specified in your `.env`).

### 2. Start the Frontend Development Server

From the `front-end` directory:

```bash
npm run dev
```

The frontend application will typically open in your browser at `http://localhost:5173` (or the port specified by Vite).

You can now interact with the application through your web browser.

## Project Structure

The project is organized into `back-end` and `front-end` directories, representing a typical full-stack architecture.

```
ai-doc-gen-i2t6qfb4/
├── back-end/                  # Contains the Node.js/Express API server
│   ├── public/                # Static assets served by the backend (e.g., temporary uploads)
│   ├── src/                   # Source code for the backend application
│   │   ├── controllers/       # Request handlers for API endpoints
│   │   ├── models/            # Database schemas and models
│   │   ├── routes/            # API route definitions
│   │   ├── utils/             # Utility functions (e.g., asyncHandler, ApiError, ApiResponse, uploadOnCloudinary)
│   │   ├── middlewares/       # Express middleware (e.g., requestId, validate, validateAll)
│   │   ├── db/                # Database connection logic (connectDB)
│   │   ├── config/            # Configuration management (validateEnv)
│   │   └── index.js           # Main entry point for the backend server
│   ├── Readme.md              # Backend-specific README
│   ├── package-lock.json      # Locked dependencies for backend
│   └── package.json           # Backend dependencies and scripts
└── front-end/                 # Contains the client-side application (e.g., React, Vue)
    ├── public/                # Static assets for the frontend (e.g., index.html, favicon)
    ├── src/                   # Source code for the frontend application
    │   ├── components/        # Reusable UI components
    │   ├── pages/             # Application pages/views
    │   ├── services/          # API interaction logic
    │   ├── assets/            # Frontend-specific static assets (images, fonts)
    │   └── main.jsx           # Main entry point for the frontend application
    ├── README.md              # Frontend-specific README
    ├── eslint.config.js       # ESLint configuration for frontend
    ├── index.html             # Main HTML file for the frontend
    ├── package-lock.json      # Locked dependencies for frontend
    ├── package.json           # Frontend dependencies and scripts
    └── vite.config.js         # Vite build configuration
```

## API Reference

The backend API provides a set of endpoints for user management, authentication, file uploads, and document generation. Key functionalities are built around custom utility functions and classes for consistent error handling and response formatting.

**Core Concepts:**
*   **`ApiError`**: Custom error class for standardized API error responses.
*   **`ApiResponse`**: Custom success response class for consistent API data formatting.
*   **`asyncHandler`**: Utility for wrapping asynchronous Express route handlers to catch errors.
*   **`validate`, `validateAll`**: Middleware or utility functions for input validation.
*   **`requestId`**: Middleware for tracking requests.

**Key Endpoints (Inferred):**

### Authentication & User Management
*   **`POST /api/v1/users/register`**: Register a new user.
*   **`POST /api/v1/users/login`**: Authenticate a user and generate access/refresh tokens.
    *   *Functionality*: `genAccessAndRefreshToken`
*   **`POST /api/v1/users/logout`**: Invalidate user tokens.
*   **`POST /api/v1/users/refresh-token`**: Obtain a new access token using a refresh token.
*   **`GET /api/v1/users/current-user`**: Get details of the currently logged-in user (requires authentication).

### File Uploads
*   **`POST /api/v1/upload`**: Upload files (e.g., images, documents) to Cloudinary.
    *   *Functionality