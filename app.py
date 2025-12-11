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
            
            # Stream translation from Bedrock
            # print(f"🟡 [BACKEND] CALLING BEDROCK STREAMING - ID: {request_id}")
            full_translation = ""
            async for chunk_data in bedrock_stream_translation(pdf_bytes, request.target_lang, request_id):
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
        
        # Extract and translate content using Claude 4.5 (main processing - no S3 blocking)
        extraction_start = time.time()
        translated_document = await extract_and_translate_pdf(pdf_bytes, request.target_lang, request_id)
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

async def bedrock_stream_translation(pdf_bytes: bytes, target_lang: str, request_id: str):
    """Stream translation from Bedrock with real-time updates"""
    
    # print(f"🟡 [BEDROCK] STARTING BEDROCK CALL - ID: {request_id}")
    target_language = "Hindi" if target_lang == "hi" else "English"
    source_language = "English" if target_lang == "hi" else "Hindi"
    
    # Optimized concise prompt (same as before)
    prompt_text = f"""Translate this PDF document completely from {source_language} to {target_language}.

REQUIREMENTS:
1. Translate EVERY word from start to finish - do not stop early
2. Preserve exact structure: headings, lists, tables, formatting
3. Keep all numbers, dates, names, and legal terms unchanged
4. Use markdown: # for titles, ## for sections, **bold** for emphasis
5. Include ALL sections A-N and beyond, annexures, signatures, contact info

OUTPUT: Start translation immediately. Translate the complete document including all fine print and appendices."""

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
                modelId=MODEL_ID,
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

async def extract_and_translate_pdf(pdf_bytes: bytes, target_lang: str, request_id: str) -> str:
    """Extract content from PDF and translate using Claude 4.5"""
    
    target_language = "Hindi" if target_lang == "hi" else "English"
    source_language = "English" if target_lang == "hi" else "Hindi"
    
    # Optimized concise prompt (much faster processing)
    prompt_text = f"""Translate this PDF document completely from {source_language} to {target_language}.

REQUIREMENTS:
1. Translate EVERY word from start to finish - do not stop early
2. Preserve exact structure: headings, lists, tables, formatting
3. Keep all numbers, dates, names, and legal terms unchanged
4. Use markdown: # for titles, ## for sections, **bold** for emphasis
5. Include ALL sections A-N and beyond, annexures, signatures, contact info

OUTPUT: Start translation immediately. Translate the complete document including all fine print and appendices."""

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
                    modelId=MODEL_ID,
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
    
    # Parse response
    try:
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
            # Concise retry prompt
            retry_prompt_text = f"""COMPLETE TRANSLATION REQUIRED: Translate this ENTIRE document from {source_language} to {target_language}.

Previous attempt was incomplete. Translate ALL sections A-N+, tables, annexures, signatures, and contact info. Do not stop early.

Translate the COMPLETE document now:"""

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
            
            try:
                # Use async executor for retry call as well
                loop = asyncio.get_event_loop()
                retry_response = await loop.run_in_executor(
                    None,
                    lambda: bedrock.invoke_model(
                        modelId=MODEL_ID,
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
    cleaned = text
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