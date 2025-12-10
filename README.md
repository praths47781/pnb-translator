# PDF Translation Service

A FastAPI-based service that translates PDF documents using AWS Bedrock (Claude 4.5) and generates professionally formatted output PDFs.

## Features

- **AI-Powered Translation**: Uses Claude 4.5 for OCR extraction and English↔Hindi translation
- **Professional Templates**: Generates clean, formatted PDFs with consistent styling
- **Web Interface**: Integrated HTML frontend with drag-and-drop file upload
- **Document Structure Preservation**: Maintains headings, sections, and tables
- **Fast Processing**: 15-40 seconds for translation, <2 seconds for PDF generation

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
   export MODEL_ID="us.anthropic.claude-sonnet-4-20250514-v1:0"
   export BUCKET_NAME="your-bucket-name"  # Optional
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
Navigate to `http://localhost:8000` for the integrated web interface with:
- Drag-and-drop PDF upload
- Language selection (English/Hindi)
- Real-time progress tracking
- Automatic PDF download

### REST API

**Endpoint:** `POST /translate`

**Request Body (JSON):**
```json
{
  "body": "base64_encoded_pdf_data",
  "target_lang": "hi",
  "template_choice": "simplified"
}
```

**Parameters:**
- `body`: Base64 encoded PDF file data
- `target_lang`: Target language (`"hi"` for Hindi, `"en"` for English)
- `template_choice`: Template type (currently only `"simplified"`)

**Response:**
- Content-Type: `application/pdf`
- Binary PDF data for download

**Example with curl:**
```bash
# Convert PDF to base64 first
base64_data=$(base64 -i sample.pdf)

# Send translation request
curl -X POST "http://localhost:8000/translate" \
  -H "Content-Type: application/json" \
  -d "{
    \"body\": \"$base64_data\",
    \"target_lang\": \"hi\",
    \"template_choice\": \"simplified\"
  }" \
  --output translated_document.pdf
```

## Document Structure

The service extracts and preserves:
- **Document title and headers**
- **Section headings and content**
- **Tables with headers and data**
- **Footer information and notes**

## Template Specifications

- **Page Format**: A4 with professional margins
- **Fonts**: Noto Sans, DejaVu Sans, Arial fallback
- **Styling**: Clean, enterprise-friendly design
- **Tables**: Bordered with alternating row colors
- **Headers/Footers**: Automatic page numbering

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

1. **WeasyPrint font errors:**
   ```bash
   # Install additional fonts (Ubuntu/Debian)
   sudo apt-get install fonts-noto fonts-dejavu-core
   ```

2. **AWS Bedrock access denied:**
   ```bash
   # Ensure your AWS credentials have Bedrock permissions
   aws bedrock list-foundation-models --region us-east-1
   ```

3. **Large file processing:**
   - Ensure files are under 15MB
   - Check available memory for PDF processing

### Development

**Run tests:**
```bash
# Test the API endpoint
python -c "
import requests
import base64

with open('sample.pdf', 'rb') as f:
    pdf_data = base64.b64encode(f.read()).decode()

response = requests.post('http://localhost:8000/translate', json={
    'body': pdf_data,
    'target_lang': 'hi',
    'template_choice': 'simplified'
})

with open('output.pdf', 'wb') as f:
    f.write(response.content)
"
```

## License

MIT License - see LICENSE file for details.