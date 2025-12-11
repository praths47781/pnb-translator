import boto3
import base64
import json
import os
import re
import logging
import time
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from botocore.config import Config
from docx_generator import generate_docx_from_translation
from pdf_generator import generate_pdf_from_translation

# Configure logging (console only for EC2 deployment)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
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
# logger.info("Initializing AWS clients...")
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
    # logger.info("✅ AWS Bedrock client initialized successfully with extended timeout (5min)")
    # logger.info("✅ AWS S3 client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize AWS clients: {str(e)}")
    raise

# Environment variables
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'pnb-poc-docs')
MODEL_ID = os.environ.get('MODEL_ID', 'global.anthropic.claude-opus-4-5-20251101-v1:0')

# Supported models configuration
SUPPORTED_MODELS = {
    'claude-opus': 'global.anthropic.claude-opus-4-5-20251101-v1:0',
    'nova-2-lite': 'global.amazon.nova-2-lite-v1:0'  # Correct model ID from AWS console
}

# logger.info(f"🔧 Configuration loaded:")
# logger.info(f"   - Bucket: {BUCKET_NAME}")
# logger.info(f"   - Model ID: {MODEL_ID}")
# logger.info(f"   - AWS Region: {bedrock.meta.region_name}")

# Test Bedrock connectivity at startup
try:
    # logger.info("🔍 Testing Bedrock connectivity...")
    bedrock_client = boto3.client('bedrock', config=config)
    bedrock_client.list_foundation_models()
    # logger.info("✅ Bedrock connectivity test passed")
except Exception as e:
    logger.warning(f"⚠️  Bedrock connectivity test failed: {str(e)}")
    # logger.warning("   This may indicate AWS credentials or region issues, but runtime should still work")

# Request/Response models
class TranslateRequest(BaseModel):
    body: str  # base64 encoded PDF
    target_lang: str  # "hi" or "en"
    template_choice: Optional[str] = "simplified"
    model_choice: Optional[str] = "claude-opus"  # "claude-opus" or "nova-2-lite"

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
        "model": SUPPORTED_MODELS["claude-opus"],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/models")
async def get_available_models():
    """Get list of available AI models"""
    return {
        "models": [
            {
                "id": "claude-opus",
                "name": "Claude 4.5 Opus",
                "description": "Advanced reasoning and document analysis",
                "provider": "Anthropic",
                "model_id": SUPPORTED_MODELS["claude-opus"]
            },
            {
                "id": "nova-2-lite",
                "name": "Amazon Nova 2 Lite",
                "description": "Fast and efficient multimodal processing",
                "provider": "Amazon",
                "model_id": SUPPORTED_MODELS["nova-2-lite"]
            }
        ],
        "default": "claude-opus"
    }

