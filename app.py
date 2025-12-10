import boto3
import base64
import json
import os
import re
import logging
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from botocore.config import Config
from docx_generator import generate_docx_from_translation
from pdf_generator import generate_pdf_from_translation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pdf_translator.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="PDF Translation Service", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AWS clients with extended timeout
logger.info("Initializing AWS clients...")
try:
    config = Config(
        read_timeout=300,  # 5 minutes
        connect_timeout=60,  # 1 minute
        retries={
            'max_attempts': 3,
            'mode': 'adaptive'
        }
    )
    
    bedrock = boto3.client('bedrock-runtime', config=config)
    s3_client = boto3.client('s3', config=config)
    logger.info("✅ AWS Bedrock client initialized successfully with extended timeout (5min)")
    logger.info("✅ AWS S3 client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize AWS clients: {str(e)}")
    raise

# Environment variables
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'pnb-poc-docs')
MODEL_ID = os.environ.get('MODEL_ID', 'global.anthropic.claude-opus-4-5-20251101-v1:0')

logger.info(f"🔧 Configuration loaded:")
logger.info(f"   - Bucket: {BUCKET_NAME}")
logger.info(f"   - Model ID: {MODEL_ID}")
logger.info(f"   - AWS Region: {bedrock.meta.region_name}")

# Test Bedrock connectivity at startup
try:
    logger.info("🔍 Testing Bedrock connectivity...")
    bedrock_client = boto3.client('bedrock', config=config)
    bedrock_client.list_foundation_models()
    logger.info("✅ Bedrock connectivity test passed")
except Exception as e:
    logger.warning(f"⚠️  Bedrock connectivity test failed: {str(e)}")
    logger.warning("   This may indicate AWS credentials or region issues, but runtime should still work")

# Request/Response models
class TranslateRequest(BaseModel):
    body: str  # base64 encoded PDF
    target_lang: str  # "hi" or "en"
    template_choice: Optional[str] = "simplified"

