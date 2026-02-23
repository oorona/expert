# AI Expert Diagnostic Engine

An advanced, production-ready AI Diagnostic System designed for high-pressure environments. This project leverages state-of-the-art **Artificial Intelligence**, **Machine Learning**, and **Data Science** to autonomously ingest system errors, process screenshots, query external web data, cross-reference internal documentation, and generate highly structured, actionable resolution paths.

Built to mimic the cognitive workflow of a Senior Site Reliability Engineer (SRE), this system acts as a highly specialized, always-on technical expert.

---

## Core AI & Machine Learning Capabilities

This project isn't just an API wrapper; it incorporates advanced ML search topologies, complex LLM orchestration, reciprocal rank fusion, and multimodal analysis.

### 1. Hybrid Semantic Search & RRF (Reciprocal Rank Fusion)
Retrieving the right past incident or documentation chunk is critical. This project utilizes a hybridized search architecture directly within PostgreSQL:
*   **Vector Search (`pgvector`)**: Computes dense Euclidean/cosine similarity metrics. Errors are embedded using `gemini-embedding-001` (768 dimensions), allowing the system to understand the conceptual meaning of an error rather than just textual overlap.
*   **BM25 Full-Text Search**: Utilizes sparse vector matching (`pg_textsearch`) for high-precision exact keyword hits (e.g., specific error codes).
*   **Reciprocal Rank Fusion (RRF)**: The engine mathematically merges the normalized scores of both the dense (semantic) and sparse (keyword) outputs using an equal 0.5/0.5 weighting strategy to surface the absolute best historical context.

### 2. Autonomous RAG (Retrieval-Augmented Generation) & File Search
The AI supports customized "Experts" (e.g., an Oracle Database Expert, a Kubernetes Expert). Each expert is linked to a private RAG document store.
*   When a diagnostic is required, the LLM actively queries this document store, citing its sources automatically via internal grounding.
*   Provides robust citation mappings (confidence scores, page numbers, and chunk text) to guarantee traceability and decrease hallucinations.

### 3. Integrated Web Grounding
For bleeding-edge or undocumented errors, the engine escapes its knowledge base and utilizes live Google Search grounding. The LLM parses recent forums and vendor documentation in real-time to formulate a verified resolution.

### 4. Automated Image Understanding (Multimodal ML)
Users can upload screenshots of dashboards, stack traces, or broken UIs. The system uses multimodal optical character recognition and visual reasoning to understand the context of the error image, transcribing the visual anomaly into a structured textual diagnostic process.

### 5. Infinite "Thinking" Mode Configuration
The architecture fully supports Gemini's advanced reasoning (Thinking) capabilities. Real-time inference steps are streamed back to the client, allowing operators to watch the AI's internal reasoning process (budgeting up to 24,576 tokens for deep problem-solving) before it commits to an answer.

### 6. Automated Schema & Prompt Generation
The system employs AI to manage the AI. When an operator creates a new Expert profile, the LLM is invoked to autonomously **generate and refine its own system and user prompts**, tailoring its internal behavior to the specific technical domain (e.g., rewriting generic prompts into deep Kubernetes-specific architectural instructions).

### 7. Generative Image Data Visualization (Text-to-Image)
Not all problems are best solved with text. This platform uses `imagen-3.0-generate-001` to automatically generate technical infographics (architecture diagrams, flowcharts, or configuration comparisons) based on the context of the error, aiding visual learners.

---

## Documentation
Detailed documentation regarding installation, configuration, and architecture can be found in the `docs/` directory:

*   **[Installation Guide](docs/INSTALLATION.md)**: Prerequisites and quick-start instructions.
*   **[Configuration Guide](docs/CONFIGURATION.md)**: Environment variants, secrets management, and proxies.
*   **[Architecture Deep Dive](docs/ARCHITECTURE.md)**: Technical overview of the Next.js/FastAPI/PostgreSQL stack.

*(Technical specifications can be found under `specs/specs.txt`)*

---

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
