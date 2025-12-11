# Enterprise PDF Translation Service

A production-ready FastAPI-based web application that translates PDF documents using AWS Bedrock (Claude 4.5 Opus) with real-time streaming and generates professionally formatted documents with PNB Housing Finance branding.

## Features

### Core Translation Capabilities
- **🔄 Real-Time Streaming Translation**: Live translation with Server-Sent Events showing text as it's generated
- **🤖 AI-Powered Translation**: Uses Claude 4.5 Opus for intelligent OCR extraction and English↔Hindi translation
- **📋 Document Structure Preservation**: Maintains headings, sections, tables, lists, and formatting hierarchy
- **📄 Multiple Output Formats**: Generate professional PDFs, Word documents (DOCX), and text files
- **🎨 Professional Templates**: PNB Housing Finance branded documents with consistent enterprise styling
- **🔤 Hindi Font Support**: Automatic font detection and registration for proper Hindi text rendering

### Web Application Features
- **🌐 Modern Web Interface**: Responsive design with drag-and-drop file upload and real-time feedback
- **📊 Live Progress Tracking**: Real-time streaming with visual progress indicators and chunk counters
- **✏️ In-Browser Document Editing**: Edit translated content before final download with live preview
- **⬇️ Multiple Download Options**: PDF, DOCX, and TXT formats with professional formatting
- **📱 Mobile Responsive**: Optimized for desktop, tablet, and mobile devices with touch-friendly interface
- **🎯 Professional UI**: PNB Housing Finance branding with modern design elements and animations

### Enterprise Features
- **☁️ AWS S3 Integration**: Automatic file storage and management with metadata and background uploads
- **📝 Production Logging**: Optimized logging for EC2 deployment with essential error tracking only
- **🔍 Health Monitoring**: Built-in health checks and S3 connectivity status endpoints
- **🔄 Error Recovery**: Retry logic with exponential backoff for API failures and streaming resilience
- **⚡ Performance Optimization**: Streaming translation (15-40s), instant document generation (<2s), memory optimized

## Prerequisites

- Python 3.11+
- AWS CLI configured with Bedrock access
- Environment variables:
  - `MODEL_ID` (optional): Claude model ID (default: `us.anthropic.claude-sonnet-4-20250514-v1:0`)
  - `BUCKET_NAME` (optional): S3 bucket for file storage

## Quick Start

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure AWS credentials:**
   ```bash
   aws configure
   # Ensure your credentials have Bedrock access
   ```

3. **Set environment variables:**
   ```bash
   export MODEL_ID="global.anthropic.claude-opus-4-5-20251101-v1:0"
   export BUCKET_NAME="pnb-poc-docs"
   ```

4. **Run the service:**
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Access the web interface:**
   Open http://localhost:8000 in your browser

### Docker Deployment

1. **Build the container:**
   ```bash
   docker build -t pdf-translator .
   ```

2. **Run with environment variables:**
   ```bash
   docker run -p 8000:8000 \
     -e MODEL_ID="us.anthropic.claude-sonnet-4-20250514-v1:0" \
     -e BUCKET_NAME="your-bucket" \
     -e AWS_ACCESS_KEY_ID="your-key" \
     -e AWS_SECRET_ACCESS_KEY="your-secret" \
     -e AWS_DEFAULT_REGION="us-east-1" \
     pdf-translator
   ```

## API Usage

### Web Interface
Navigate to `http://localhost:8000` for the complete web application featuring:
- **File Upload**: Drag-and-drop interface with visual feedback and file validation
- **Language Selection**: Bidirectional translation (English ↔ Hindi) with visual indicators
- **Progress Tracking**: Real-time progress with step-by-step processing indicators
- **Document Preview**: Formatted preview of translated content with editing capabilities
- **Multiple Downloads**: PDF, DOCX, and TXT formats with professional templates
- **Responsive Design**: Mobile-optimized interface with PNB Housing Finance branding

### REST API

