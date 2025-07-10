# The Insight Engine

The Insight Engine is a premium AI-powered video analysis platform designed to extract deep insights from video content. It features a sophisticated, multi-modal architecture that combines state-of-the-art language and vision models to provide rich, context-aware analysis.

## Key Features

*   **AI Summarization Chat:** Upload videos and receive intelligent, context-grounded summaries through an interactive chat interface. The system uses a Retrieval-Augmented Generation (RAG) pipeline to ensure answers are accurate and grounded in the video's content.
*   **Object-Based Clip Extraction:** Automatically detect and extract clips containing specific objects. The system uses an intelligent object detection model and can generate clips based on simple queries.
*   **Multi-Modal RAG Pipeline:** The core of the Insight Engine is its multi-modal RAG pipeline, which processes both transcripts and visual data to provide a comprehensive understanding of the video content.
*   **Dynamic AI Decision Engine:** The system uses a data-driven decision engine to dynamically select the best AI model for a given task based on real-time performance metrics, ensuring an optimal balance of speed and accuracy.
*   **Modern, High-Performance UI:** The frontend is a clean, fast, and responsive dashboard built with Next.js, Shadcn/UI, and Tailwind CSS, providing a superior user experience.
*   **Serverless-Oriented Architecture:** The ingestion pipeline is designed to be serverless, ensuring scalability and cost-effectiveness.

## Getting Started

To get started with the Insight Engine, you will need to have Docker, Python 3.11+, and Node.js installed.

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    ```
2.  **Set up the environment:**
    *   Create a Python virtual environment and install the required dependencies:
        ```bash
        pip install -r insight-engine/requirements.txt
        ```
    *   Install the frontend dependencies:
        ```bash
        cd insight-engine/frontend
        npm install
        ```
3.  **Configure the application:**
    *   Create a `.env` file in the `insight-engine` directory and populate it with the necessary API keys and configuration values. You can use the `.env.example` file in the `Context-Engineering-Intro` directory as a template.
4.  **Run the application:**
    *   Start the backend server:
        ```bash
        uvicorn insight_engine.main:app --host 0.0.0.0 --port 8000
        ```
    *   Start the frontend development server:
        ```bash
        cd insight-engine/frontend
        npm run dev
        ```

## Project Structure

The project is organized into several key directories:

*   `insight-engine/`: The main application, containing the FastAPI backend and the Next.js frontend.
*   `Context-Engineering-Intro/`: Contains documentation and resources related to the context engineering principles used in the project.
*   `video-ai-system/`: A legacy version of the video analysis system.

We welcome contributions to the Insight Engine! Please feel free to open an issue or submit a pull request.
