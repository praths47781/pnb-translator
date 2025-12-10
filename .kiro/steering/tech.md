# Technology Stack & Build System

## Core Technologies
- **Backend Framework**: FastAPI (Python 3.11)
- **AI/ML Service**: AWS Bedrock Runtime SDK (boto3) with Claude 4.5
- **PDF Processing**: WeasyPrint for HTML-to-PDF conversion
- **Template Engine**: Jinja2 for HTML template rendering
- **Containerization**: Docker with system dependencies

## Key Dependencies
```
fastapi
boto3 (AWS Bedrock Runtime SDK)
jinja2
weasyprint
python-multipart (for file uploads)
```

## AWS Bedrock Integration
- Use `invoke_model` with Claude 4.5
- Pass PDF bytes as body with `contentType: application/pdf`
- Extract structured JSON responses using regex validation
- Handle translation between English and Hindi

## Common Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Test API endpoint (JSON body with base64 file)
curl -X POST "http://localhost:8000/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "body": "base64_encoded_pdf_data",
    "target_lang": "hi",
    "template_choice": "simplified"
  }'
```

### Environment Variables
```bash
export BUCKET_NAME="your-bucket-name"
export MODEL_ID="us.anthropic.claude-sonnet-4-20250514-v1:0"
# AWS credentials should be configured via AWS CLI
```

### Docker
```bash
# Build container
docker build -t pdf-translator .

# Run container with environment variables
docker run -p 8000:8000 \
  -e BUCKET_NAME="your-bucket" \
  -e MODEL_ID="us.anthropic.claude-sonnet-4-20250514-v1:0" \
  pdf-translator
```

## Performance Requirements
- PDF extraction + translation: 15-40 seconds
- PDF rendering: Under 2 seconds
- File size limit: 15MB maximum

## Error Handling Priorities
1. Claude JSON parsing failures
2. Corrupted PDF files
3. Missing document sections
4. Empty or malformed tables