#### Streaming Translation Endpoint: `POST /translate-stream` (Recommended)

**Real-time streaming translation with Server-Sent Events for live feedback:**

**Request Body (JSON):**
```json
{
  "body": "base64_encoded_pdf_data",
  "target_lang": "hi",
  "template_choice": "simplified"
}
```

**Response (Server-Sent Events):**
```
data: {"type": "start", "document_id": "stream_1234567890", "file_size_mb": 2.54, "target_lang": "hi", "status": "starting"}

data: {"type": "chunk", "chunk": "# PNB Housing Finance Limited", "progress": 25, "chunk_count": 1, "status": "translating"}

data: {"type": "chunk", "chunk": "\n\n**पंजीकृत कार्यालय:**", "progress": 50, "chunk_count": 2, "status": "translating"}

data: {"type": "final", "success": true, "document_id": "stream_1234567890", "detected_language": "English", "target_language": "Hindi", "translated_document": "complete_translated_text", "processing_time": 25.67, "message": "Document translated successfully", "status": "complete"}
```

**Event Types:**
- `start`: Translation begins with document metadata
- `chunk`: Real-time translation chunks as they're generated
- `final`: Complete translation with metadata and statistics
- `error`: Error information if translation fails
- `retry`: Retry attempt information

#### Translation Endpoint: `POST /translate` (Legacy)

**Request Body (JSON):**
```json
{
  "body": "base64_encoded_pdf_data",
  "target_lang": "hi",
  "template_choice": "simplified"
}
```

**Parameters:**
- `body`: Base64 encoded PDF file data (max 15MB)
- `target_lang`: Target language (`"hi"` for Hindi, `"en"` for English)
- `template_choice`: Template type (currently only `"simplified"`)

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

#### Document Generation Endpoint: `POST /download`

**Request Body (JSON):**
```json
{
  "translated_text": "document_content",
  "source_lang": "English",
  "target_lang": "Hindi",
  "format": "pdf"
}
```

**Parameters:**
- `translated_text`: The translated document content
- `source_lang`: Source language name
- `target_lang`: Target language name
- `format`: Output format (`"pdf"`, `"docx"`, or `"txt"`)

**Response:**
- Content-Type: Varies by format (application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, text/plain)
- Binary document data for download

#### Additional Endpoints
- `GET /` - Serves the web interface
- `GET /health` - Service health check with configuration details
- `GET /s3-status` - S3 connectivity and file count status
- `POST /test-s3` - S3 upload functionality test

**Example with curl:**
```bash
# Convert PDF to base64 first
base64_data=$(base64 -i sample.pdf)

# Send translation request (returns JSON with translated text)
curl -X POST "http://localhost:8000/translate" \
  -H "Content-Type: application/json" \
  -d "{
    \"body\": \"$base64_data\",
    \"target_lang\": \"hi\",
    \"template_choice\": \"simplified\"
  }" > translation_result.json

# Extract translated text and generate PDF
translated_text=$(cat translation_result.json | jq -r '.translated_document')
curl -X POST "http://localhost:8000/download" \
  -H "Content-Type: application/json" \
  -d "{
    \"translated_text\": \"$translated_text\",
    \"source_lang\": \"English\",
    \"target_lang\": \"Hindi\",
    \"format\": \"pdf\"
  }" \
  --output professional_translation.pdf
```

## Document Processing Capabilities

