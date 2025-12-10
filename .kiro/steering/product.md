# Product Overview

## PDF Translation and Template-Preserving Generator

A backend service that processes uploaded PDF files through AWS Bedrock (Claude 4.5) to extract, translate, and regenerate content using a standardized professional template.

### Core Functionality
- **PDF Upload & Processing**: Accept PDF files up to 15MB via HTTP POST
- **AI-Powered Translation**: Use Claude 4.5 for OCR extraction, structure detection, and English↔Hindi translation
- **Template-Based Rendering**: Generate clean, professional PDFs using a simplified uniform template
- **Structured Output**: Maintain document hierarchy (headings, sections, tables) while applying consistent formatting

### Key Value Proposition
Transform any PDF document into a clean, professionally formatted version while preserving content structure and providing accurate translation between English and Hindi.

### Target Performance
- Translation processing: 15-40 seconds for typical documents
- PDF rendering: Under 2 seconds
- Support for both text-based and scanned PDFs