@app.get("/s3-status")
async def s3_status():
    """Check S3 bucket status and file counts"""
    try:
        # logger.info(f"🔍 Testing S3 connectivity to bucket: {BUCKET_NAME}")
        
        # Test bucket access
        try:
            s3_client.head_bucket(Bucket=BUCKET_NAME)
            # logger.info(f"✅ S3 bucket access confirmed: {BUCKET_NAME}")
        except Exception as bucket_error:
            logger.error(f"❌ S3 bucket access failed: {str(bucket_error)}")
            return {
                "status": "bucket_access_denied",
                "bucket": BUCKET_NAME,
                "error": str(bucket_error),
                "timestamp": datetime.now().isoformat()
            }
        
        # List objects in input folder
        # logger.info(f"📂 Listing objects in input/ folder...")
        input_response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix="input/",
            MaxKeys=1000
        )
        input_count = input_response.get('KeyCount', 0)
        # logger.info(f"📊 Found {input_count} files in input/ folder")
        
        # List objects in output folder
        # logger.info(f"📂 Listing objects in output/ folder...")
        output_response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix="output/",
            MaxKeys=1000
        )
        output_count = output_response.get('KeyCount', 0)
        # logger.info(f"📊 Found {output_count} files in output/ folder")
        
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
        
        # Upload test file (synchronous since we need the URL for response)
        s3_url = upload_to_s3_sync(
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

@app.get("/test-stream")
async def test_streaming():
    """Test streaming functionality"""
    async def generate_test_stream():
        for i in range(5):
            yield f"data: {json.dumps({'chunk': f'Test chunk {i+1}', 'count': i+1})}\n\n"
            await asyncio.sleep(1)
        yield f"data: {json.dumps({'type': 'final', 'message': 'Test complete'})}\n\n"
    
    return StreamingResponse(
        generate_test_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

@app.get("/list-available-models")
async def list_available_models():
    """List all available Bedrock models in the current region"""
    try:
        bedrock_client = boto3.client('bedrock', config=config)
        response = bedrock_client.list_foundation_models()
        
        models = []
        for model in response.get('modelSummaries', []):
            models.append({
                'modelId': model.get('modelId'),
                'modelName': model.get('modelName'),
                'providerName': model.get('providerName'),
                'inputModalities': model.get('inputModalities', []),
                'outputModalities': model.get('outputModalities', []),
                'responseStreamingSupported': model.get('responseStreamingSupported', False)
            })
        
        # Filter for Nova models specifically
        nova_models = [m for m in models if 'nova' in m['modelId'].lower()]
        
        return {
            "status": "success",
            "region": bedrock_client.meta.region_name,
            "total_models": len(models),
            "nova_models": nova_models,
            "all_models": models[:10],  # First 10 for reference
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to list models: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/test-model")
async def test_model_support(request: dict):
    """Test model connectivity and basic functionality"""
    model_choice = request.get('model_choice', 'claude-opus')
    
    if model_choice not in SUPPORTED_MODELS:
        return {
            "status": "error",
            "error": f"Unsupported model: {model_choice}",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        # Simple test prompt
        test_text = "Hello, this is a test."
        
        if model_choice == "nova-2-lite":
            # Test Nova model
            conversation = [
                {
                    "role": "user",
                    "content": [{"text": f"Translate this to Hindi: {test_text}"}]
                }
            ]
            
            response = bedrock.converse(
                modelId=SUPPORTED_MODELS[model_choice],
                messages=conversation,
                inferenceConfig={
                    "maxTokens": 100,
                    "temperature": 0.1
                }
            )
            
            result_text = response['output']['message']['content'][0]['text']
            
        else:  # Claude model
            prompt = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "temperature": 0.1,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": f"Translate this to Hindi: {test_text}"}]
                    }
                ]
            }
            
            response = bedrock.invoke_model(
                modelId=SUPPORTED_MODELS[model_choice],
                body=json.dumps(prompt),
                contentType='application/json',
                accept='application/json'
            )
            
            body_content = response['body']
            if hasattr(body_content, 'read'):
                body_text = body_content.read().decode('utf-8')
            else:
                body_text = str(body_content)
            
            result = json.loads(body_text)
            result_text = result['content'][0]['text']
        
        return {
            "status": "success",
            "model": model_choice,
            "model_id": SUPPORTED_MODELS[model_choice],
            "test_input": test_text,
            "test_output": result_text,
            "message": f"{model_choice} model is working correctly",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Model test failed for {model_choice}: {str(e)}")
        return {
            "status": "error",
            "model": model_choice,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/test-fonts")
async def test_font_support():
    """Test Hindi font support and availability"""
    try:
        from pdf_generator import register_hindi_fonts, check_hindi_text
        
        # Test font registration
        selected_font = register_hindi_fonts()
        
        # Test Hindi text detection
        hindi_sample = "हिंदी परीक्षण"
        has_hindi = check_hindi_text(hindi_sample)
        
        # Check available fonts
        import os
        font_paths = [
            '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
        ]
        
        available_fonts = []
        for path in font_paths:
            if os.path.exists(path):
                available_fonts.append(path)
        
        return {
            "status": "success",
            "selected_font": selected_font,
            "hindi_detection": {
                "sample_text": hindi_sample,
                "contains_hindi": has_hindi
            },
            "available_font_files": available_fonts,
            "font_support": "good" if selected_font != "Helvetica" else "limited",
            "recommendation": "Install fonts-noto-devanagari for better Hindi support" if selected_font == "Helvetica" else "Font support is adequate",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Font test failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

class DownloadRequest(BaseModel):
    translated_text: str
    source_lang: str = "English"
    target_lang: str = "Hindi"
    format: str = "pdf"  # pdf, docx, txt
    document_id: Optional[str] = None  # For tracking/logging

@app.post("/download")
async def download_document(request: DownloadRequest, background_tasks: BackgroundTasks):
    """Generate and download document in specified format - on-demand generation"""
    # Use provided document_id or generate new one
    request_id = request.document_id or f"download_{int(time.time())}"
    generation_start = time.time()
    
    try:
        if request.format.lower() == "pdf":
            # Generate PDF on-demand (2-3 seconds)
            doc_bytes = generate_pdf_from_translation(
                request.translated_text, 
                request.source_lang, 
                request.target_lang
            )
            
            # Schedule PDF upload to S3 as background task (non-blocking)
            output_file_name = generate_file_name("translated_document", request_id, "pdf") + ".pdf"
            background_tasks.add_task(
                upload_to_s3_background,
                file_content=doc_bytes,
                file_name=output_file_name,
                folder="output",
                request_id=request_id,
                content_type="application/pdf"
            )
            
            generation_time = time.time() - generation_start
            
            return Response(
                content=doc_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": "attachment; filename=professional_translation.pdf",
                    "Content-Length": str(len(doc_bytes)),
                    "X-Generation-Time": str(round(generation_time, 2))
                }
            )
        
        elif request.format.lower() == "docx":
            # Generate DOCX on-demand (1-2 seconds)
            doc_bytes = generate_docx_from_translation(
                request.translated_text,
                request.source_lang,
                request.target_lang
            )
            
            # Schedule DOCX upload to S3 as background task (non-blocking)
            output_file_name = generate_file_name("translated_document", request_id, "docx") + ".docx"
            background_tasks.add_task(
                upload_to_s3_background,
                file_content=doc_bytes,
                file_name=output_file_name,
                folder="output",
                request_id=request_id,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
            generation_time = time.time() - generation_start
            
            return Response(
                content=doc_bytes,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": "attachment; filename=professional_translation.docx",
                    "Content-Length": str(len(doc_bytes)),
                    "X-Generation-Time": str(round(generation_time, 2))
                }
            )
        
        elif request.format.lower() == "txt":
            # Generate TXT immediately (instant)
            txt_content = f"""PNB HOUSING FINANCE LTD.

{request.translated_text}

CONFIDENTIAL DOCUMENT | PNB Housing Finance Ltd.
"""
            
            txt_bytes = txt_content.encode('utf-8')
            generation_time = time.time() - generation_start
            
            return Response(
                content=txt_bytes,
                media_type="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": "attachment; filename=professional_translation.txt",
                    "Content-Length": str(len(txt_bytes)),
                    "X-Generation-Time": str(round(generation_time, 2))
                }
            )
        
        else:
            logger.error(f"❌ [{request_id}] Unsupported format: {request.format}")
            raise HTTPException(status_code=400, detail="Unsupported format. Use 'pdf', 'docx', or 'txt'")
            
    except Exception as e:
        logger.error(f"💥 [{request_id}] Download error: {str(e)}")
        logger.exception(f"📋 [{request_id}] Full traceback:")
        raise HTTPException(status_code=500, detail=f"Failed to generate {request.format.upper()} document: {str(e)}")

@app.post("/translate-stream")
async def translate_pdf_stream(request: TranslateRequest, background_tasks: BackgroundTasks):
    """Stream PDF translation with real-time progress updates"""
    start_time = time.time()
    request_id = f"stream_{int(time.time())}"
    
    async def generate_stream():
        try:
            # print(f"\n🔴 [BACKEND] NEW REQUEST RECEIVED - ID: {request_id}")
            # print(f"🔴 [BACKEND] Target language: {request.target_lang}")
            
            # Decode base64 PDF
            try:
                pdf_bytes = base64.b64decode(request.body)
                # print(f"🔴 [BACKEND] File size: {len(pdf_bytes) / (1024*1024):.2f} MB")
            except Exception as e:
                # print(f"❌ [BACKEND] Failed to decode PDF - ID: {request_id}")
                yield f"data: {json.dumps({'type': 'error', 'error': 'Invalid base64 PDF data', 'status': 'error'})}\n\n"
                return
            
            # Validate file size (15MB limit)
            file_size_mb = len(pdf_bytes) / (1024 * 1024)
            
            if len(pdf_bytes) > 15 * 1024 * 1024:
                yield f"data: {json.dumps({'type': 'error', 'error': f'File size exceeds 15MB limit: {file_size_mb:.2f} MB', 'status': 'error'})}\n\n"
                return
            
            # Send initial status
            # print(f"🟢 [BACKEND] STARTING PROCESSING - ID: {request_id}")
            yield f"data: {json.dumps({'type': 'start', 'document_id': request_id, 'file_size_mb': round(file_size_mb, 2), 'target_lang': request.target_lang, 'status': 'starting'})}\n\n"
            
            # Schedule input PDF upload to S3 as background task
            input_file_name = generate_file_name("input_document", request_id) + ".pdf"
            background_tasks.add_task(
                upload_to_s3_background,
                file_content=pdf_bytes,
                file_name=input_file_name,
                folder="input",
                request_id=request_id,
                content_type="application/pdf"
            )
            
            # Stream translation from selected model
            model_choice = request.model_choice or "claude-opus"
            if model_choice not in SUPPORTED_MODELS:
                yield f"data: {json.dumps({'type': 'error', 'error': f'Unsupported model: {model_choice}', 'status': 'error'})}\n\n"
                return
            
            # Choose streaming function based on model
            if model_choice == "nova-2-lite":
                stream_function = nova_stream_translation
            else:  # claude-opus (default)
                stream_function = bedrock_stream_translation
            
            full_translation = ""
            async for chunk_data in stream_function(pdf_bytes, request.target_lang, request_id):
                if chunk_data['type'] == 'chunk':
                    full_translation += chunk_data['chunk']
                
                # Send chunk to frontend
                yield f"data: {json.dumps(chunk_data)}\n\n"
                
                # No more 'complete' events - streaming ends naturally when generator finishes
            
            # Post-process the translation
            cleaned_document = post_process_translation(full_translation, request_id)
            
            # Detect languages
            detected_language = detect_language_from_content(cleaned_document)
            target_language = "Hindi" if request.target_lang == "hi" else "English"
            
            total_time = time.time() - start_time
            
            # Send final result
            # print(f"🟢 [BACKEND] PROCESSING COMPLETE - ID: {request_id}, Time: {total_time:.2f}s")
            final_result = {
                'type': 'final',
                'success': True,
                'document_id': request_id,
                'detected_language': detected_language,
                'target_language': target_language,
                'translated_document': cleaned_document,
                'processing_time': round(total_time, 2),
                'message': "Document translated successfully",
                'status': 'complete'
            }
            
            yield f"data: {json.dumps(final_result)}\n\n"
            # print(f"🔵 [BACKEND] FINAL RESULT SENT - ID: {request_id}")
            
        except Exception as e:
            total_time = time.time() - start_time
            error_result = {
                'type': 'error',
                'error': str(e),
                'processing_time': round(total_time, 2),
                'status': 'error'
            }
            yield f"data: {json.dumps(error_result)}\n\n"
    
    return StreamingResponse(
        generate_stream(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.post("/translate")
async def translate_pdf(request: TranslateRequest, background_tasks: BackgroundTasks):
    """Translate PDF document using Claude 4.5 and return translated text"""
    start_time = time.time()
    request_id = f"req_{int(time.time())}"
    
    try:
        # Decode base64 PDF
        try:
            pdf_bytes = base64.b64decode(request.body)
        except Exception as e:
            logger.error(f"❌ [{request_id}] Failed to decode base64 PDF: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid base64 PDF data")
        
        # Validate file size (15MB limit)
        file_size_mb = len(pdf_bytes) / (1024 * 1024)
        
        if len(pdf_bytes) > 15 * 1024 * 1024:
            logger.error(f"❌ [{request_id}] File size exceeds 15MB limit: {file_size_mb:.2f} MB")
            raise HTTPException(status_code=400, detail="File size exceeds 15MB limit")
        
        # Schedule input PDF upload to S3 as background task (non-blocking)
        input_file_name = generate_file_name("input_document", request_id) + ".pdf"
        background_tasks.add_task(
            upload_to_s3_background,
            file_content=pdf_bytes,
            file_name=input_file_name,
            folder="input",
            request_id=request_id,
            content_type="application/pdf"
        )
        
        # Extract and translate content using selected model (main processing - no S3 blocking)
        model_choice = request.model_choice or "claude-opus"
        if model_choice not in SUPPORTED_MODELS:
            raise HTTPException(status_code=400, detail=f"Unsupported model: {model_choice}")
        
        extraction_start = time.time()
        translated_document = await extract_and_translate_pdf(pdf_bytes, request.target_lang, request_id, model_choice)
        extraction_time = time.time() - extraction_start
        
        total_time = time.time() - start_time
        
        # Detect languages
        detected_language = detect_language_from_content(translated_document)
        target_language = "Hindi" if request.target_lang == "hi" else "English"
        
        # Return JSON response with translated document (S3 upload happens in background)
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

async def nova_stream_translation(pdf_bytes: bytes, target_lang: str, request_id: str):
    """Stream translation from Amazon Nova with real-time updates using correct Nova API format"""
    
    target_language = "Hindi" if target_lang == "hi" else "English"
    source_language = "English" if target_lang == "hi" else "Hindi"
    
    # Nova-specific prompt following Amazon Nova multimodal guidelines
    prompt_text = f"""## Instructions
Extract all information from this document and translate it completely from {source_language} to {target_language} using only Markdown formatting. Retain the original layout and structure including lists, tables, charts and all content.

## Rules
1. TRANSLATE EVERY WORD - Read the complete document and translate every single sentence, paragraph, table, list, header, footer, and section
2. COMPLETE TRANSLATION - Do not summarize or skip any content. Translate the entire document from beginning to end
3. STRUCTURE PRESERVATION - Maintain exact document structure and formatting hierarchy
4. Use # for main headings, ## for subheadings, ### for sub-subheadings
5. Preserve bullet points (•) and numbered lists exactly
6. Maintain table structures with proper formatting
7. Keep numbers, dates, proper names, and technical terms unchanged
8. NEVER use HTML image tags `<img>` in the output
9. NEVER use Markdown image tags `![]()` in the output
10. Always wrap the entire output in ``` tags

CRITICAL: This must be a COMPLETE word-for-word translation of the entire document. Do not provide summaries or excerpts."""

    # Nova request body format (based on official documentation)
    # For invoke_model API, bytes need to be base64 encoded
    import base64
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    # Following Nova multimodal guidelines: document first, then text prompt
    request_body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "document": {
                            "format": "pdf",
                            "name": "document.pdf",  # Simple, compliant name
                            "source": {"bytes": pdf_base64}  # Base64 encoded for JSON serialization
                        }
                    },
                    {"text": prompt_text}  # Text prompt must be last per guidelines
                ]
            }
        ],
        "inferenceConfig": {
            "maxTokens": 40000,  # Increased for complete translations
            "temperature": 0.7,  # Default temperature per guidelines
            "topP": 0.9  # Default topP per guidelines
        }
        # Reasoning disabled per OCR guidelines for better performance
    }
    
    logger.info(f"🔧 [{request_id}] NOVA STREAMING - Using correct Nova API format")
    logger.info(f"🔧 [{request_id}] NOVA STREAMING - Model ID: {SUPPORTED_MODELS['nova-2-lite']}")
    logger.info(f"🔧 [{request_id}] NOVA STREAMING - Document name: document.pdf")
    
    # Use streaming API with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Use Nova's invoke_model_with_response_stream API (correct method for documents)
            logger.info(f"🔧 [{request_id}] NOVA STREAMING - Calling invoke_model_with_response_stream (attempt {attempt + 1})")
            
            response = bedrock.invoke_model_with_response_stream(
                modelId=SUPPORTED_MODELS["nova-2-lite"],
                body=json.dumps(request_body)
            )
            
            logger.info(f"🔧 [{request_id}] NOVA STREAMING - API call successful, processing stream")
            
            # Process streaming response (based on official documentation)
            full_translation = ""
            chunk_count = 0
            last_chunks = []  # Track recent chunks to detect repetition
            
            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])
                
                if "contentBlockDelta" in chunk:
                    delta = chunk["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        chunk_text = delta["text"]
                        
                        # Check for repetition (only if exact same chunk repeats 5+ times)
                        if len(last_chunks) >= 5 and chunk_text.strip() and all(chunk_text.strip() == prev_chunk.strip() for prev_chunk in last_chunks[-5:]):
                            logger.warning(f"🔄 [{request_id}] NOVA STREAMING - Detected exact repetition, stopping stream")
                            break
                        
                        # Track recent chunks
                        last_chunks.append(chunk_text)
                        if len(last_chunks) > 5:  # Keep only last 5 chunks
                            last_chunks.pop(0)
                        
                        full_translation += chunk_text
                        chunk_count += 1
                        
                        # Yield chunk to frontend
                        yield {
                            'type': 'chunk',
                            'chunk': chunk_text,
                            'progress': len(full_translation),
                            'chunk_count': chunk_count,
                            'status': 'translating'
                        }
                
                elif "messageStop" in chunk:
                    # Translation complete
                    break
            
            # SUCCESS: Break out of retry loop after successful streaming completion
            logger.info(f"🔧 [{request_id}] NOVA STREAMING - Streaming completed successfully")
            break
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [{request_id}] NOVA STREAMING - Attempt {attempt + 1} failed: {error_msg}")
            
            if attempt == max_retries - 1:  # Last attempt
                yield {
                    'type': 'error',
                    'error': f"Nova streaming failed: {error_msg}",
                    'status': 'error'
                }
                raise HTTPException(status_code=500, detail=f"Nova streaming error: {error_msg}")
            else:
                # Wait before retry
                await asyncio.sleep(2 ** attempt)
                yield {
                    'type': 'retry',
                    'attempt': attempt + 1,
                    'max_retries': max_retries,
                    'status': 'retrying'
                }
                continue

async def bedrock_stream_translation(pdf_bytes: bytes, target_lang: str, request_id: str):
    """Stream translation from Bedrock with real-time updates"""
    
    # print(f"🟡 [BEDROCK] STARTING BEDROCK CALL - ID: {request_id}")
    target_language = "Hindi" if target_lang == "hi" else "English"
    source_language = "English" if target_lang == "hi" else "Hindi"
    
    # Claude prompt following multimodal guidelines - text should be last
    prompt_text = f"""## Instructions
Extract all information from this document and translate it completely from {source_language} to {target_language} using only Markdown formatting. Retain the original layout and structure including lists, tables, charts and all content.

## Rules
1. TRANSLATE EVERY WORD - Read the complete document and translate every single sentence, paragraph, table, list, header, footer, and section
2. COMPLETE TRANSLATION - Do not summarize or skip any content. Translate the entire document from beginning to end
3. STRUCTURE PRESERVATION - Maintain exact document structure and formatting hierarchy
4. Use # for main headings, ## for subheadings, ### for sub-subheadings
5. Preserve bullet points (•) and numbered lists exactly
6. Maintain table structures with proper formatting
7. Keep numbers, dates, proper names, and technical terms unchanged
8. For math formulae, always use LaTeX syntax
9. Describe images using only text
10. NEVER use HTML image tags `<img>` in the output
11. NEVER use Markdown image tags `![]()` in the output
12. Always wrap the entire output in ``` tags

CRITICAL: This must be a COMPLETE word-for-word translation of the entire document. Do not provide summaries or excerpts."""

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
    
    # Optimized Bedrock payload for streaming
    prompt = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 64000,
        "temperature": 0.05,
        "messages": [
            {
                "role": "user",
                "content": content_items
            }
        ]
    }
    
    # Use streaming API with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Use streaming invoke
            # print(f"🟡 [BEDROCK] INVOKING MODEL - ID: {request_id}, Attempt: {attempt + 1}")
            response = bedrock.invoke_model_with_response_stream(
                modelId=SUPPORTED_MODELS["claude-opus"],
                body=json.dumps(prompt),
                contentType='application/json',
                accept='application/json'
            )
            
            # Process streaming response
            full_translation = ""
            chunk_count = 0
            
            for event in response['body']:
                if 'chunk' in event:
                    chunk_data = json.loads(event['chunk']['bytes'].decode())
                    
                    if 'delta' in chunk_data and 'text' in chunk_data['delta']:
                        chunk_text = chunk_data['delta']['text']
                        full_translation += chunk_text
                        chunk_count += 1
                        
                        # Yield chunk to frontend
                        yield {
                            'type': 'chunk',
                            'chunk': chunk_text,
                            'progress': len(full_translation),
                            'chunk_count': chunk_count,
                            'status': 'translating'
                        }
                    
                    elif 'stop_reason' in chunk_data:
                        # Translation complete - just break, don't send duplicate complete event
                        # The main function will send the final event with cleaned document
                        break
            
            # SUCCESS: Break out of retry loop after successful streaming completion
            # print(f"🟢 [BEDROCK] STREAMING COMPLETED SUCCESSFULLY - ID: {request_id}, Attempt: {attempt + 1}")
            break
            
        except Exception as e:
            error_msg = str(e)
            
            if attempt == max_retries - 1:  # Last attempt
                yield {
                    'type': 'error',
                    'error': f"Bedrock streaming failed: {error_msg}",
                    'status': 'error'
                }
                raise HTTPException(status_code=500, detail=f"Bedrock streaming error: {error_msg}")
            else:
                # Wait before retry
                await asyncio.sleep(2 ** attempt)
                yield {
                    'type': 'retry',
                    'attempt': attempt + 1,
                    'max_retries': max_retries,
                    'status': 'retrying'
                }
                continue