@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML file"""
    return FileResponse("index.html")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "PDF Translation Service",
        "version": "1.0.0",
        "bucket": BUCKET_NAME,
        "model": MODEL_ID,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/s3-status")
async def s3_status():
    """Check S3 bucket status and file counts"""
    try:
        logger.info(f"🔍 Testing S3 connectivity to bucket: {BUCKET_NAME}")
        
        # Test bucket access
        try:
            s3_client.head_bucket(Bucket=BUCKET_NAME)
            logger.info(f"✅ S3 bucket access confirmed: {BUCKET_NAME}")
        except Exception as bucket_error:
            logger.error(f"❌ S3 bucket access failed: {str(bucket_error)}")
            return {
                "status": "bucket_access_denied",
                "bucket": BUCKET_NAME,
                "error": str(bucket_error),
                "timestamp": datetime.now().isoformat()
            }
        
        # List objects in input folder
        logger.info(f"📂 Listing objects in input/ folder...")
        input_response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix="input/",
            MaxKeys=1000
        )
        input_count = input_response.get('KeyCount', 0)
        logger.info(f"📊 Found {input_count} files in input/ folder")
        
        # List objects in output folder
        logger.info(f"📂 Listing objects in output/ folder...")
        output_response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix="output/",
            MaxKeys=1000
        )
        output_count = output_response.get('KeyCount', 0)
        logger.info(f"📊 Found {output_count} files in output/ folder")
        
        # Get recent files
        recent_files = []
        if 'Contents' in input_response:
            for obj in input_response['Contents'][:5]:  # Last 5 files
                recent_files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'modified': obj['LastModified'].isoformat()
                })
        
        return {
            "status": "connected",
            "bucket": BUCKET_NAME,
            "region": s3_client.meta.region_name,
            "input_files": input_count,
            "output_files": output_count,
            "recent_files": recent_files,
            "folders": {
                "input": f"s3://{BUCKET_NAME}/input/",
                "output": f"s3://{BUCKET_NAME}/output/"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ S3 status check failed: {str(e)}")
        logger.exception("📋 S3 Status Check Traceback:")
        return {
            "status": "error",
            "bucket": BUCKET_NAME,
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.now().isoformat()
        }

@app.post("/test-s3")
async def test_s3_upload():
    """Test S3 upload functionality with a small test file"""
    request_id = f"test_{int(time.time())}"
    
    try:
        # Create a small test file
        test_content = f"Test file created at {datetime.now().isoformat()}".encode('utf-8')
        test_file_name = f"test_file_{request_id}.txt"
        
        # Upload test file
        s3_url = upload_to_s3(
            file_content=test_content,
            file_name=test_file_name,
            folder="test",
            request_id=request_id,
            content_type="text/plain"
        )
        
        return {
            "status": "success",
            "message": "S3 upload test successful",
            "s3_url": s3_url,
            "file_size": len(test_content),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ S3 upload test failed: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

class DownloadRequest(BaseModel):
    translated_text: str
    source_lang: str = "English"
    target_lang: str = "Hindi"
    format: str = "pdf"  # pdf, docx, txt

@app.post("/download")
async def download_document(request: DownloadRequest):
    """Generate and download document in specified format"""
    request_id = f"download_{int(time.time())}"
    logger.info(f"📥 [{request_id}] Download request: {request.format.upper()} format")
    
    try:
        if request.format.lower() == "pdf":
            logger.info(f"🔄 [{request_id}] Generating PDF document...")
            doc_bytes = generate_pdf_from_translation(
                request.translated_text, 
                request.source_lang, 
                request.target_lang
            )
            logger.info(f"✅ [{request_id}] PDF generated successfully ({len(doc_bytes)} bytes)")
            
            # Save PDF to S3
            try:
                output_file_name = generate_file_name("translated_document", request_id, "pdf") + ".pdf"
                output_s3_url = upload_to_s3(
                    file_content=doc_bytes,
                    file_name=output_file_name,
                    folder="output",
                    request_id=request_id,
                    content_type="application/pdf"
                )
                logger.info(f"📁 [{request_id}] Output PDF saved to S3: {output_s3_url}")
            except Exception as e:
                logger.warning(f"⚠️  [{request_id}] Failed to save PDF to S3: {str(e)}")
                # Continue with download even if S3 upload fails
            
            return Response(
                content=doc_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": "attachment; filename=professional_translation.pdf",
                    "Content-Length": str(len(doc_bytes))
                }
            )
        
        elif request.format.lower() == "docx":
            logger.info(f"🔄 [{request_id}] Generating DOCX document...")
            doc_bytes = generate_docx_from_translation(
                request.translated_text,
                request.source_lang,
                request.target_lang
            )
            logger.info(f"✅ [{request_id}] DOCX generated successfully ({len(doc_bytes)} bytes)")
            
            # Save DOCX to S3
            output_s3_url = None
            try:
                logger.info(f"💾 [{request_id}] Attempting to save output DOCX to S3...")
                output_file_name = generate_file_name("translated_document", request_id, "docx") + ".docx"
                output_s3_url = upload_to_s3(
                    file_content=doc_bytes,
                    file_name=output_file_name,
                    folder="output",
                    request_id=request_id,
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                logger.info(f"📁 [{request_id}] ✅ Output DOCX saved to S3: {output_s3_url}")
            except Exception as e:
                logger.error(f"❌ [{request_id}] Failed to save DOCX to S3: {str(e)}")
                logger.error(f"📋 [{request_id}] S3 Error Details: {type(e).__name__}")
                logger.exception(f"📋 [{request_id}] S3 DOCX Upload Traceback:")
                # Continue with download even if S3 upload fails
            
            return Response(
                content=doc_bytes,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": "attachment; filename=professional_translation.docx",
                    "Content-Length": str(len(doc_bytes))
                }
            )
        
        elif request.format.lower() == "txt":
            logger.info(f"🔄 [{request_id}] Generating TXT document...")
            # Add professional header to TXT file
            txt_content = f"""PNB HOUSING FINANCE LTD.
PROFESSIONAL TRANSLATION SERVICE

Document: Professional Translation
Source Language: {request.source_lang}
Target Language: {request.target_lang}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*60}

