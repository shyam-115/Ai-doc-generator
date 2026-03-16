This document outlines the project structure of the "Ai-doc-generator" application, providing a guide for developers to understand its organization, responsibilities of different modules, and where to contribute new features.

## 1. Overview

The "Ai-doc-generator" project is designed to automatically generate various types of documentation (e.g., READMEs, API docs, architecture overviews, project structure guides) for code repositories using AI. Its architecture is modular, separating concerns into distinct components responsible for code loading, parsing, analysis, chunking, embedding, and documentation generation. This design promotes maintainability, scalability, and clear separation of concerns, making it easier to develop, test, and extend the system.

## 2. Directory Structure

```
Ai-doc-generator/
├── analyzer/
│   ├── __init__.py
│   ├── call_graph.py  # 1 class(es), 4 function(s)
│   └── dependency_graph.py  # 1 class(es), 3 function(s)
├── api/
│   ├── __init__.py
│   └── main.py  # 2 class(es), 4 function(s)
├── chunking/
│   ├── __init__.py
│   └── code_chunker.py  # 1 class(es), 5 function(s)
├── cli/
│   ├── __init__.py
│   └── generate_docs.py  # 6 function(s)
├── core/
│   ├── __init__.py
│   ├── language_detector.py  # 4 function(s)
│   └── repo_loader.py  # 1 class(es), 4 function(s)
├── final_test/
│   ├── README.md
│   ├── api_docs.md
│   └── architecture.md
├── generator/
│   ├── __init__.py
│   ├── api_doc_generator.py  # 1 class(es), 6 function(s)
│   