async def extract_and_translate_pdf(pdf_bytes: bytes, target_lang: str, request_id: str, model_choice: str = "claude-opus") -> str:
    """Extract content from PDF and translate using Claude 4.5"""
    
    target_language = "Hindi" if target_lang == "hi" else "English"
    source_language = "English" if target_lang == "hi" else "Hindi"
    
    # Improved prompt following multimodal guidelines for complete translation
    prompt_text = f"""## Instructions
Extract all information from this document and translate it completely from {source_language} to {target_language} using only Markdown formatting. Retain the original layout and structure including lists, tables, charts and all content.

## Rules
1. TRANSLATE EVERY WORD - Read the complete document and translate every single sentence, paragraph, table, list, header, footer, and section
2. COMPLETE TRANSLATION - Do not summarize or skip any content. Translate the entire document from beginning to end
3. STRUCTURE PRESERVATION - Maintain exact document structure and formatting hierarchy
4. Use # for main headings, ## for subheadings, ### for sub-subheadings
5. Preserve bullet points (•) and numbered lists exactly
6. Maintain table structures with proper formatting
7. Keep numbers, dates, proper names, and technical terms unchanged
8. For math formulae, always use LaTeX syntax
9. Describe images using only text
10. NEVER use HTML image tags `<img>` in the output
11. NEVER use Markdown image tags `![]()` in the output
12. Always wrap the entire output in ``` tags

CRITICAL: This must be a COMPLETE word-for-word translation of the entire document. Do not provide summaries or excerpts. Translate every single page, section, table, list, and paragraph."""

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
    
    # Choose API format based on model
    if model_choice == "nova-2-lite":
        # Nova request body format (correct API format)
        # For invoke_model API, bytes need to be base64 encoded
        import base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # Following Nova multimodal guidelines: document first, then text prompt
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "document": {
                                "format": "pdf",
                                "name": "document.pdf",
                                "source": {"bytes": pdf_base64}  # Base64 encoded for JSON serialization
                            }
                        },
                        {"text": prompt_text}  # Text prompt must be last per guidelines
                    ]
                }
            ],
            "inferenceConfig": {
                "maxTokens": 40000,  # Increased for complete translations
                "temperature": 0.7,  # Default temperature per guidelines
                "topP": 0.9  # Default topP per guidelines
            }
            # Reasoning disabled per OCR guidelines for better performance
        }
        
        logger.info(f"🔧 [{request_id}] NOVA NON-STREAMING - Using correct Nova API format")
        logger.info(f"🔧 [{request_id}] NOVA NON-STREAMING - Model ID: {SUPPORTED_MODELS[model_choice]}")
        
        # Async retry logic for Nova API
        max_retries = 3
        for attempt in range(max_retries):
            try:
                bedrock_start = time.time()
                # Use asyncio to run Nova call in thread pool (non-blocking)
                logger.info(f"🔧 [{request_id}] NOVA NON-STREAMING - Calling invoke_model (attempt {attempt + 1})")
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: bedrock.invoke_model(
                        modelId=SUPPORTED_MODELS[model_choice],
                        body=json.dumps(request_body)
                    )
                )
                logger.info(f"🔧 [{request_id}] NOVA NON-STREAMING - API call successful")
                bedrock_time = time.time() - bedrock_start
                break  # Success, exit retry loop
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ [{request_id}] Nova API attempt {attempt + 1} failed: {error_msg}")
                
                if attempt == max_retries - 1:  # Last attempt
                    if "timeout" in error_msg.lower():
                        logger.error(f"💥 [{request_id}] All attempts failed due to timeout.")
                        raise HTTPException(
                            status_code=504, 
                            detail="Request timed out. The document may be too large or complex."
                        )
                    else:
                        logger.error(f"💥 [{request_id}] All Nova API attempts failed")
                        raise HTTPException(status_code=500, detail=f"Nova API error: {error_msg}")
                else:
                    # Async wait before retry (non-blocking)
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
    
    else:  # Claude model (default)
        # Optimized Bedrock payload for faster processing
        prompt = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 64000,  # Higher limit for complete translations
            "temperature": 0,  # Lower temperature for faster, more deterministic responses
            "messages": [
                {
                    "role": "user",
                    "content": content_items
                }
            ]
        }
        
        # Async retry logic for Bedrock API
        max_retries = 3
        for attempt in range(max_retries):
            try:
                bedrock_start = time.time()
                # Use asyncio to run Bedrock call in thread pool (non-blocking)
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: bedrock.invoke_model(
                        modelId=SUPPORTED_MODELS[model_choice],
                        body=json.dumps(prompt),
                        contentType='application/json',
                        accept='application/json'
                    )
                )
                bedrock_time = time.time() - bedrock_start
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
                    # Async wait before retry (non-blocking)
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
    
    # Parse response based on model type
    try:
        if model_choice == "nova-2-lite":
            # Nova response format (invoke_model returns different structure)
            body_content = response['body']
            if hasattr(body_content, 'read'):
                body_text = body_content.read().decode('utf-8')
            else:
                body_text = str(body_content)
            
            result = json.loads(body_text)
            translated_document = result['output']['message']['content'][0]['text']
        else:
            # Claude response format
            body_content = response['body']
            if hasattr(body_content, 'read'):
                body_text = body_content.read().decode('utf-8')
            else:
                body_text = str(body_content)
            
            result = json.loads(body_text)
            translated_document = result['content'][0]['text']
        
        response_length = len(translated_document)
        
        # Check if translation seems complete (enhanced heuristics)
        if response_length < 100:
            logger.warning(f"⚠️  [{request_id}] Translation seems very short ({response_length} chars)")
        
        # Check for common document ending patterns
        ending_patterns = [
            "signature", "हस्ताक्षर", "annexure", "अनुलग्नक", 
            "details of", "का विवरण", "borrower", "उधारकर्ता",
            "authorized person", "अधिकृत व्यक्ति"
        ]
        
        has_proper_ending = any(pattern.lower() in translated_document.lower() for pattern in ending_patterns)
        if not has_proper_ending:
            logger.warning(f"⚠️  [{request_id}] Translation may be incomplete - missing expected ending patterns")
        
        # Check for section completeness (should have sections A through N minimum)
        section_count = len([line for line in translated_document.split('\n') if line.strip().startswith(('A)', 'B)', 'C)', 'D)', 'E)', 'F)', 'G)', 'H)', 'I)', 'J)', 'K)', 'L)', 'M)', 'N)'))])
        if section_count < 10:  # Should have at least 10 major sections
            logger.warning(f"⚠️  [{request_id}] Translation may be incomplete - only found {section_count} major sections")
        
        # Check if we need to retry for completeness
        if response_length < 1000 or not has_proper_ending:
            # Retry prompt with emphasis on completeness
            retry_prompt_text = f"""## Instructions - RETRY FOR COMPLETENESS
The previous translation was incomplete. Extract ALL information from this document and translate it COMPLETELY from {source_language} to {target_language} using only Markdown formatting. 

## Critical Requirements
1. TRANSLATE EVERY SINGLE WORD - Do not skip any content, sections, tables, lists, headers, footers, or appendices
2. COMPLETE DOCUMENT TRANSLATION - Translate from the very first word to the very last word
3. INCLUDE ALL PAGES - Translate every page, every section, every paragraph, every table row
4. PRESERVE ALL STRUCTURE - Maintain exact formatting, lists, tables, and hierarchy
5. NO SUMMARIES - This must be a complete word-for-word translation, not a summary
6. Use # for main headings, ## for subheadings, ### for sub-subheadings
7. Preserve bullet points (•) and numbered lists exactly
8. Maintain table structures with proper formatting
9. Keep numbers, dates, proper names, and technical terms unchanged
10. Always wrap the entire output in ``` tags

CRITICAL: Translate the ENTIRE document completely. Every word, every sentence, every section must be translated."""

            try:
                if model_choice == "nova-2-lite":
                    # Nova retry format (correct API format)
                    # For invoke_model API, bytes need to be base64 encoded
                    import base64
                    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                    
                    # Following Nova multimodal guidelines: document first, then text prompt
                    retry_request_body = {
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "document": {
                                            "format": "pdf",
                                            "name": "document.pdf",
                                            "source": {"bytes": pdf_base64}  # Base64 encoded for JSON serialization
                                        }
                                    },
                                    {"text": retry_prompt_text}  # Text prompt must be last per guidelines
                                ]
                            }
                        ],
                        "inferenceConfig": {
                            "maxTokens": 40000,  # Increased for complete translations
                            "temperature": 0.7,  # Default temperature per guidelines
                            "topP": 0.9  # Default topP per guidelines
                        }
                        # Reasoning disabled per OCR guidelines for better performance
                    }
                    
                    logger.info(f"🔧 [{request_id}] NOVA RETRY - Using correct Nova API format for retry")
                    
                    # Use async executor for retry call
                    loop = asyncio.get_event_loop()
                    retry_response = await loop.run_in_executor(
                        None,
                        lambda: bedrock.invoke_model(
                            modelId=SUPPORTED_MODELS[model_choice],
                            body=json.dumps(retry_request_body)
                        )
                    )
                    
                    # Parse Nova retry response
                    retry_body_content = retry_response['body']
                    if hasattr(retry_body_content, 'read'):
                        retry_body_text = retry_body_content.read().decode('utf-8')
                    else:
                        retry_body_text = str(retry_body_content)
                    
                    retry_result = json.loads(retry_body_text)
                    retry_translated_document = retry_result['output']['message']['content'][0]['text']
                    
                else:
                    # Claude retry format
                    retry_content_items = [
                        {
                            "type": "text",
                            "text": retry_prompt_text
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
                    
                    retry_prompt = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 64000,  # Match main prompt token limit
                        "temperature": 0.03,  # Even lower for retry consistency
                        "messages": [
                            {
                                "role": "user",
                                "content": retry_content_items
                            }
                        ]
                    }
                    
                    # Use async executor for retry call as well
                    loop = asyncio.get_event_loop()
                    retry_response = await loop.run_in_executor(
                        None,
                        lambda: bedrock.invoke_model(
                            modelId=SUPPORTED_MODELS[model_choice],
                            body=json.dumps(retry_prompt),
                            contentType='application/json',
                            accept='application/json'
                        )
                    )
                    
                    retry_body_content = retry_response['body']
                    if hasattr(retry_body_content, 'read'):
                        retry_body_text = retry_body_content.read().decode('utf-8')
                    else:
                        retry_body_text = str(retry_body_content)
                    
                    retry_result = json.loads(retry_body_text)
                    retry_translated_document = retry_result['content'][0]['text']
                
                # Use retry result if it's longer and more complete
                if len(retry_translated_document) > len(translated_document):
                    translated_document = retry_translated_document
                    
            except Exception as retry_error:
                logger.warning(f"⚠️  [{request_id}] Retry failed: {str(retry_error)}, using original translation")
        
        # Post-process the translation to clean it up
        cleaned_document = post_process_translation(translated_document, request_id)
        
        return cleaned_document
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] Failed to parse Bedrock response: {str(e)}")
        logger.error(f"📋 [{request_id}] Raw response preview: {body_text[:500]}...")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")