{request.translated_text}

{'='*60}

CONFIDENTIAL DOCUMENT | PNB Housing Finance Ltd.
This document was generated using AI-powered professional translation technology.
"""
            
            txt_bytes = txt_content.encode('utf-8')
            logger.info(f"✅ [{request_id}] TXT generated successfully ({len(txt_bytes)} bytes)")
            
            return Response(
                content=txt_bytes,
                media_type="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": "attachment; filename=professional_translation.txt",
                    "Content-Length": str(len(txt_bytes))
                }
            )
        
        else:
            logger.error(f"❌ [{request_id}] Unsupported format: {request.format}")
            raise HTTPException(status_code=400, detail="Unsupported format. Use 'pdf', 'docx', or 'txt'")
            
    except Exception as e:
        logger.error(f"💥 [{request_id}] Download error: {str(e)}")
        logger.exception(f"📋 [{request_id}] Full traceback:")
        raise HTTPException(status_code=500, detail=f"Failed to generate {request.format.upper()} document: {str(e)}")

@app.post("/translate")
async def translate_pdf(request: TranslateRequest):
    """Translate PDF document using Claude 4.5 and return translated text"""
    start_time = time.time()
    request_id = f"req_{int(time.time())}"
    
    logger.info(f"🚀 [{request_id}] Starting PDF translation request")
    logger.info(f"📋 [{request_id}] Target language: {request.target_lang}")
    
    try:
        # Decode base64 PDF
        logger.info(f"🔄 [{request_id}] Decoding base64 PDF data...")
        try:
            pdf_bytes = base64.b64decode(request.body)
            logger.info(f"✅ [{request_id}] PDF decoded successfully")
        except Exception as e:
            logger.error(f"❌ [{request_id}] Failed to decode base64 PDF: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid base64 PDF data")
        
        # Validate file size (15MB limit)
        file_size_mb = len(pdf_bytes) / (1024 * 1024)
        logger.info(f"📏 [{request_id}] PDF file size: {file_size_mb:.2f} MB")
        
        if len(pdf_bytes) > 15 * 1024 * 1024:
            logger.error(f"❌ [{request_id}] File size exceeds 15MB limit: {file_size_mb:.2f} MB")
            raise HTTPException(status_code=400, detail="File size exceeds 15MB limit")
        
        # Save input PDF to S3
        input_s3_url = None
        try:
            logger.info(f"💾 [{request_id}] Attempting to save input PDF to S3...")
            input_file_name = generate_file_name("input_document", request_id) + ".pdf"
            input_s3_url = upload_to_s3(
                file_content=pdf_bytes,
                file_name=input_file_name,
                folder="input",
                request_id=request_id,
                content_type="application/pdf"
            )
            logger.info(f"📁 [{request_id}] ✅ Input PDF saved to S3: {input_s3_url}")
        except Exception as e:
            logger.error(f"❌ [{request_id}] Failed to save input PDF to S3: {str(e)}")
            logger.error(f"📋 [{request_id}] S3 Error Details: {type(e).__name__}")
            logger.exception(f"📋 [{request_id}] S3 Input Upload Traceback:")
            # Continue processing even if S3 upload fails
        
        # Extract and translate content using Claude 4.5
        logger.info(f"🤖 [{request_id}] Starting AI extraction and translation...")
        extraction_start = time.time()
        translated_document = await extract_and_translate_pdf(pdf_bytes, request.target_lang, request_id)
        extraction_time = time.time() - extraction_start
        logger.info(f"✅ [{request_id}] AI processing completed in {extraction_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"🎉 [{request_id}] Translation completed successfully!")
        logger.info(f"⏱️  [{request_id}] Total processing time: {total_time:.2f}s")
        
        # Detect languages
        detected_language = detect_language_from_content(translated_document)
        target_language = "Hindi" if request.target_lang == "hi" else "English"
        
        # Return JSON response with translated document
        return {
            "success": True,
            "document_id": request_id,
            "detected_language": detected_language,
            "target_language": target_language,
            "translated_document": translated_document,
            "processing_time": total_time,
            "message": "Document translated successfully"
        }
        
    except HTTPException as he:
        logger.error(f"❌ [{request_id}] HTTP Exception: {he.detail}")
        raise
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"💥 [{request_id}] Unexpected error after {total_time:.2f}s: {str(e)}")
        logger.exception(f"📋 [{request_id}] Full traceback:")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

async def extract_and_translate_pdf(pdf_bytes: bytes, target_lang: str, request_id: str) -> str:
    """Extract content from PDF and translate using Claude 4.5"""
    
    target_language = "Hindi" if target_lang == "hi" else "English"
    source_language = "English" if target_lang == "hi" else "Hindi"
    
    logger.info(f"🔧 [{request_id}] Preparing content for Claude 4.5...")
    logger.info(f"🌐 [{request_id}] Translation: {source_language} → {target_language}")
    
    # Prepare content for Claude
    prompt_text = f"""You are a professional document translator specializing in legal, financial, and official documents. Your task is to translate this PDF document from {source_language} to {target_language}.

