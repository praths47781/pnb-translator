# API Documentation

## Enterprise PDF Translation Service API

This document provides comprehensive API documentation for the PDF Translation Service.

## Base URL
```
http://localhost:8000
```

## Authentication
The service uses AWS credentials for Bedrock and S3 access. No additional API authentication is required for local deployment.

## Endpoints

### 1. Streaming Translation (Recommended)
**POST /translate-stream**

Real-time streaming translation with Server-Sent Events for live feedback. Supports multiple AI models.

**Request Body:**
```json
{
  "body": "base64_encoded_pdf_data",
  "target_lang": "hi",
  "template_choice": "simplified",
  "model_choice": "claude-opus"
}
```

**Parameters:**
- `body` (string, required): Base64 encoded PDF file data (max 15MB)
- `target_lang` (string, required): Target language (`"hi"` for Hindi, `"en"` for English)
- `template_choice` (string, optional): Template type (default: `"simplified"`)
- `model_choice` (string, optional): AI model (`"claude-opus"` for advanced reasoning, `"nova-2-lite"` for fast processing, default: `"claude-opus"`)

**Response:**
- Content-Type: `text/event-stream`
- Server-Sent Events stream with real-time translation chunks

**Event Types:**

**Start Event:**
```
data: {
  "type": "start",
  "document_id": "stream_1234567890",
  "file_size_mb": 2.54,
  "target_lang": "hi",
  "status": "starting"
}
```

**Chunk Events (Multiple):**
```
data: {
  "type": "chunk",
  "chunk": "# PNB Housing Finance Limited",
  "progress": 25,
  "chunk_count": 1,
  "status": "translating"
}
```

**Final Event:**
```
data: {
  "type": "final",
  "success": true,
  "document_id": "stream_1234567890",
  "detected_language": "English",
  "target_language": "Hindi",
  "translated_document": "complete_translated_text",
  "processing_time": 25.67,
  "message": "Document translated successfully",
  "status": "complete"
}
```

**Error Event:**
```
data: {
  "type": "error",
  "error": "Error message",
  "processing_time": 5.23,
  "status": "error"
}
```

**JavaScript Example:**
```javascript
const eventSource = new EventSource('/translate-stream');
eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'start':
      console.log('Translation started:', data.document_id);
      break;
    case 'chunk':
      console.log('Received chunk:', data.chunk);
      // Update UI with streaming content
      break;
    case 'final':
      console.log('Translation complete:', data.translated_document);
      eventSource.close();
      break;
    case 'error':
      console.error('Translation error:', data.error);
      eventSource.close();
      break;
  }
};
```

---

### 2. Available Models
**GET /models**

Returns list of available AI models for translation.

**Response:**
```json
{
  "models": [
    {
      "id": "claude-opus",
      "name": "Claude 4.5 Opus",
      "description": "Advanced reasoning and document analysis",
      "provider": "Anthropic",
      "model_id": "global.anthropic.claude-opus-4-5-20251101-v1:0"
    },
    {
      "id": "nova-2-lite",
      "name": "Amazon Nova 2 Lite", 
      "description": "Fast and efficient multimodal processing",
      "provider": "Amazon",
      "model_id": "global.amazon.nova-2-lite-v1:0"
    }
  ],
  "default": "claude-opus"
}
```

---