def post_process_translation(text: str, request_id: str) -> str:
    """Clean up and format the translated document - optimized single-pass processing"""
    
    # First, strip outer code fences if present (Nova might wrap output in ``` tags)
    def strip_outer_code_fences(text):
        lines = text.split("\n")
        # Remove only the outer code fences if present
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
        return "\n".join(lines).strip()
    
    # Strip code fences first
    cleaned = strip_outer_code_fences(text)
    
    # Combined regex patterns for single-pass processing (much faster)
    # Remove black boxes, excessive whitespace, and clean up formatting in one go
    patterns = [
        (r'[■□]+', ''),  # Remove box characters
        (r'\n\s*\n\s*\n+', '\n\n'),  # Fix excessive whitespace
        (r'^\s*[0-9]\s*$', ''),  # Remove single numbers on lines
        (r'^[\s\-_=|]+$', ''),  # Remove lines with only special chars
        (r'^[-=]{3,}$', ''),  # Remove separator lines
        (r'\n+(#{1,3}\s)', r'\n\n\1'),  # Fix header spacing
        (r'\n{3,}', '\n\n')  # Final spacing cleanup
    ]
    
    # Apply all patterns in sequence (still faster than multiple separate calls)
    for pattern, replacement in patterns:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.MULTILINE)
    
    # Single-pass line filtering (optimized)
    lines = cleaned.split('\n')
    filtered_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Combined conditions for faster processing
        if (len(stripped) <= 2 and stripped.isdigit()) or \
           (len(stripped) <= 1 and not stripped.isalnum()) or \
           (len(stripped) > 0 and stripped.count('■') / len(stripped) > 0.5):
            continue
        filtered_lines.append(line)
    
    return '\n'.join(filtered_lines).strip()