CRITICAL TRANSLATION REQUIREMENTS:
1. COMPLETE TRANSLATION: Translate EVERY SINGLE WORD from the beginning to the absolute end of the document
2. NO TRUNCATION: Never stop mid-sentence, mid-paragraph, or mid-section - translate until the document is 100% complete
3. PRESERVE STRUCTURE: Maintain exact document hierarchy, headings, subheadings, and sections
4. MAINTAIN FORMATTING: Keep all bullet points, numbered lists, tables, and indentation exactly as they appear
5. PRESERVE LEGAL TERMS: Keep legal references, case numbers, dates, and official terminology accurate
6. PROFESSIONAL QUALITY: Use appropriate formal language and terminology for official documents
7. COMPLETE TABLES: Translate all table content including headers, rows, and footnotes
8. FINISH EVERYTHING: Ensure no content is left untranslated, including disclaimers, notes, and fine print

FORMATTING REQUIREMENTS:
- Use clear markdown formatting for structure:
  - # for main document title
  - ## for major sections (like "Terms and Conditions", "Important Information")
  - ### for subsections
  - **bold** for important terms, headings, and emphasis
  - Use proper numbered lists: 1. 2. 3. with clear spacing
  - Use bullet points: • for sub-items
- For tables, use pipe-separated format: | Column 1 | Column 2 | Column 3 |
- Use proper paragraph spacing with double line breaks between sections
- Preserve all original numbering, lettering (a, b, c), and indentation
- Remove any empty pages or unnecessary whitespace
- Ensure clean, readable formatting without scattered text

CONTENT PRESERVATION:
- Keep all numbers, dates, amounts, and percentages exactly as they appear
- Preserve proper nouns, company names, and legal entity names
- Maintain reference numbers, case citations, and official codes
- Keep addresses, contact information, and formal signatures unchanged
- Translate headers, footers, and all visible text content
- Include all disclaimers, notes, and fine print at the end

TRANSLATION COMPLETENESS CHECK:
- Ensure you have translated from the very first word to the very last word
- Include all footnotes, disclaimers, and legal notices
- Do not stop until you reach the absolute end of the document
- If the document has multiple pages, translate ALL pages completely
- Include any contact information, website URLs, or reference numbers

OUTPUT REQUIREMENTS:
- Start translation immediately without any preamble
- Translate the COMPLETE document from first word to last word
- End only when the entire document has been fully translated including all fine print
- Do not add any explanatory notes or comments
- Ensure clean, well-formatted output without empty sections
- Remove any OCR artifacts or scattered characters
- Ensure the translation flows naturally while maintaining accuracy
- CRITICAL: Do not stop until you have translated every single piece of text in the document