### 3. Web Interface
**GET /**

Serves the main web application interface.

**Response:**
- Content-Type: `text/html`
- Returns the complete web application

---

### 2. Health Check
**GET /health**

Returns service health status and configuration information.

**Response:**
```json
{
  "status": "healthy",
  "service": "PDF Translation Service",
  "version": "1.0.0",
  "bucket": "pnb-poc-docs",
  "model": "global.anthropic.claude-opus-4-5-20251101-v1:0",
  "timestamp": "2024-12-10T10:30:00.000Z"
}
```

---

### 3. S3 Status Check
**GET /s3-status**

Returns S3 connectivity status and file statistics.

**Response:**
```json
{
  "status": "connected",
  "bucket": "pnb-poc-docs",
  "region": "us-east-1",
  "input_files": 25,
  "output_files": 47,
  "recent_files": [
    {
      "key": "input/document_req_1234567890_20241210_103000.pdf",
      "size": 2048576,
      "modified": "2024-12-10T10:30:00.000Z"
    }
  ],
  "folders": {
    "input": "s3://pnb-poc-docs/input/",
    "output": "s3://pnb-poc-docs/output/"
  },
  "timestamp": "2024-12-10T10:30:00.000Z"
}
```

---

### 4. S3 Upload Test
**POST /test-s3**

Tests S3 upload functionality with a small test file.

**Response:**
```json
{
  "status": "success",
  "message": "S3 upload test successful",
  "s3_url": "s3://pnb-poc-docs/test/test_file_test_1234567890.txt",
  "file_size": 45,
  "timestamp": "2024-12-10T10:30:00.000Z"
}
```

---

### 5. Document Translation
**POST /translate**

Translates a PDF document using selected AI model (Claude 4.5 Opus or Amazon Nova 2 Lite).

**Request Body:**
```json
{
  "body": "base64_encoded_pdf_data",
  "target_lang": "hi",
  "template_choice": "simplified",
  "model_choice": "claude-opus"
}
```

**Parameters:**
- `body` (string, required): Base64 encoded PDF file data (max 15MB)
- `target_lang` (string, required): Target language code
  - `"hi"` for Hindi
  - `"en"` for English
- `template_choice` (string, optional): Template type (default: "simplified")
- `model_choice` (string, optional): AI model selection
  - `"claude-opus"` for Claude 4.5 Opus (advanced reasoning, default)
  - `"nova-2-lite"` for Amazon Nova 2 Lite (fast processing)

**Response:**
```json
{
  "success": true,
  "document_id": "req_1234567890",
  "detected_language": "English",
  "target_language": "Hindi",
  "translated_document": "# मुख्य शीर्षक\n\nयह एक अनुवादित दस्तावेज़ है...",
  "processing_time": 25.67,
  "message": "Document translated successfully"
}
```

**Error Response:**
```json
{
  "detail": "File size exceeds 15MB limit"
}
```

**Status Codes:**
- `200`: Translation successful
- `400`: Invalid request (file too large, invalid format, etc.)
- `500`: Internal server error (Bedrock API failure, etc.)

---

### 6. Document Generation
**POST /download**

Generates a professional document from translated text.

**Request Body:**
```json
{
  "translated_text": "# Main Title\n\nThis is translated content...",
  "source_lang": "English",
  "target_lang": "Hindi",
  "format": "pdf"
}
```

**Parameters:**
- `translated_text` (string, required): The translated document content
- `source_lang` (string, optional): Source language name (default: "English")
- `target_lang` (string, optional): Target language name (default: "Hindi")
- `format` (string, required): Output format
  - `"pdf"` for PDF document
  - `"docx"` for Word document
  - `"txt"` for text file

**Response:**
- Content-Type: Varies by format
  - PDF: `application/pdf`
  - DOCX: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - TXT: `text/plain; charset=utf-8`
- Content-Disposition: `attachment; filename=professional_translation.{format}`
- Binary document data

**Status Codes:**
- `200`: Document generated successfully
- `400`: Invalid format or missing content
- `500`: Document generation error

---

## Error Handling

### Common Error Responses

**File Too Large:**
```json
{
  "detail": "File size exceeds 15MB limit"
}
```

**Invalid PDF:**
```json
{
  "detail": "Invalid base64 PDF data"
}
```

**Bedrock API Error:**
```json
{
  "detail": "Request timed out. The document may be too large or complex."
}
```

**S3 Access Error:**
```json
{
  "detail": "S3 upload failed: Access Denied"
}
```

### HTTP Status Codes
- `200`: Success
- `400`: Bad Request (client error)
- `404`: Not Found
- `500`: Internal Server Error
- `504`: Gateway Timeout (Bedrock timeout)

---

## Rate Limiting

Currently, no rate limiting is implemented. For production deployment, consider implementing:
- Request rate limiting per IP
- Concurrent processing limits
- File size and processing time monitoring

---

## Examples

### Complete Translation Workflow

```python
import requests
import base64
import json

# Step 1: Encode PDF file
with open('document.pdf', 'rb') as f:
    pdf_data = base64.b64encode(f.read()).decode()

# Step 2: Translate document
translate_response = requests.post('http://localhost:8000/translate', json={
    'body': pdf_data,
    'target_lang': 'hi',
    'template_choice': 'simplified'
})

if translate_response.status_code == 200:
    result = translate_response.json()
    print(f"Translation completed in {result['processing_time']:.2f}s")
    
    # Step 3: Generate PDF
    pdf_response = requests.post('http://localhost:8000/download', json={
        'translated_text': result['translated_document'],
        'source_lang': result['detected_language'],
        'target_lang': result['target_language'],
        'format': 'pdf'
    })
    
    if pdf_response.status_code == 200:
        with open('translated_document.pdf', 'wb') as f:
            f.write(pdf_response.content)
        print("Professional PDF generated successfully!")
    else:
        print(f"PDF generation failed: {pdf_response.status_code}")
else:
    print(f"Translation failed: {translate_response.status_code}")
    print(translate_response.json())
```

### Health Check Example

```bash
# Check service health
curl -X GET http://localhost:8000/health | jq

# Check S3 status
curl -X GET http://localhost:8000/s3-status | jq

# Test S3 upload
curl -X POST http://localhost:8000/test-s3 | jq
```

### JavaScript/Browser Example

```javascript
// File upload and translation
async function translateDocument(file) {
    // Convert file to base64
    const base64 = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.readAsDataURL(file);
    });
    
    // Translate document
    const translateResponse = await fetch('/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            body: base64,
            target_lang: 'hi',
            template_choice: 'simplified',
            model_choice: 'claude-opus'
        })
    });
    
    if (translateResponse.ok) {
        const result = await translateResponse.json();
        console.log('Translation completed:', result);
        
        // Generate PDF
        const pdfResponse = await fetch('/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                translated_text: result.translated_document,
                source_lang: result.detected_language,
                target_lang: result.target_language,
                format: 'pdf'
            })
        });
        
        if (pdfResponse.ok) {
            const blob = await pdfResponse.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'professional_translation.pdf';
            a.click();
            URL.revokeObjectURL(url);
        }
    }
}
```

---

## Performance Considerations

### Processing Times
- **Translation**: 15-40 seconds for typical documents
- **PDF Generation**: Under 2 seconds
- **DOCX Generation**: Under 3 seconds
- **TXT Generation**: Under 1 second

### Resource Usage
- **Memory**: 2GB minimum recommended for concurrent processing
- **Storage**: S3 storage for input/output files with automatic cleanup
- **Network**: Bedrock API calls require stable internet connection

### Optimization Tips
- Use appropriate file sizes (under 15MB for optimal performance)
- Monitor processing times via health endpoints
- Implement client-side progress indicators for better UX
- Consider caching for frequently translated documents