### Structure Preservation
The service intelligently extracts and preserves:
- **Document hierarchy**: Main titles, section headings (# ## ###), and subheadings
- **Content formatting**: Paragraphs, bullet points, numbered lists
- **Tables**: Headers, rows, and data with proper formatting
- **Text emphasis**: Bold text (**text**) and other formatting markers
- **Document metadata**: Source/target languages, processing information

### Professional Templates

#### PDF Generation (ReportLab)
- **Page Format**: A4 with professional margins (72pt standard)
- **Fonts**: Automatic Hindi font detection (Noto Sans/DejaVu Sans/Arial fallback)
- **Branding**: PNB Housing Finance header with company logo placement
- **Color Scheme**: Primary blue (#1e40af), secondary gray (#374151)
- **Tables**: Professional grid styling with alternating row colors and borders
- **Footer**: Confidentiality notice with automatic page numbering

#### DOCX Generation (python-docx)
- **Margins**: 1.0 inch on all sides for professional appearance
- **Headers**: Company branding in document header section
- **Metadata Table**: Translation information with processing details
- **Styling**: Professional font hierarchy with proper spacing
- **Tables**: Grid format with bold headers and consistent spacing
- **Footer**: Confidentiality notice and service attribution

#### TXT Generation
- **Header**: Professional document header with metadata
- **Content**: Clean text formatting with proper line breaks
- **Footer**: Confidentiality notice and generation timestamp

## Error Handling

The service handles:
- Invalid PDF files
- File size limits (15MB max)
- Claude API failures
- JSON parsing errors
- PDF generation issues

## Performance

- **Translation**: 15-40 seconds (typical documents)
- **PDF Generation**: <2 seconds
- **File Size Limit**: 15MB maximum
- **Supported Formats**: PDF (text-based and scanned)

## Troubleshooting

### Common Issues

1. **Font rendering issues (Hindi text):**
   ```bash
   # Install Hindi fonts (Ubuntu/Debian)
   sudo apt-get install fonts-noto-devanagari fonts-dejavu-core
   
   # macOS (install via Homebrew)
   brew install --cask font-noto-sans-devanagari
   
   # Verify font installation
   python -c "from reportlab.pdfbase import pdfmetrics; print('Fonts available:', pdfmetrics.getRegisteredFontNames())"
   ```

2. **AWS Bedrock access issues:**
   ```bash
   # Test Bedrock connectivity
   aws bedrock list-foundation-models --region us-east-1
   
   # Verify Claude 4.5 Opus access
   aws bedrock get-foundation-model --model-identifier global.anthropic.claude-opus-4-5-20251101-v1:0
   
   # Check IAM permissions for Bedrock
   aws iam get-user
   ```

3. **S3 connectivity problems:**
   ```bash
   # Test S3 access
   aws s3 ls s3://pnb-poc-docs/
   
   # Create bucket if needed
   aws s3 mb s3://your-bucket-name
   
   # Set bucket permissions
   aws s3api put-bucket-policy --bucket your-bucket-name --policy file://bucket-policy.json
   ```

4. **Large file processing:**
   - Ensure files are under 15MB limit
   - Check available memory (minimum 2GB recommended)
   - Monitor processing time (typical: 15-40 seconds)
   - Use health endpoints to monitor system status

5. **Docker deployment issues:**
   ```bash
   # Check container logs
   docker logs pdf-translator
   
   # Verify environment variables
   docker exec pdf-translator env | grep -E "(BUCKET_NAME|MODEL_ID|AWS_)"
   
   # Test container health
   docker exec pdf-translator curl http://localhost:8000/health
   ```

### Development & Testing

**Test the complete workflow:**
```bash
# Test translation endpoint
python -c "
import requests
import base64
import json

# Load and encode PDF
with open('sample.pdf', 'rb') as f:
    pdf_data = base64.b64encode(f.read()).decode()

# Translate document
response = requests.post('http://localhost:8000/translate', json={
    'body': pdf_data,
    'target_lang': 'hi',
    'template_choice': 'simplified'
})

result = response.json()
print(f'Translation completed in {result[\"processing_time\"]:.2f}s')

# Generate PDF
pdf_response = requests.post('http://localhost:8000/download', json={
    'translated_text': result['translated_document'],
    'source_lang': result['detected_language'],
    'target_lang': result['target_language'],
    'format': 'pdf'
})

with open('professional_translation.pdf', 'wb') as f:
    f.write(pdf_response.content)

print('Professional PDF generated successfully!')
"
```

**Test health endpoints:**
```bash
# Check service health
curl http://localhost:8000/health

# Check S3 connectivity
curl http://localhost:8000/s3-status

# Test S3 upload functionality
curl -X POST http://localhost:8000/test-s3
```

## Recent Enhancements (v2.0)

### 🔄 Real-Time Streaming Translation
- **Server-Sent Events**: Live translation streaming with immediate feedback as text is generated
- **Progress Tracking**: Real-time progress indicators with chunk counters and character counts
- **Streaming Resilience**: Robust error handling and retry logic for streaming connections
- **Duplicate Prevention**: Fixed retry loop issues that caused duplicate processing

### 🤖 AI Processing Improvements
- **Enhanced Claude Prompts**: Optimized prompts for complete document translation with structure preservation
- **Increased Token Limits**: Raised to 64,000 tokens for comprehensive document processing
- **Advanced Post-Processing**: Automatic cleanup of OCR artifacts, empty sections, and formatting normalization
- **Language Detection**: Automatic source language detection from document content
- **Model Optimization**: Switched to Claude 4.5 Sonnet for improved performance

### 🎨 User Experience Enhancements
- **Real-Time Translation Display**: Live streaming text appears as it's translated
- **Modern Web Interface**: Complete redesign with PNB Housing Finance branding and animations
- **Progressive Enhancement**: Streaming with fallback to traditional translation
- **In-Browser Editing**: Edit translated content before final download with live preview
- **Multiple Format Support**: PDF, DOCX, and TXT output options with professional templates
- **Mobile Responsive**: Fully optimized for desktop, tablet, and mobile devices with touch gestures
- **Document Statistics**: Live word count, character count, and processing time display

### 🏢 Enterprise Features
- **Production Logging**: Optimized logging for EC2 deployment with minimal overhead
- **AWS S3 Integration**: Background file storage with metadata and audit trails
- **Health Monitoring**: Built-in health checks and S3 connectivity status endpoints
- **Error Recovery**: Exponential backoff retry logic for API failures and streaming resilience
- **Professional Templates**: Branded document templates with consistent styling and Hindi font support

### ⚡ Performance Optimizations
- **Streaming Architecture**: Real-time translation delivery without waiting for completion
- **Memory Optimization**: Efficient handling of large documents and concurrent users
- **Background Processing**: Non-blocking S3 uploads and document generation
- **Timeout Management**: Configurable timeouts with graceful error handling
- **Font Management**: Automatic Hindi font detection and registration for proper rendering
- **Production Ready**: Commented debug logs, optimized for EC2 deployment

## Documentation

### Additional Resources
- **[API Documentation](API_DOCUMENTATION.md)**: Comprehensive API reference with examples
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)**: Production deployment instructions for various environments
- **[Steering Files](.kiro/steering/)**: Project guidelines and technical specifications
  - [Product Overview](.kiro/steering/product.md): Business requirements and value proposition
  - [Technical Stack](.kiro/steering/tech.md): Technology choices and implementation details
  - [Project Structure](.kiro/steering/structure.md): Architecture and file organization

### Project Structure
```
├── app.py                      # Main FastAPI application
├── index.html                  # Complete web interface
├── pdf_generator.py            # ReportLab PDF generation
├── docx_generator.py           # python-docx Word generation
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container configuration
├── README.md                   # This file
├── API_DOCUMENTATION.md        # Complete API reference
├── DEPLOYMENT_GUIDE.md         # Production deployment guide
└── .kiro/steering/             # Project documentation
    ├── product.md              # Product overview and requirements
    ├── tech.md                 # Technology stack and build system
    └── structure.md            # Project structure and organization
```

## License

MIT License - see LICENSE file for details.

## Support

For technical support or questions:
1. Check the [API Documentation](API_DOCUMENTATION.md) for usage examples
2. Review the [Deployment Guide](DEPLOYMENT_GUIDE.md) for setup issues
3. Examine the steering files in `.kiro/steering/` for project guidelines
4. Use the health endpoints (`/health`, `/s3-status`) for system diagnostics