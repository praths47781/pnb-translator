# Technology Stack & Build System

## Core Technologies
- **Backend Framework**: FastAPI (Python 3.11) with comprehensive logging
- **AI/ML Service**: AWS Bedrock Runtime SDK (boto3) with Claude 4.5 Opus
- **PDF Generation**: ReportLab for professional PDF creation
- **DOCX Generation**: python-docx for Word document creation
- **Cloud Storage**: AWS S3 for file management and archival
- **Containerization**: Docker with system dependencies for fonts

## Key Dependencies
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
boto3==1.34.0
pydantic==2.5.0
python-docx==1.1.0
reportlab==4.0.7
```

## AWS Integration Architecture
- **Bedrock Runtime**: `invoke_model` with Claude 4.5 Opus for document processing
- **S3 Storage**: File archival in input/ and output/ folders with metadata
- **Document Processing**: PDF bytes passed directly to Claude with document context
- **Response Handling**: Raw text extraction with post-processing cleanup
- **Retry Logic**: Exponential backoff for API failures and timeout handling
- **Regional Configuration**: Multi-region support with configurable endpoints

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
export BUCKET_NAME="pnb-poc-docs"
export MODEL_ID="global.anthropic.claude-opus-4-5-20251101-v1:0"
# AWS credentials should be configured via AWS CLI or environment variables
```

### Docker
```bash
# Build container
docker build -t pdf-translator .

# Run container with environment variables
docker run -p 8000:8000 \
  -e BUCKET_NAME="pnb-poc-docs" \
  -e MODEL_ID="global.anthropic.claude-opus-4-5-20251101-v1:0" \
  -e AWS_ACCESS_KEY_ID="your-key" \
  -e AWS_SECRET_ACCESS_KEY="your-secret" \
  -e AWS_DEFAULT_REGION="us-east-1" \
  pdf-translator

# Access the web interface
open http://localhost:8000
```

## Performance Requirements
- **Translation Processing**: 15-40 seconds for typical documents
- **Document Generation**: Under 2 seconds for PDF/DOCX creation
- **File Size Limit**: 15MB maximum per upload
- **Concurrent Processing**: Multiple simultaneous translations supported
- **Memory Usage**: Optimized for cloud deployment environments
- **API Timeout**: 5-minute timeout for Bedrock calls with retry logic

## Error Handling & Monitoring
1. **Bedrock API Failures**: Exponential backoff retry with detailed logging
2. **File Processing Errors**: Size validation, format verification, corruption detection
3. **S3 Integration Issues**: Graceful degradation when storage is unavailable
4. **Document Generation Failures**: Fallback options and user-friendly error messages
5. **Font and Encoding Issues**: Automatic font detection and Unicode handling
6. **Network Timeouts**: Configurable timeouts with progress feedback

## Logging & Observability
- **Structured Logging**: JSON-formatted logs with request IDs and timestamps
- **Performance Metrics**: Processing time tracking and performance analytics
- **Error Tracking**: Comprehensive error logging with stack traces
- **Health Monitoring**: Built-in health checks and status endpoints
- **Audit Trail**: Complete request/response logging for compliance