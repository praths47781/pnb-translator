# Project Structure & Organization

## Simplified Architecture
```
app.py                   # Single backend file with all functionality
index.html              # Single frontend file with upload interface
requirements.txt        # Python dependencies
Dockerfile              # Container configuration with WeasyPrint deps
README.md               # Setup and usage instructions
```

## File Responsibilities

### `app.py` (Single Backend File)
- FastAPI application setup and CORS handling
- `/translate` POST endpoint implementation
- AWS Bedrock Runtime SDK integration
- Claude 4.5 model invocation for PDF extraction and translation
- PDF rendering with WeasyPrint (HTML template embedded)
- File upload handling (base64 encoded in JSON body)
- Error handling and HTTP status codes
- Environment variable configuration (BUCKET_NAME, MODEL_ID)

### `index.html` (Single Frontend File)
- File upload interface with drag-and-drop
- Language selection (English ↔ Hindi)
- Progress indicators and error handling
- PDF download functionality
- Base64 encoding for file transmission
- Responsive design for mobile/desktop

## API Contract

### Endpoint: `POST /translate`
**Request (JSON Body):**
```json
{
  "body": "base64_encoded_pdf_data",
  "target_lang": "hi" | "en",
  "template_choice": "simplified"
}
```

**Response:**
- Content-Type: `application/pdf`
- Binary PDF data (direct download)

## AWS Integration Patterns
- Use `boto3.client('bedrock-runtime')` for Claude 4.5 calls
- Environment variables: `BUCKET_NAME`, `MODEL_ID`
- AWS credentials configured via CLI (no hardcoded keys)
- Handle Bedrock response parsing with proper error handling

## Claude Response Schema (Internal)
```json
{
  "title": "string",
  "header": "string", 
  "sections": [
    {
      "heading": "string",
      "body": "HTML-safe string"
    }
  ],
  "tables": [
    {
      "title": "string",
      "headers": ["col1", "col2"],
      "rows": [["row1col1", "row1col2"]]
    }
  ],
  "footer": "string",
  "notes": "string"
}
```

## Template Specifications
- **Margins**: top 36mm, sides 18mm, bottom 24mm
- **Fonts**: Noto Sans / DejaVu Sans / Arial fallback
- **Logo**: Top-right aligned, fixed 140px width
- **Tables**: Bordered, collapsed styling with text wrapping
- **Footer**: Document metadata + auto page numbers