def detect_language_from_content(text: str) -> str:
    """Detect the primary language of the text content - optimized single-pass"""
    # Single-pass character counting (much faster than regex findall)
    hindi_count = 0
    english_count = 0
    
    for char in text:
        if '\u0900' <= char <= '\u097F':  # Devanagari range
            hindi_count += 1
        elif 'a' <= char <= 'z' or 'A' <= char <= 'Z':  # English range
            english_count += 1
        
        # Early exit optimization - if one language is clearly dominant
        if hindi_count > english_count + 100:
            return "Hindi"
        elif english_count > hindi_count + 100:
            return "English"
    
    return "Hindi" if hindi_count > english_count else "English"

# Background task functions for async S3 operations
def upload_to_s3_background(file_content: bytes, file_name: str, folder: str, request_id: str, content_type: str = 'application/octet-stream'):
    """Background task for S3 upload - non-blocking"""
    try:
        # Create S3 key with folder structure
        s3_key = f"{folder}/{file_name}"
        
        # Upload to S3 without blocking main thread
        s3_client.put_object(
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
        
    except Exception as e:
        # Log error but don't fail the main request
        logger.warning(f"⚠️ [{request_id}] Background S3 upload failed: {str(e)}")

def upload_to_s3_sync(file_content: bytes, file_name: str, folder: str, request_id: str, content_type: str = 'application/octet-stream') -> str:
    """Synchronous S3 upload for critical operations that need confirmation"""
    try:
        # Create S3 key with folder structure
        s3_key = f"{folder}/{file_name}"
        
        # Test S3 connectivity first
        try:
            s3_client.head_bucket(Bucket=BUCKET_NAME)
        except Exception as bucket_error:
            logger.error(f"❌ [{request_id}] S3 bucket access failed: {str(bucket_error)}")
            raise Exception(f"S3 bucket access denied: {str(bucket_error)}")
        
        # Upload to S3
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
        
        # Generate S3 URL
        s3_url = f"s3://{BUCKET_NAME}/{s3_key}"
        
        return s3_url
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] S3 upload failed with error: {str(e)}")
        raise Exception(f"S3 upload failed: {str(e)}")

