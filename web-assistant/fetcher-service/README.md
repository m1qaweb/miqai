# Fetcher Service

This microservice fetches a web page from a given URL, extracts the text content from all paragraph (`<p>`) tags, and returns it as plain text.

## Prerequisites

- [Node.js](https://nodejs.org/) (v14 or later)
- [npm](https://www.npmjs.com/)

## Installation

1.  Navigate to the `fetcher-service` directory.
2.  Install the dependencies:
    ```bash
    npm install
    ```

## Running the Service

1.  Start the server:
    ```bash
    node index.js
    ```
2.  The service will be running at `http://localhost:8889`.

## API

### GET /fetch

Fetches and extracts text from a URL.

- **URL Query Parameter:**

  - `url` (required): The URL of the web page to fetch.

- **Example Request:**

  ```
  http://localhost:8889/fetch?url=https://www.example.com
  ```

- **Success Response:**

  - **Code:** 200 OK
  - **Content:** The extracted text from the web page.

- **Error Response:**
  - **Code:** 400 Bad Request (if `url` parameter is missing)
  - **Code:** 500 Internal Server Error (if the fetch or parsing fails)
