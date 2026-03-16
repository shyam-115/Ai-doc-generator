# AI Document Generator API Documentation

This document provides comprehensive API documentation for the AI Document Generator platform, outlining available endpoints, authentication methods, request/response structures, and error handling.

## Table of Contents

1.  [Overview](#overview)
2.  [Authentication](#authentication)
3.  [Endpoints](#endpoints)
    *   [Health Check](#health-check)
    *   [Get Item Status](#get-item-status)
    *   [Get Item Count](#get-item-count)
    *   [Like/Unlike Item](#likeunlike-item)
    *   [Search Users](#search-users)
    *   [Upload Video](#upload-video)
    *   [List Videos](#list-videos)
    *   [Get Channel Videos](#get-channel-videos)
    *   [Get Video Details](#get-video-details)
4.  [Error Codes](#error-codes)
5.  [Rate Limiting](#rate-limiting)
6.  [Examples](#examples)

---

## 1. Overview

The AI Document Generator API provides a suite of services for managing and interacting with AI-generated content, including document generation, content interaction (liking), user search, and video management. This API is designed to be RESTful, using standard HTTP methods and status codes.

*   **Purpose:** To programmatically interact with the AI Document Generator platform, enabling content creation, retrieval, and user engagement.
*   **Base URL:** `https://api.ai-doc-gen.com/api/v1`
*   **Authentication:** All protected endpoints require authentication using a Bearer Token (JWT).

---

## 2. Authentication

The AI Document Generator API uses JSON Web Tokens (JWTs) for authentication. After a user successfully logs in (via a separate authentication endpoint not detailed here), an access token (JWT) is issued. This token must be included in the `Authorization` header of all subsequent requests to protected endpoints.

**Authentication Header Example:**

```
Authorization: Bearer <YOUR_ACCESS_TOKEN>
```

*   Replace `<YOUR_ACCESS_TOKEN>` with the actual JWT obtained after successful authentication.
*   Tokens typically have an expiration time. If a request returns a `401 Unauthorized` error, your token may have expired or be invalid.

---

## 3. Endpoints

This section details all available API endpoints, their functionality, parameters, and expected responses.

### Health Check

Checks the health and availability of the API service.

*   **`GET /health`**

**Description:**
Returns a simple status message indicating if the API is operational. This endpoint does not require authentication.

**Request Parameters:**
None.

**Response Schema:**
```json
{
  "status": "string",
  "message": "string"
}
```

**Example Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Service is healthy"
}
```

**Error Codes:**
*   `500 Internal Server Error`: If the service encounters an unexpected issue.

---

### Get Item Status

Retrieves the current status of a specific item, which could be a document generation job, a video upload, or a like operation.

*   **`GET /status/:id`**

**Description:**
Fetches the status of an item identified by its unique ID. This is useful for tracking asynchronous operations.

**Request Parameters:**

| Name | Type   | In     | Required | Description                               |
| :--- | :----- | :----- | :------- | :---------------------------------------- |
| `id` | string | Path   | Yes      | The unique identifier of the item to check status for. |

**Response Schema:**
```json
{
  "id": "string",
  "status": "string",
  "progress": "number",
  "message": "string",
  "createdAt": "string",
  "updatedAt": "string"
}
```

**Example Response (200 OK):**
```json
{
  "id": "doc_12345",
  "status": "processing",
  "progress": 75,
  "message": "Document generation in progress.",
  "createdAt": "2023-10-26T10:00:00Z",
  "updatedAt": "2023-10-26T10:15:30Z"
}
```

**Error Codes:**
*   `401 Unauthorized`: If the request lacks valid authentication credentials.
*   `404 Not Found`: If an item with the specified `id` does not exist.
*   `500 Internal Server Error`: If an unexpected server error occurs.

---

### Get Item Count

Retrieves the count associated with a specific item, such as the number of likes, views, or comments.

*   **`GET /:id/count`**

**Description:**
Returns the total count for a given item ID. This is typically used for social metrics like "likes".

**Request Parameters:**

| Name | Type   | In     | Required | Description                               |
| :--- | :----- | :----- | :------- | :---------------------------------------- |
| `id` | string | Path   | Yes      | The unique identifier of the item to get the count for. |

**Response Schema:**
```json
{
  "id": "string",
  "count": "number",
  "type": "string"
}
```

**Example Response (200 OK):**
```json
{
  "id": "video_abcde",
  "count": 1250,
  "type": "likes"
}
```

**Error Codes:**
*   `401 Unauthorized`: If the request lacks valid authentication credentials.
*   `404 Not Found`: If an item with the specified `id` does not exist.
*   `500 Internal Server Error`: If an unexpected server error occurs.

---

### Like/Unlike Item

Allows a user to like or unlike a specific item.

*   **`POST /:id`**

**Description:**
Toggles the like status for an item. If the user has already liked the item, it will be unliked. If not, it will be liked.

**Request Parameters:**

| Name | Type   | In     | Required | Description                               |
| :--- | :----- | :----- | :------- | :---------------------------------------- |
| `id` | string | Path   | Yes      | The unique identifier of the item to like/unlike. |

**Request Body Schema (application/json):**
```json
{
  "action": "string"
}
```
*   `action`: Can be `"like"` or `"unlike"`. If omitted, the API might toggle based on current state. Explicit action is recommended.

**Example Request Body (Like):**
```json
{
  "action": "like"
}
```

**Response Schema:**
```json
{
  "id": "string",
  "liked": "boolean",
  "totalLikes": "number",
  "message": "string"
}
```

**Example Response (200 OK - Liked):**
```json
{
  "id": "video_abcde",
  "liked":