def sanitize_document_name_for_nova(name: str = "document") -> str:
    """
    Sanitize document name for Nova API requirements:
    - Only alphanumeric characters, whitespace, hyphens, parentheses, and square brackets
    - No more than one consecutive whitespace character
    - Max length should be reasonable
    """
    import re
    
    # Start with a safe default if name is empty
    if not name or not name.strip():
        name = "document"
    
    # Remove file extensions
    name = re.sub(r'\.[^.]*$', '', name)
    
    # Replace problematic characters with safe alternatives
    # Convert underscores and dots to hyphens (which are allowed)
    name = name.replace('_', '-').replace('.', '-')
    
    # Keep only allowed characters: alphanumeric, whitespace, hyphens, parentheses, square brackets
    name = re.sub(r'[^a-zA-Z0-9\s\-\(\)\[\]]', '', name)
    
    # Replace multiple consecutive whitespace with single space
    name = re.sub(r'\s+', ' ', name)
    
    # Replace multiple consecutive hyphens with single hyphen
    name = re.sub(r'-+', '-', name)
    
    # Trim whitespace and hyphens
    name = name.strip().strip('-')
    
    # Ensure it's not empty after cleaning
    if not name:
        name = "document"
    
    # Limit length to be safe (Nova doesn't specify max length, but let's be conservative)
    if len(name) > 50:
        name = name[:50].strip().strip('-')
    
    # Add .pdf extension for clarity
    return f"{name}.pdf"

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
    uvicorn.run(app, host="0.0.0.0", port=8000)