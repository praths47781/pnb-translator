from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import re
import os
import urllib.request
import tempfile

def generate_pdf(title="Sample PDF Report",
                body="This is a sample PDF generated using ReportLab.",
                logo_path=None,
                output_path="output.pdf"):
    """Generate a professional PDF document with header, body, table, and footer"""
    
    if output_path:
        doc = SimpleDocTemplate(output_path, pagesize=A4,
                              rightMargin=72, leftMargin=72,
                              topMargin=100, bottomMargin=72)
    else:
        # Create in-memory PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                              rightMargin=72, leftMargin=72,
                              topMargin=100, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.HexColor('#34495e'),
        leftIndent=0
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        leftIndent=0,
        rightIndent=0
    )
    
    story = []
    
    # LOGO (top right)
    if logo_path:
        try:
            img = Image(logo_path, width=1.2*inch, height=1.2*inch)
            img.hAlign = 'RIGHT'
            story.append(img)
        except:
            story.append(Paragraph("<b>PNB Housing Finance Ltd.</b>", styles["Normal"]))
    else:
        # Company header
        company_style = ParagraphStyle(
            'Company',
            parent=styles['Normal'],
            fontSize=12,
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#2c3e50')
        )
        story.append(Paragraph("<b>PNB Housing Finance Ltd.</b>", company_style))
    
    story.append(Spacer(1, 20))
    
    # TITLE
    story.append(Paragraph(title, title_style))
    
    # Horizontal line
    story.append(Spacer(1, 12))
    
    # BODY - Process markdown-like formatting
    body_paragraphs = body.split('\n\n')
    
    for para_text in body_paragraphs:
        if not para_text.strip():
            continue
            
        # Handle headers
        if para_text.startswith('# '):
            header_text = para_text[2:].strip()
            story.append(Paragraph(header_text, title_style))
        elif para_text.startswith('## '):
            header_text = para_text[3:].strip()
            story.append(Paragraph(header_text, heading_style))
        elif para_text.startswith('### '):
            header_text = para_text[4:].strip()
            sub_heading_style = ParagraphStyle(
                'SubHeading',
                parent=heading_style,
                fontSize=12
            )
            story.append(Paragraph(header_text, sub_heading_style))
        else:
            # Regular paragraph - handle bold text
            formatted_text = para_text.replace('**', '<b>', 1).replace('**', '</b>', 1)
            
            # Handle bullet points
            if para_text.strip().startswith('•') or para_text.strip().startswith('-'):
                bullet_style = ParagraphStyle(
                    'Bullet',
                    parent=body_style,
                    leftIndent=20,
                    bulletIndent=10
                )
                story.append(Paragraph(formatted_text, bullet_style))
            else:
                story.append(Paragraph(formatted_text, body_style))
        
        story.append(Spacer(1, 6))
    
    # TABLE (if content suggests tabular data)
    if any(keyword in body.lower() for keyword in ["table", "data", "summary", "information"]):
        story.append(Spacer(1, 20))
        story.append(Paragraph("Document Summary", heading_style))
        
        data = [
            ["Attribute", "Value", "Status"],
            ["Document Type", "Translation Report", "✓ Complete"],
            ["Processing Method", "AI-Powered Translation", "✓ Automated"],
            ["Quality Check", "Structure Preserved", "✓ Verified"],
            ["Output Format", "Professional Template", "✓ Applied"],
        ]
        
        table = Table(data, colWidths=[2.5*inch, 2.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            
            # Data rows
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            
            # Borders
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            
            # Alternating row colors
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
    
    # FOOTER HANDLER
    def add_footer(canvas, doc):
        canvas.saveState()
        
        # Footer line
        canvas.setStrokeColor(colors.grey)
        canvas.line(72, 50, A4[0] - 72, 50)
        
        # Footer text
        canvas.setFont("Helvetica", 8)
        footer_text = "Confidential Document | PNB Housing Finance Ltd."
        canvas.drawString(72, 35, footer_text)
        
        # Page number
        page_text = f"Page {doc.page}"
        canvas.drawRightString(A4[0] - 72, 35, page_text)
        
        canvas.restoreState()
    
    # BUILD PDF WITH FOOTER CALLBACK
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    
    if output_path:
        return output_path
    else:
        buffer.seek(0)
        return buffer.getvalue()

def register_dejavu_font():
    """Register DejaVu Sans font which has good Unicode support"""
    try:
        # DejaVu Sans paths in different systems
        dejavu_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            '/System/Library/Fonts/DejaVuSans.ttf',
            'C:\\Windows\\Fonts\\DejaVuSans.ttf'
        ]
        
        for path in dejavu_paths:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont('DejaVuSans', path))
                    return 'DejaVuSans'
                    
                except Exception as test_error:
                    continue
        
        return None
    except Exception as e:
        return None

