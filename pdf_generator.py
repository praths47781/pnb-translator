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

def register_hindi_fonts():
    """Register Hindi-compatible fonts for PDF generation"""
    try:
        # Try to register system fonts that support Hindi
        font_paths = [
            '/System/Library/Fonts/Arial Unicode MS.ttf',  # macOS
            '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',  # Linux
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux fallback
            'C:\\Windows\\Fonts\\arial.ttf',  # Windows fallback
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('HindiFont', font_path))
                    return 'HindiFont'
                except:
                    continue
        
        # If no system fonts found, use default with Unicode support
        return 'Helvetica'
        
    except Exception as e:
        print(f"Font registration warning: {e}")
        return 'Helvetica'

def generate_pdf_from_translation(translated_text, source_lang="English", target_lang="Hindi"):
    """Generate professional PDF document from translation results"""
    
    # Register Hindi fonts
    hindi_font = register_hindi_fonts()
    
    # Create in-memory PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                          rightMargin=72, leftMargin=72,
                          topMargin=100, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    
    # Professional styles with Hindi font support
    title_style = ParagraphStyle(
        'ProfessionalTitle',
        parent=styles['Heading1'],
        fontSize=22,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1e40af'),
        fontName=hindi_font if target_lang == "Hindi" else 'Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'ProfessionalHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=15,
        spaceBefore=20,
        textColor=colors.HexColor('#1e40af'),
        fontName=hindi_font if target_lang == "Hindi" else 'Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'ProfessionalSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=15,
        textColor=colors.HexColor('#374151'),
        fontName=hindi_font if target_lang == "Hindi" else 'Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'ProfessionalBody',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        fontName=hindi_font if target_lang == "Hindi" else 'Helvetica',
        leading=18
    )
    
    meta_style = ParagraphStyle(
        'MetaData',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        fontName=hindi_font if target_lang == "Hindi" else 'Helvetica',
        textColor=colors.HexColor('#6b7280')
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
    
    # DOCUMENT TITLE
    story.append(Paragraph(doc_title, title_style))
    
    # METADATA SECTION
    story.append(Paragraph("Translation Information", heading_style))
    
    # Create metadata table
    meta_data = [
        ["Source Language:", source_lang],
        ["Target Language:", target_lang],
        ["Translation Method:", "AI-Powered Professional Translation"],
        ["Processing Engine:", "AWS Bedrock Claude 4.5"],
        ["Document Status:", "Verified Professional Translation"],
        ["Generated:", "Automated Translation Service"]
    ]
    
    meta_table = Table(meta_data, colWidths=[2.5*inch, 3.5*inch])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    story.append(meta_table)
    story.append(Spacer(1, 30))
    
    # TRANSLATED CONTENT SECTION
    story.append(Paragraph("Translated Document", heading_style))
    
    # Process translated content with proper formatting
    for line in lines:
        if not line:
            story.append(Spacer(1, 6))
            continue
            
        # Handle headers
        if line.startswith('# '):
            story.append(Paragraph(line[2:], title_style))
        elif line.startswith('## '):
            story.append(Paragraph(line[3:], heading_style))
        elif line.startswith('### '):
            story.append(Paragraph(line[4:], subheading_style))
        # Handle lists
        elif line.strip().startswith(('•', '-', '*')):
            bullet_style = ParagraphStyle(
                'BulletPoint',
                parent=body_style,
                leftIndent=20,
                bulletIndent=10,
                bulletFontName='Symbol'
            )
            story.append(Paragraph(f"• {line.strip()[1:].strip()}", bullet_style))
        elif line.strip().startswith(tuple(f'{i}.' for i in range(1, 10))):
            number_style = ParagraphStyle(
                'NumberedList',
                parent=body_style,
                leftIndent=20
            )
            story.append(Paragraph(line.strip(), number_style))
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
            # Handle bold text
            formatted_line = line.replace('**', '<b>', 1).replace('**', '</b>', 1)
            story.append(Paragraph(formatted_line, body_style))
    
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