Begin the complete translation now and ensure you translate EVERYTHING:"""

    content_items = [
        {
            "type": "text",
            "text": prompt_text
        },
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.b64encode(pdf_bytes).decode('utf-8')
            }
        }
    ]
    
    # Prepare Bedrock payload with maximum tokens for complete translations
    prompt = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 12000,  # Maximum tokens for complete translations
        "temperature": 0.1,  # Lower temperature for more consistent translations
        "messages": [
            {
                "role": "user",
                "content": content_items
            }
        ]
    }
    
    # Retry logic for Bedrock API
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"📡 [{request_id}] Calling AWS Bedrock API (attempt {attempt + 1}/{max_retries})...")
            logger.info(f"🔧 [{request_id}] Model ID: {MODEL_ID}")
            logger.info(f"⏱️  [{request_id}] Timeout configured: 5 minutes")
            
            bedrock_start = time.time()
            response = bedrock.invoke_model(
                modelId=MODEL_ID,
                body=json.dumps(prompt),
                contentType='application/json',
                accept='application/json'
            )
            bedrock_time = time.time() - bedrock_start
            logger.info(f"✅ [{request_id}] Bedrock API call completed in {bedrock_time:.2f}s")
            break  # Success, exit retry loop
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [{request_id}] Bedrock API attempt {attempt + 1} failed: {error_msg}")
            
            if attempt == max_retries - 1:  # Last attempt
                if "timeout" in error_msg.lower():
                    logger.error(f"💥 [{request_id}] All attempts failed due to timeout.")
                    raise HTTPException(
                        status_code=504, 
                        detail="Request timed out. The document may be too large or complex."
                    )
                else:
                    logger.error(f"💥 [{request_id}] All Bedrock API attempts failed")
                    raise HTTPException(status_code=500, detail=f"Bedrock API error: {error_msg}")
            else:
                # Wait before retry (exponential backoff)
                wait_time = 2 ** attempt
                logger.info(f"⏳ [{request_id}] Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
    
    # Parse response
    try:
        logger.info(f"📥 [{request_id}] Parsing Bedrock response...")
        body_content = response['body']
        if hasattr(body_content, 'read'):
            body_text = body_content.read().decode('utf-8')
        else:
            body_text = str(body_content)
            
        logger.info(f"🔍 [{request_id}] Raw response length: {len(body_text)} characters")
        
        result = json.loads(body_text)
        translated_document = result['content'][0]['text']
        
        response_length = len(translated_document)
        logger.info(f"📄 [{request_id}] Received translated document ({response_length} characters)")
        
        # Check if translation seems complete (basic heuristic)
        if response_length < 100:
            logger.warning(f"⚠️  [{request_id}] Translation seems very short ({response_length} chars)")
        
        # Log first and last 100 characters for debugging
        if response_length > 200:
            logger.info(f"📝 [{request_id}] Translation preview:")
            logger.info(f"   Start: {translated_document[:100]}...")
            logger.info(f"   End: ...{translated_document[-100:]}")
        else:
            logger.info(f"📝 [{request_id}] Full translation: {translated_document}")
        
        # Post-process the translation to clean it up
        cleaned_document = post_process_translation(translated_document, request_id)
        
        return cleaned_document
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] Failed to parse Bedrock response: {str(e)}")
        logger.error(f"📋 [{request_id}] Raw response preview: {body_text[:500]}...")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")

def post_process_translation(text: str, request_id: str) -> str:
    """Clean up and format the translated document"""
    logger.info(f"🧹 [{request_id}] Post-processing translation...")
    
    # Remove excessive whitespace and empty lines
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # Remove scattered single characters or numbers on their own lines
    cleaned = re.sub(r'^\s*[0-9]\s*$', '', cleaned, flags=re.MULTILINE)
    
    # Remove lines with only special characters or whitespace
    cleaned = re.sub(r'^[\s\-_=|]+$', '', cleaned, flags=re.MULTILINE)
    
    # Clean up spacing around headers
    cleaned = re.sub(r'\n+(#{1,3}\s)', r'\n\n\1', cleaned)
    
    # Remove empty sections (lines with just "---" or similar)
    cleaned = re.sub(r'^[-=]{3,}$', '', cleaned, flags=re.MULTILINE)
    
    # Fix spacing issues
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # Remove any remaining OCR artifacts (single characters on their own lines)
    lines = cleaned.split('\n')
    filtered_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Skip lines that are just single characters, numbers, or short meaningless text
        if len(stripped) <= 2 and stripped.isdigit():
            continue
        if len(stripped) <= 1 and not stripped.isalnum():
            continue
        filtered_lines.append(line)
    
    cleaned = '\n'.join(filtered_lines)
    
    # Final cleanup
    cleaned = cleaned.strip()
    
    final_length = len(cleaned)
    logger.info(f"✅ [{request_id}] Post-processing complete ({final_length} characters)")
    
    return cleaned

def detect_language_from_content(text: str) -> str:
    """Detect the primary language of the text content"""
    # Simple language detection based on script
    hindi_chars = re.findall(r'[\u0900-\u097F]', text)
    english_chars = re.findall(r'[a-zA-Z]', text)
    
    # Determine primary language
    if len(hindi_chars) > len(english_chars):
        return "Hindi"
    else:
        return "English"

def upload_to_s3(file_content: bytes, file_name: str, folder: str, request_id: str, content_type: str = 'application/octet-stream') -> str:
    """Upload file to S3 bucket in specified folder"""
    try:
        # Create S3 key with folder structure
        s3_key = f"{folder}/{file_name}"
        
        logger.info(f"📤 [{request_id}] Starting S3 upload...")
        logger.info(f"📋 [{request_id}] S3 Details:")
        logger.info(f"   - Bucket: {BUCKET_NAME}")
        logger.info(f"   - Key: {s3_key}")
        logger.info(f"   - Content Type: {content_type}")
        logger.info(f"   - File Size: {len(file_content)} bytes")
        
        # Check S3 client configuration
        logger.info(f"🔧 [{request_id}] S3 Client Region: {s3_client.meta.region_name}")
        
        # Test S3 connectivity first
        logger.info(f"🔍 [{request_id}] Testing S3 bucket access...")
        try:
            s3_client.head_bucket(Bucket=BUCKET_NAME)
            logger.info(f"✅ [{request_id}] S3 bucket access confirmed")
        except Exception as bucket_error:
            logger.error(f"❌ [{request_id}] S3 bucket access failed: {str(bucket_error)}")
            raise Exception(f"S3 bucket access denied: {str(bucket_error)}")
        
        # Upload to S3
        logger.info(f"📤 [{request_id}] Executing S3 put_object...")
        response = s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
            Metadata={
                'request_id': request_id,
                'upload_timestamp': datetime.now().isoformat(),
                'service': 'pdf-translator',
                'file_size': str(len(file_content))
            }
        )
        
        # Log response details
        logger.info(f"📋 [{request_id}] S3 Upload Response:")
        logger.info(f"   - ETag: {response.get('ETag', 'N/A')}")
        logger.info(f"   - VersionId: {response.get('VersionId', 'N/A')}")
        
        # Generate S3 URL
        s3_url = f"s3://{BUCKET_NAME}/{s3_key}"
        https_url = f"https://{BUCKET_NAME}.s3.{s3_client.meta.region_name}.amazonaws.com/{s3_key}"
        
        logger.info(f"✅ [{request_id}] Successfully uploaded to S3!")
        logger.info(f"   - S3 URL: {s3_url}")
        logger.info(f"   - HTTPS URL: {https_url}")
        
        return s3_url
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] S3 upload failed with error: {str(e)}")
        logger.error(f"📋 [{request_id}] Error type: {type(e).__name__}")
        logger.exception(f"📋 [{request_id}] Full S3 upload traceback:")
        raise Exception(f"S3 upload failed: {str(e)}")

def generate_file_name(original_name: str, request_id: str, suffix: str = "") -> str:
    """Generate a unique file name for S3 storage"""
    # Clean the original name
    base_name = original_name.replace('.pdf', '').replace(' ', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if suffix:
        return f"{base_name}_{suffix}_{request_id}_{timestamp}"
    else:
        return f"{base_name}_{request_id}_{timestamp}"

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting PDF Translation Service...")
    logger.info("🌐 Server will be available at: http://localhost:8000")
    logger.info("📋 Ready to process PDF translations!")
    uvicorn.run(app, host="0.0.0.0", port=8000)