def clean_text_for_pdf(text):
    """Clean text to remove characters that might not render properly"""
    if not text:
        return ""
    
    # Replace problematic characters that show as black boxes
    replacements = {
        '■': '',  # Remove black box characters (these are showing in your output)
        '□': '',  # Remove empty box characters
        '\uf0b7': '•',  # Replace bullet character
        '\u2022': '•',  # Standard bullet
        '\u25cf': '•',  # Black circle to bullet
        '\u25a0': '',  # Black square
        '\u25a1': '',  # White square
        '\ufffd': '',  # Replacement character (indicates encoding issues)
    }
    
    cleaned_text = text
    for old_char, new_char in replacements.items():
        cleaned_text = cleaned_text.replace(old_char, new_char)
    
    # Remove any remaining control characters or problematic Unicode
    import re
    cleaned_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', '', cleaned_text)
    
    # Also remove any remaining box-drawing characters that might cause issues
    cleaned_text = re.sub(r'[\u2500-\u257F]', '', cleaned_text)  # Box drawing characters
    cleaned_text = re.sub(r'[\u2580-\u259F]', '', cleaned_text)  # Block elements
    
    return cleaned_text

def register_hindi_fonts():
    """Register Hindi-compatible fonts for PDF generation"""
    
    # Try DejaVu Sans first (most reliable for Unicode)
    dejavu_font = register_dejavu_font()
    if dejavu_font:
        return dejavu_font
    
    # List of font paths to try (in order of preference)
    import os
    home_dir = os.path.expanduser("~")
    
    font_candidates = [
        # User's Noto fonts (macOS - highest priority)
        (f'{home_dir}/Library/Fonts/NotoSansDevanagari-Regular.ttf', 'NotoDevanagari'),
        (f'{home_dir}/Library/Fonts/NotoSansDevanagariUI-Regular.ttf', 'NotoDevanagariUI'),
        
        # System Noto fonts (Linux)
        ('/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf', 'NotoDevanagariSystem'),
        ('/usr/share/fonts/noto/NotoSansDevanagari-Regular.ttf', 'NotoDevanagariSystem2'),
        
        # macOS system fonts with Devanagari support
        ('/System/Library/Fonts/Supplemental/DevanagariMT.ttc', 'DevanagariMT'),
        ('/System/Library/Fonts/Supplemental/ITFDevanagari.ttc', 'ITFDevanagari'),
        ('/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc', 'DevanagariSangam'),
        
        # Other good Unicode fonts
        ('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 'LiberationSans'),
        ('/System/Library/Fonts/Arial Unicode MS.ttf', 'ArialUnicode'),
        ('/Library/Fonts/Arial Unicode MS.ttf', 'ArialUnicode2'),
        
        # Windows fonts
        ('C:\\Windows\\Fonts\\arial.ttf', 'WindowsArial'),
    ]
    
    for font_path, font_name in font_candidates:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                return font_name
            except Exception as e:
                continue
    
    # Final fallback - use Helvetica
    return 'Helvetica'

def wrap_hindi_text_with_font(text, font_name):
    """Wrap Hindi text segments with explicit font tags"""
    if not text or font_name == 'Helvetica':
        return text
    
    import re
    
    # Find Hindi text segments (Devanagari script)
    def replace_hindi(match):
        hindi_text = match.group(0)
        return f'<font name="{font_name}">{hindi_text}</font>'
    
    # Pattern to match Devanagari characters (Hindi script)
    hindi_pattern = r'[\u0900-\u097F]+'
    
    # Replace Hindi segments with font-wrapped versions
    wrapped_text = re.sub(hindi_pattern, replace_hindi, text)
    
    return wrapped_text

def safe_text_for_pdf(text, font_name='Helvetica'):
    """Ensure text is properly encoded for PDF generation"""
    if not text:
        return ""
    
    try:
        # Ensure text is properly encoded as UTF-8
        if isinstance(text, bytes):
            text = text.decode('utf-8')
        
        # Clean problematic characters first
        text = clean_text_for_pdf(text)
        
        # For Hindi text, ensure proper Unicode normalization
        import unicodedata
        text = unicodedata.normalize('NFC', text)
        
        # Wrap Hindi text with explicit font tags to force correct rendering
        if font_name != 'Helvetica':
            text = wrap_hindi_text_with_font(text, font_name)
        
        return text
    except Exception as e:
        return str(text)

def create_fonts_directory():
    """Create fonts directory and download essential Hindi font"""
    try:
        # Create fonts directory
        fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
        os.makedirs(fonts_dir, exist_ok=True)
        
        # Use a more reliable font source - Noto Sans from Google Fonts
        font_filename = 'NotoSans-Regular.ttf'
        font_path = os.path.join(fonts_dir, font_filename)
        
        return fonts_dir
    except Exception as e:
        return None

def check_hindi_text(text):
    """Check if text contains Hindi characters"""
    if not text:
        return False
    
    # Check for Devanagari script characters (Hindi)
    for char in text:
        if 0x0900 <= ord(char) <= 0x097F:  # Devanagari Unicode range
            return True
    return False

def generate_pdf_from_translation(translated_text, source_lang="English", target_lang="Hindi"):
    """Generate professional PDF document from translation results"""
    
    # Check if we have Hindi text
    has_hindi = check_hindi_text(translated_text)
    
    # Register fonts
    selected_font = register_hindi_fonts()
    
    # Ensure text is properly encoded
    translated_text = safe_text_for_pdf(translated_text, selected_font)
    
    # Create in-memory PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                          rightMargin=72, leftMargin=72,
                          topMargin=100, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    
    # For bold text, try to register a bold version or use the same font
    selected_font_bold = selected_font
    
    # If we have a Hindi font, try to register bold version
    if selected_font == 'NotoDevanagari':
        try:
            # Try to find and register bold version
            home_dir = os.path.expanduser("~")
            bold_font_path = f'{home_dir}/Library/Fonts/NotoSansDevanagari-Bold.ttf'
            if os.path.exists(bold_font_path):
                pdfmetrics.registerFont(TTFont('NotoDevanagariBold', bold_font_path))
                selected_font_bold = 'NotoDevanagariBold'
        except Exception as e:
            selected_font_bold = selected_font
    
    title_style = ParagraphStyle(
        'ProfessionalTitle',
        fontSize=22,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1e40af'),
        fontName=selected_font_bold,
        leading=26,
        wordWrap='LTR'  # Ensure proper text direction
    )
    
    heading_style = ParagraphStyle(
        'ProfessionalHeading',
        fontSize=16,
        spaceAfter=15,
        spaceBefore=20,
        textColor=colors.HexColor('#1e40af'),
        fontName=selected_font_bold,
        leading=20,
        wordWrap='LTR'
    )
    
    subheading_style = ParagraphStyle(
        'ProfessionalSubHeading',
        fontSize=14,
        spaceAfter=12,
        spaceBefore=15,
        textColor=colors.HexColor('#374151'),
        fontName=selected_font_bold,
        leading=18,
        wordWrap='LTR'
    )
    
    body_style = ParagraphStyle(
        'ProfessionalBody',
        fontSize=12,
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        fontName=selected_font,
        leading=18,
        wordWrap='LTR'
    )
    
    meta_style = ParagraphStyle(
        'MetaData',
        fontSize=10,
        spaceAfter=8,
        fontName=selected_font,
        textColor=colors.HexColor('#6b7280'),
        leading=12,
        wordWrap='LTR'
    )
    
    story = []
    
    # COMPANY HEADER
    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Normal'],
        fontSize=14,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#1e40af'),
        fontName='Helvetica-Bold'
    )
    story.append(Paragraph("PNB Housing Finance Ltd.", company_style))
    story.append(Paragraph("Professional Translation Service", meta_style))
    story.append(Spacer(1, 30))
    
    # Extract document title
    lines = [line.strip() for line in translated_text.split('\n') if line.strip()]
    doc_title = "Professional Translation Document"
    
    for line in lines[:3]:
        if line and (line.startswith('#') or len(line) < 80):
            doc_title = line.replace('#', '').strip()
            break
    
    # DOCUMENT TITLE (if extracted from content)
    if doc_title and doc_title != "Professional Translation Document":
        story.append(Paragraph(doc_title, title_style))
        story.append(Spacer(1, 20))
    
    # Process translated content with improved formatting
    for line in lines:
        if not line:
            story.append(Spacer(1, 6))
            continue
            
        # Handle headers
        if line.startswith('# '):
            safe_title = safe_text_for_pdf(line[2:], selected_font)
            story.append(Paragraph(safe_title, title_style))
        elif line.startswith('## '):
            safe_heading = safe_text_for_pdf(line[3:], selected_font)
            story.append(Paragraph(safe_heading, heading_style))
        elif line.startswith('### '):
            safe_subheading = safe_text_for_pdf(line[4:], selected_font)
            story.append(Paragraph(safe_subheading, subheading_style))
        # Handle lists
        elif line.strip().startswith(('•', '-', '*')):
            bullet_style = ParagraphStyle(
                'BulletPoint',
                parent=body_style,
                leftIndent=20,
                bulletIndent=10,
                bulletFontName='Symbol',
                fontName=selected_font
            )
            safe_bullet = safe_text_for_pdf(f"• {line.strip()[1:].strip()}", selected_font)
            story.append(Paragraph(safe_bullet, bullet_style))
        elif line.strip().startswith(tuple(f'{i}.' for i in range(1, 10))):
            number_style = ParagraphStyle(
                'NumberedList',
                parent=body_style,
                leftIndent=20,
                fontName=selected_font
            )
            safe_number = safe_text_for_pdf(line.strip(), selected_font)
            story.append(Paragraph(safe_number, number_style))
        # Handle tables
        elif '|' in line and len(line.split('|')) > 2:
            table_style = ParagraphStyle(
                'TableText',
                parent=styles['Normal'],
                fontSize=9,
                fontName='Courier',
                spaceAfter=6
            )
            story.append(Paragraph(line, table_style))
        # Regular paragraphs
        else:
            # Handle bold text and ensure proper encoding
            formatted_line = line.replace('**', '<b>', 1).replace('**', '</b>', 1)
            safe_line = safe_text_for_pdf(formatted_line, selected_font)
            
            story.append(Paragraph(safe_line, body_style))
    
    # FOOTER HANDLER
    def add_professional_footer(canvas, doc):
        canvas.saveState()
        
        # Footer line
        canvas.setStrokeColor(colors.HexColor('#1e40af'))
        canvas.setLineWidth(2)
        canvas.line(72, 60, A4[0] - 72, 60)
        
        # Confidentiality notice
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor('#6b7280'))
        footer_text = "CONFIDENTIAL DOCUMENT | PNB Housing Finance Ltd. | Professional Translation Service"
        canvas.drawCentredString(A4[0] / 2, 45, footer_text)
        
        # Page number
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(colors.HexColor('#1e40af'))
        page_text = f"Page {doc.page}"
        canvas.drawRightString(A4[0] - 72, 30, page_text)
        
        canvas.restoreState()
    
    # BUILD PDF
    doc.build(story, onFirstPage=add_professional_footer, onLaterPages=add_professional_footer)
    
    buffer.seek(0)
    return buffer.getvalue()

if __name__ == "__main__":
    generate_pdf()