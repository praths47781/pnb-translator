# Project Structure & Organization

## Current Architecture
```
app.py                   # Main FastAPI backend with all endpoints
index.html              # Complete frontend with modern UI
pdf_generator.py        # ReportLab-based PDF generation
docx_generator.py       # python-docx Word document generation
requirements.txt        # Python dependencies
Dockerfile              # Container configuration with font support
README.md               # Complete setup and usage guide
.kiro/steering/         # Project documentation and guidelines
```

## File Responsibilities

### `app.py` (Main Backend Application)
- FastAPI application with production-optimized logging and CORS
- Multiple endpoints: `/translate-stream`, `/translate`, `/download`, `/health`, `/s3-status`
- AWS Bedrock Runtime SDK with streaming support and fixed retry logic
- Claude 4.5 Opus model invocation with real-time streaming capabilities
- S3 integration with background uploads for file storage and management
- Base64 file handling with 15MB size limits and memory optimization
- Advanced error handling, status monitoring, and production logging
- Environment configuration (BUCKET_NAME, MODEL_ID) optimized for EC2

### `index.html` (Complete Frontend Application)
- Modern responsive UI with PNB Housing Finance branding and animations
- Drag-and-drop file upload with visual feedback and real-time streaming
- Live translation display with Server-Sent Events integration
- Language selection (English ↔ Hindi) with visual icons and progress tracking
- In-browser document editing capabilities with live preview
- Multiple download formats (PDF, DOCX, TXT) with instant generation
- Professional styling with CSS custom properties and mobile optimization
- Production-optimized JavaScript with commented debug logs

### `pdf_generator.py` (PDF Generation Module)
- ReportLab-based professional PDF creation
- Hindi font support with automatic font registration
- Professional templates with PNB branding
- Table formatting and document structure preservation
- Metadata sections and confidentiality notices
- Custom styling for headers, footers, and content

### `docx_generator.py` (Word Document Module)
- python-docx based Word document generation
- Professional formatting with company branding
- Table creation from pipe-separated content
- Metadata sections and translation information
- Header/footer management with confidentiality notices
- Support for various document elements (lists, tables, headers)

## API Contract

### Main Endpoints

#### `POST /translate-stream` (Primary)
**Request (JSON Body):**
```json
{
  "body": "base64_encoded_pdf_data",
  "target_lang": "hi" | "en",
  "template_choice": "simplified"
}
```

**Response (Server-Sent Events):**
```
data: {"type": "start", "document_id": "stream_123", "status": "starting"}
data: {"type": "chunk", "chunk": "translated_text", "progress": 50}
data: {"type": "final", "translated_document": "complete_text", "status": "complete"}
```

#### `POST /translate` (Legacy)
**Request (JSON Body):**
```json
{
  "body": "base64_encoded_pdf_data",
  "target_lang": "hi" | "en",
  "template_choice": "simplified"
}
```

**Response (JSON):**
```json
{
  "success": true,
  "document_id": "req_1234567890",
  "detected_language": "English",
  "target_language": "Hindi",
  "translated_document": "translated_text_content",
  "processing_time": 25.67,
  "message": "Document translated successfully"
}
```

#### `POST /download`
**Request (JSON Body):**
```json
{
  "translated_text": "document_content",
  "source_lang": "English",
  "target_lang": "Hindi",
  "format": "pdf" | "docx" | "txt"
}
```

**Response:**
- Content-Type: `application/pdf` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `text/plain`
- Binary document data for download

#### Additional Endpoints
- `GET /` - Serves the web interface
- `GET /health` - Service health check with configuration info
- `GET /s3-status` - S3 connectivity and file count status
- `POST /test-s3` - S3 upload functionality test

## AWS Integration Patterns
- Use `boto3.client('bedrock-runtime')` for Claude 4.5 calls
- Environment variables: `BUCKET_NAME`, `MODEL_ID`
- AWS credentials configured via CLI (no hardcoded keys)
- Handle Bedrock response parsing with proper error handling

## Claude Processing Flow
1. **PDF Upload**: Base64 encoded PDF sent to Claude 4.5 Opus
2. **AI Processing**: OCR extraction, structure detection, and translation
3. **Content Parsing**: Raw translated text with markdown-like formatting
4. **Post-Processing**: Cleanup of OCR artifacts and formatting normalization
5. **Document Generation**: Professional templates applied via ReportLab/python-docx

## Document Template Specifications

### PDF Templates (ReportLab)
- **Page Format**: A4 with professional margins (72pt standard)
- **Fonts**: Hindi font auto-detection (Noto Sans/DejaVu/Arial fallback)
- **Branding**: PNB Housing Finance header with company styling
- **Colors**: Primary blue (#1e40af), secondary gray (#374151)
- **Tables**: Professional grid styling with alternating row colors
- **Footer**: Confidentiality notice with automatic page numbering

### DOCX Templates (python-docx)
- **Margins**: 1.0 inch on all sides for professional appearance
- **Headers**: Company branding in document header
- **Metadata**: Translation information table with processing details
- **Styling**: Professional fonts with proper hierarchy
- **Tables**: Grid format with bold headers and proper spacing
- **Footer**: Confidentiality notice and service attribution

### Content Structure Preservation
- **Headers**: # ## ### markdown-style hierarchy maintained
- **Lists**: Bullet points (•) and numbered lists preserved
- **Tables**: Pipe-separated format converted to proper tables
- **Formatting**: Bold text (**text**) and emphasis maintained
- **Paragraphs**: Proper spacing and justification applied