#!/usr/bin/env python3
"""
Generate: IsolationForest_VousFin_Technical_Overview.pdf
A comprehensive professional PDF covering the Isolation Forest anomaly detection
module in vousFin Smart Accountant.
"""

import os
import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, PageBreak, KeepTogether, ListFlowable, ListItem,
    Flowable,
)
from reportlab.platypus.doctemplate import NextPageTemplate
from reportlab.lib.utils import ImageReader

# ── Colour palette ─────────────────────────────────────────────────────────
NAVY    = HexColor('#0B1020')
SLATE   = HexColor('#1E293B')
BRAND   = HexColor('#2563EB')
CYAN    = HexColor('#06B6D4')
GREEN   = HexColor('#10B981')
AMBER   = HexColor('#F59E0B')
RED     = HexColor('#EF4444')
PURPLE  = HexColor('#8B5CF6')
LGRAY   = HexColor('#F1F5F9')
MGRAY   = HexColor('#CBD5E1')
DGRAY   = HexColor('#64748B')
WHITE   = colors.white
BLACK   = colors.black

# ── Page geometry ──────────────────────────────────────────────────────────
PW, PH = A4
ML, MR, MT, MB = 2.2*cm, 2.2*cm, 2.4*cm, 2.8*cm
BODY_W = PW - ML - MR

# ── Output path ────────────────────────────────────────────────────────────
OUT = r"C:\Users\shafi\OneDrive\Desktop\VousFin Smart Accountant\FInal FYP Web\IsolationForest_VousFin_Technical_Overview.pdf"

# ═══════════════════════════════════════════════════════════════════════════
#  Styles
# ═══════════════════════════════════════════════════════════════════════════
def build_styles():
    s = getSampleStyleSheet()

    def add(name, **kw):
        s.add(ParagraphStyle(name=name, **kw))

    # Cover
    add('CoverTitle',    fontName='Helvetica-Bold',   fontSize=28, leading=36,
        textColor=WHITE, alignment=TA_CENTER, spaceAfter=10)
    add('CoverSub',      fontName='Helvetica',        fontSize=13, leading=18,
        textColor=HexColor('#94A3B8'), alignment=TA_CENTER, spaceAfter=6)
    add('CoverMeta',     fontName='Helvetica',        fontSize=10, leading=14,
        textColor=HexColor('#64748B'), alignment=TA_CENTER)
    add('CoverLabel',    fontName='Helvetica-Bold',   fontSize=9,  leading=12,
        textColor=CYAN, alignment=TA_CENTER, spaceAfter=4)

    # Body headings
    add('H1', fontName='Helvetica-Bold', fontSize=16, leading=22,
        textColor=NAVY, spaceBefore=18, spaceAfter=8,
        borderPadding=(0,0,4,0))
    add('H2', fontName='Helvetica-Bold', fontSize=13, leading=18,
        textColor=BRAND, spaceBefore=14, spaceAfter=6)
    add('H3', fontName='Helvetica-Bold', fontSize=11, leading=15,
        textColor=SLATE, spaceBefore=10, spaceAfter=4)

    # Body text
    add('Body', fontName='Helvetica', fontSize=9.5, leading=14,
        textColor=SLATE, spaceAfter=6, alignment=TA_JUSTIFY)
    add('BodyBold', fontName='Helvetica-Bold', fontSize=9.5, leading=14,
        textColor=SLATE, spaceAfter=6)
    add('Small', fontName='Helvetica', fontSize=8.5, leading=12,
        textColor=DGRAY, spaceAfter=4)

    # Table cells
    add('TH', fontName='Helvetica-Bold', fontSize=8.5, leading=11,
        textColor=WHITE, alignment=TA_CENTER)
    add('TD', fontName='Helvetica', fontSize=8.5, leading=11,
        textColor=SLATE, alignment=TA_LEFT)
    add('TDC', fontName='Helvetica', fontSize=8.5, leading=11,
        textColor=SLATE, alignment=TA_CENTER)
    add('TDB', fontName='Helvetica-Bold', fontSize=8.5, leading=11,
        textColor=SLATE, alignment=TA_LEFT)

    # Code / formula
    add('CodeBlock', fontName='Courier', fontSize=8, leading=12,
        textColor=HexColor('#1E293B'), backColor=HexColor('#F8FAFC'),
        spaceAfter=4, spaceBefore=4, leftIndent=10, rightIndent=10,
        borderPadding=4)
    add('Formula', fontName='Courier-Bold', fontSize=10, leading=16,
        textColor=BRAND, alignment=TA_CENTER, spaceAfter=4, spaceBefore=6)

    # Callout
    add('Callout', fontName='Helvetica', fontSize=9, leading=13,
        textColor=NAVY, leftIndent=12, rightIndent=12, spaceBefore=4, spaceAfter=4)
    add('CalloutTitle', fontName='Helvetica-Bold', fontSize=9, leading=13,
        textColor=BRAND, leftIndent=12, rightIndent=12)

    # TOC
    add('TOCH1', fontName='Helvetica-Bold', fontSize=10, leading=16,
        textColor=NAVY, spaceAfter=2)
    add('TOCH2', fontName='Helvetica', fontSize=9, leading=14,
        textColor=DGRAY, spaceAfter=1, leftIndent=14)

    # Footer / header text
    add('Footer', fontName='Helvetica', fontSize=7.5, leading=10,
        textColor=DGRAY, alignment=TA_CENTER)
    add('FooterR', fontName='Helvetica', fontSize=7.5, leading=10,
        textColor=DGRAY, alignment=TA_RIGHT)

    # Bullet
    add('BulletItem', fontName='Helvetica', fontSize=9.5, leading=14,
        textColor=SLATE, leftIndent=14, spaceAfter=3)

    return s

# ═══════════════════════════════════════════════════════════════════════════
#  Custom Flowables
# ═══════════════════════════════════════════════════════════════════════════
class ColorRect(Flowable):
    """Solid colored rectangle as a decorative separator / banner."""
    def __init__(self, w, h, color, radius=0):
        super().__init__()
        self.w, self.h, self.color, self.radius = w, h, color, radius
    def wrap(self, aw, ah): return self.w, self.h
    def draw(self):
        self.canv.setFillColor(self.color)
        if self.radius:
            self.canv.roundRect(0, 0, self.w, self.h, self.radius, fill=1, stroke=0)
        else:
            self.canv.rect(0, 0, self.w, self.h, fill=1, stroke=0)


class SectionBanner(Flowable):
    """Full-width dark banner for section headings."""
    def __init__(self, number, title, width=BODY_W):
        super().__init__()
        self.number, self.title, self.width = number, title, width
        self.height = 28
    def wrap(self, aw, ah): return self.width, self.height
    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(NAVY)
        c.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        # Accent strip
        c.setFillColor(BRAND)
        c.roundRect(0, 0, 5, self.height, 2, fill=1, stroke=0)
        c.rect(3, 0, 2, self.height, fill=1, stroke=0)
        # Section number badge
        c.setFillColor(CYAN)
        c.roundRect(12, 5, 30, 18, 3, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(27, 10, self.number)
        # Title
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 11)
        c.drawString(50, 9, self.title)


class SubSectionBanner(Flowable):
    """Lighter banner for sub-sections."""
    def __init__(self, title, width=BODY_W):
        super().__init__()
        self.title, self.width = title, width
        self.height = 20
    def wrap(self, aw, ah): return self.width, self.height
    def draw(self):
        c = self.canv
        c.setFillColor(LGRAY)
        c.roundRect(0, 0, self.width, self.height, 3, fill=1, stroke=0)
        c.setFillColor(BRAND)
        c.roundRect(0, 0, 4, self.height, 2, fill=1, stroke=0)
        c.rect(2, 0, 2, self.height, fill=1, stroke=0)
        c.setFillColor(SLATE)
        c.setFont('Helvetica-Bold', 9.5)
        c.drawString(14, 6, self.title)


class FormulaBox(Flowable):
    """A styled box to display mathematical formulas."""
    def __init__(self, lines, width=BODY_W):
        super().__init__()
        self.lines = lines if isinstance(lines, list) else [lines]
        self.width = width
        self.height = 16 * len(self.lines) + 20
    def wrap(self, aw, ah): return self.width, self.height
    def draw(self):
        c = self.canv
        c.setFillColor(HexColor('#EFF6FF'))
        c.setStrokeColor(BRAND)
        c.setLineWidth(1.2)
        c.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=1)
        c.setFillColor(BRAND)
        c.roundRect(0, 0, 4, self.height, 2, fill=1, stroke=0)
        c.rect(2, 0, 2, self.height, fill=1, stroke=0)
        for i, line in enumerate(self.lines):
            y = self.height - 16 * (i+1) - 2
            c.setFillColor(NAVY if i == 0 else DGRAY)
            c.setFont('Courier-Bold' if i == 0 else 'Courier', 9 if i > 0 else 10)
            c.drawCentredString(self.width / 2, y, line)


# ═══════════════════════════════════════════════════════════════════════════
#  Page event callbacks
# ═══════════════════════════════════════════════════════════════════════════
class IFDoc(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(filename, pagesize=A4,
                         leftMargin=ML, rightMargin=MR,
                         topMargin=MT, bottomMargin=MB,
                         title='Isolation Forest – vousFin Technical Overview',
                         author='vousFin Smart Accountant',
                         subject='Anomaly Detection Module – FYP Documentation')
        self._page_num = 0
        self._build_templates()

    def _build_templates(self):
        # Cover frame
        cover_frame = Frame(0, 0, PW, PH, leftPadding=0, rightPadding=0,
                            topPadding=0, bottomPadding=0, id='cover')
        cover_tmpl = PageTemplate(id='Cover', frames=[cover_frame],
                                  onPage=self._cover_page)

        # Body frame
        body_frame = Frame(ML, MB, BODY_W, PH - MT - MB, id='body')
        body_tmpl = PageTemplate(id='Body', frames=[body_frame],
                                 onPage=self._body_page)

        self.addPageTemplates([cover_tmpl, body_tmpl])

    def _cover_page(self, canvas, doc):
        canvas.saveState()
        # Full dark background
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, PW, PH, fill=1, stroke=0)
        # Top accent bar
        canvas.setFillColor(BRAND)
        canvas.rect(0, PH - 6, PW, 6, fill=1, stroke=0)
        # Bottom accent bar
        canvas.setFillColor(CYAN)
        canvas.rect(0, 0, PW, 4, fill=1, stroke=0)
        # Grid pattern
        canvas.setStrokeColor(HexColor('#1E3A5F'))
        canvas.setLineWidth(0.4)
        for x in range(0, int(PW), 40):
            canvas.line(x, 0, x, PH)
        for y in range(0, int(PH), 40):
            canvas.line(0, y, PW, y)
        # Decorative circle
        canvas.setFillColor(HexColor('#0F2040'))
        canvas.circle(PW * 0.85, PH * 0.35, 130, fill=1, stroke=0)
        canvas.setFillColor(HexColor('#0D1A32'))
        canvas.circle(PW * 0.85, PH * 0.35, 90, fill=1, stroke=0)
        canvas.setStrokeColor(BRAND)
        canvas.setLineWidth(1.5)
        canvas.setDash(4, 4)
        canvas.circle(PW * 0.85, PH * 0.35, 110, fill=0, stroke=1)
        canvas.setDash()
        canvas.restoreState()

    def _body_page(self, canvas, doc):
        canvas.saveState()
        page = doc.page
        # Header rule
        canvas.setFillColor(BRAND)
        canvas.rect(ML, PH - MT + 4, BODY_W, 2, fill=1, stroke=0)
        # Header text
        canvas.setFillColor(DGRAY)
        canvas.setFont('Helvetica', 7)
        canvas.drawString(ML, PH - MT + 8, 'vousFin Smart Accountant — Anomaly Detection Module')
        canvas.drawRightString(ML + BODY_W, PH - MT + 8,
                               'Isolation Forest: Technical Overview')
        # Footer rule
        canvas.setFillColor(MGRAY)
        canvas.rect(ML, MB - 10, BODY_W, 0.5, fill=1, stroke=0)
        # Footer text
        canvas.setFillColor(DGRAY)
        canvas.setFont('Helvetica', 7.5)
        canvas.drawCentredString(PW / 2, MB - 20,
                                 'vousFin Smart Accountant  |  Anomaly Detection Module  |  FYP Technical Documentation')
        canvas.drawRightString(ML + BODY_W, MB - 20, f'Page {page}')
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, SectionBanner):
            key = f'section_{flowable.number}'
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(f'{flowable.number}  {flowable.title}',
                                      key, level=0, closed=False)
        elif isinstance(flowable, SubSectionBanner):
            key = f'sub_{flowable.title[:30].replace(" ","_")}'
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(f'  {flowable.title}', key, level=1, closed=True)


# ═══════════════════════════════════════════════════════════════════════════
#  Helper builders
# ═══════════════════════════════════════════════════════════════════════════
def hr(color=MGRAY, thickness=0.5, spaceBefore=6, spaceAfter=6):
    return HRFlowable(width='100%', thickness=thickness,
                      color=color, spaceBefore=spaceBefore, spaceAfter=spaceAfter)


def sp(h=6):
    return Spacer(1, h)


def p(text, style='Body', styles=None):
    if styles is None:
        styles = _STYLES
    return Paragraph(text, styles[style])


def bullet(items, styles=None, bullet_char='•'):
    if styles is None:
        styles = _STYLES
    return ListFlowable(
        [ListItem(Paragraph(item, styles['BulletItem']), leftIndent=20, bulletColor=BRAND)
         for item in items],
        bulletType='bullet', bulletFontName='Helvetica',
        bulletFontSize=10, leftIndent=10, spaceBefore=2, spaceAfter=4
    )


def callout(title, body_text, color=BRAND, styles=None):
    if styles is None:
        styles = _STYLES
    elements = []
    elements.append(sp(4))
    elements.append(ColorRect(BODY_W, 1, color))
    inner = [
        Paragraph(f'<b>{title}</b>', styles['CalloutTitle']),
        Paragraph(body_text, styles['Callout']),
    ]
    data = [[inner]]
    t = Table(data, colWidths=[BODY_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor('#F0F7FF')),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, BRAND),
        ('ROUNDEDCORNERS', [4]),
    ]))
    elements.append(t)
    elements.append(sp(4))
    return elements


def styled_table(headers, rows, col_widths, header_color=NAVY, styles=None, zebra=True):
    if styles is None:
        styles = _STYLES
    header_row = [Paragraph(h, styles['TH']) for h in headers]
    data = [header_row]
    for i, row in enumerate(rows):
        cells = []
        for j, cell in enumerate(row):
            if isinstance(cell, str):
                st = 'TDB' if j == 0 else 'TDC' if j > 0 else 'TD'
                cells.append(Paragraph(cell, styles['TDC'] if j > 0 else styles['TDB']))
            else:
                cells.append(cell)
        data.append(cells)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0,0), (-1,0), header_color),
        ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LGRAY] if zebra else [WHITE]),
        ('LINEBELOW', (0,0), (-1,0), 0.5, MGRAY),
        ('LINEBELOW', (0,1), (-1,-1), 0.3, MGRAY),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,0), (-1,-1), 0.5, MGRAY),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t


def code_block(text, styles=None):
    if styles is None:
        styles = _STYLES
    lines = text.strip().split('\n')
    data = [[Paragraph(line.replace(' ', '&nbsp;') if line.strip() else '&nbsp;',
                       styles['CodeBlock'])] for line in lines]
    t = Table(data, colWidths=[BODY_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.5, MGRAY),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════════
#  Cover page content
# ═══════════════════════════════════════════════════════════════════════════
def build_cover(styles):
    story = []
    story.append(sp(PH * 0.12))
    # Badge
    badge_data = [[Paragraph('MACHINE LEARNING  ·  ANOMALY DETECTION  ·  FYP DOCUMENTATION',
                              styles['CoverLabel'])]]
    badge_t = Table(badge_data, colWidths=[PW - 4*cm])
    badge_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor('#112244')),
        ('LEFTPADDING', (0,0), (-1,-1), 20),
        ('RIGHTPADDING', (0,0), (-1,-1), 20),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOX', (0,0), (-1,-1), 0.5, CYAN),
        ('ROUNDEDCORNERS', [4]),
    ]))
    story.append(badge_t)
    story.append(sp(22))

    story.append(Paragraph('Isolation Forest', styles['CoverTitle']))
    story.append(Paragraph('Anomaly Detection in vousFin', styles['CoverTitle']))
    story.append(sp(16))
    story.append(Paragraph('Technical Overview for Viva Voce Examination', styles['CoverSub']))
    story.append(sp(30))

    # Info grid
    info = [
        ['System', 'vousFin Smart Accountant — ERP for SMEs'],
        ['Module', 'AI Anomaly Detection (isolationForest.service.js)'],
        ['Algorithm', 'Isolation Forest — IEEE ICDM 2008 (Liu, Ting, Zhou)'],
        ['Implementation', 'Pure Node.js / JavaScript — No Python Dependency'],
        ['Author', 'FYP Team — Computer Science Department'],
        ['Date', 'May 2026'],
    ]
    info_data = []
    for label, value in info:
        info_data.append([
            Paragraph(f'<b><font color="#06B6D4">{label}</font></b>', styles['CoverMeta']),
            Paragraph(f'<font color="#CBD5E1">{value}</font>', styles['CoverMeta']),
        ])
    info_t = Table(info_data, colWidths=[3.5*cm, PW - 3.5*cm - 4*cm])
    info_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor('#0D1A35')),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LINEBELOW', (0,0), (-1,-2), 0.3, HexColor('#1E3A5F')),
        ('BOX', (0,0), (-1,-1), 0.5, HexColor('#1E3A5F')),
        ('ROUNDEDCORNERS', [4]),
        ('ALIGN', (0,0), (0,-1), 'RIGHT'),
        ('ALIGN', (1,0), (1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(info_t)
    story.append(sp(PH * 0.08))

    # Bottom credits
    story.append(Paragraph(
        'vousFin Smart Accountant  ·  Final Year Project  ·  Computer Science',
        styles['CoverMeta']))
    return story


# ═══════════════════════════════════════════════════════════════════════════
#  TABLE OF CONTENTS
# ═══════════════════════════════════════════════════════════════════════════
def build_toc(styles):
    story = []
    story.append(sp(8))
    toc_title_data = [[Paragraph('Table of Contents', ParagraphStyle(
        'TOCTITLE', fontName='Helvetica-Bold', fontSize=18, textColor=NAVY,
        alignment=TA_LEFT, spaceAfter=4))]]
    story.append(Table(toc_title_data, colWidths=[BODY_W]))
    story.append(ColorRect(BODY_W, 2, BRAND))
    story.append(sp(12))

    sections = [
        ('1', 'Executive Summary', ''),
        ('2', 'Dataset Used for Training & Validation', ''),
        ('3', 'What Is Isolation Forest?', ''),
        ('4', 'How Isolation Forest Works — The Algorithm', ''),
        ('5', 'Isolation Forest Parameters in vousFin', ''),
        ('6', 'Feature Engineering in vousFin', ''),
        ('7', 'Hybrid Heuristic Detection (Small Datasets)', ''),
        ('8', 'Anomaly Scoring & Classification', ''),
        ('9', 'Why Isolation Forest for vousFin?', ''),
        ('10', 'Multi-Tier Query Fallback System', ''),
        ('11', 'Detection Pipeline — End-to-End Flow', ''),
        ('12', 'Implementation Stack', ''),
        ('13', 'Academic References', ''),
    ]

    toc_data = []
    for num, title, pg in sections:
        toc_data.append([
            Paragraph(f'<b><font color="#2563EB">{num}</font></b>', styles['TOCH1']),
            Paragraph(f'<b>{title}</b>', styles['TOCH1']),
        ])
    toc_t = Table(toc_data, colWidths=[0.6*cm, BODY_W - 0.6*cm])
    toc_t.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LINEBELOW', (0,0), (-1,-1), 0.3, MGRAY),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [WHITE, LGRAY]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(toc_t)
    return story


# ═══════════════════════════════════════════════════════════════════════════
#  SECTION CONTENT
# ═══════════════════════════════════════════════════════════════════════════

def section_1(styles):
    s = []
    s.append(SectionBanner('1', 'Executive Summary'))
    s.append(sp(10))
    s.append(p(
        'The vousFin Anomaly Detection Module is a custom, pure-JavaScript implementation of the '
        '<b>Isolation Forest</b> algorithm embedded directly into the vousFin Smart Accountant backend. '
        'It automatically scans every business\'s journal entry transactions, computes a multi-dimensional '
        'anomaly score for each entry, and surfaces the most suspicious transactions to the accountant '
        'for review — without any manual rule-writing or human labelling of historical data.',
        'Body', styles))
    s.append(sp(6))
    s += callout('What the Module Does', (
        'Reads raw JournalEntry documents from MongoDB → Extracts 10 engineered features per transaction → '
        'Trains an Isolation Forest on the business\'s own live data → Scores every transaction → '
        'Classifies anomalies by severity → Saves AnomalyAlert documents → Presents results via REST API.'
    ), styles=styles)
    s.append(sp(8))

    s.append(SubSectionBanner('Why It Was Built', BODY_W))
    s.append(sp(6))
    s.append(bullet([
        'Small and medium enterprises (SMEs) rarely employ dedicated forensic auditors.',
        'Manual transaction review is time-consuming and error-prone.',
        'Traditional rule-based fraud detection fails against novel fraud patterns.',
        'SMEs have NO pre-labelled fraud history — supervised ML is therefore impossible.',
        'An unsupervised, self-calibrating system is needed that works from Day 1 with zero setup.',
    ], styles=styles))

    s.append(sp(8))
    s.append(SubSectionBanner('Key Outcomes', BODY_W))
    s.append(sp(6))
    outcomes = [
        ['Outcome', 'Value'],
        ['Algorithm', 'Isolation Forest (Liu, Ting, Zhou 2008) — 100% unsupervised'],
        ['Features per transaction', '10 engineered numerical features'],
        ['Severity tiers', '5 tiers: Normal → Low → Medium → High → Critical'],
        ['Minimum data requirement', '2 transactions (heuristic mode)'],
        ['Scheduled scanning', 'Every 6 hours via node-cron'],
        ['Average scoring latency', 'Sub-second for ≤ 500 transactions'],
        ['Implementation language', 'Pure Node.js — no Python, no ML framework'],
    ]
    s.append(styled_table(outcomes[0], outcomes[1:],
                          [5.5*cm, BODY_W - 5.5*cm], styles=styles))
    return s


def section_2(styles):
    s = []
    s.append(SectionBanner('2', 'Dataset Used for Training & Validation'))
    s.append(sp(10))

    s.append(SubSectionBanner('Unsupervised Learning — No Pre-Labelled Dataset Required', BODY_W))
    s.append(sp(6))
    s.append(p(
        '<b>Critical distinction:</b> Isolation Forest is an <b>unsupervised</b> algorithm. It does <b>NOT</b> '
        'require a pre-labelled training dataset containing fraud/non-fraud labels. Instead, it learns '
        'directly from the business\'s own live transaction data stored in MongoDB. '
        'The model is retrained fresh on every scan, using only the real JournalEntry documents '
        'belonging to that specific business.', 'Body', styles))
    s.append(sp(4))

    s.append(p(
        '<b>Training dataset source:</b> JournalEntry documents from the vousFin MongoDB database. '
        'Each document represents a real accounting transaction recorded by the SME, '
        'containing fields such as: amount, date, transactionType, transactionMode, '
        'debitAccountId, creditAccountId, description, status, and createdAt timestamp.',
        'Body', styles))
    s.append(sp(8))

    s.append(SubSectionBanner('Reference Datasets (Feature Engineering Inspiration)', BODY_W))
    s.append(sp(6))
    s.append(p(
        'The following publicly available datasets were used as benchmarks for anomaly feature design '
        'and to validate the scoring framework against known fraud patterns:', 'Body', styles))
    s.append(sp(4))

    ref_data = [
        ['Dataset', 'Source', 'Scale', 'Use in vousFin'],
        ['Credit Card Fraud Detection',
         'ML Group, Université Libre de Bruxelles (ULB)\nkaggle.com/datasets/mlg-ulb/creditcardfraud',
         '284,807 txns\n492 frauds (0.172%)\n30 PCA features',
         'Primary benchmark for anomaly scoring calibration and feature engineering direction'],
        ['PaySim Synthetic Mobile Money',
         'NTNU / Lopez-Rojas\nkaggle.com/datasets/ealaxi/paysim1',
         'Synthetic mobile\nmoney simulation\n6.3M transactions',
         'Validates transaction velocity and amount-pattern features'],
        ['IEEE-CIS Fraud Detection',
         'Vesta Corporation / IEEE-CIS\nkaggle.com/c/ieee-fraud-detection',
         'Real-world e-commerce\nfraud labels\n590k transactions',
         'Cross-validates account-pair rarity and timing anomaly signals'],
    ]
    cw = [3.8*cm, 5.0*cm, 3.4*cm, BODY_W - 12.2*cm]
    s.append(styled_table(ref_data[0], ref_data[1:], cw, styles=styles))
    s.append(sp(8))

    s.append(SubSectionBanner('Why vousFin Uses Its Own Live Data', BODY_W))
    s.append(sp(6))
    s.append(bullet([
        '<b>Personalised baseline:</b> The model learns what is "normal" for each specific business, '
        'not what is normal in an unrelated global dataset.',
        '<b>Zero cold-start problem:</b> Even with 5 transactions the model can produce meaningful scores '
        'through the hybrid heuristic fallback.',
        '<b>Adaptive:</b> As the business records more transactions, the model\'s baseline improves automatically.',
        '<b>Privacy-preserving:</b> Transaction data never leaves the business\'s MongoDB cluster.',
        '<b>No manual labelling:</b> The accountant never needs to tag transactions as fraud/non-fraud — '
        'the algorithm is fully autonomous.',
    ], styles=styles))
    return s


def section_3(styles):
    s = []
    s.append(SectionBanner('3', 'What Is Isolation Forest?'))
    s.append(sp(10))

    s.append(p(
        'Isolation Forest is a machine learning algorithm for anomaly detection, invented by '
        '<b>Fei Tony Liu, Kai Ming Ting, and Zhi-Hua Zhou</b> and published at the '
        '<b>IEEE International Conference on Data Mining (ICDM) in 2008</b>. '
        'It is now one of the most widely adopted unsupervised anomaly detection algorithms '
        'in production systems globally, implemented in scikit-learn, Apache Spark, and many '
        'commercial fraud detection platforms.', 'Body', styles))
    s.append(sp(6))

    s.append(SubSectionBanner('Core Idea', BODY_W))
    s.append(sp(6))
    s += callout('Fundamental Insight',
        '"Anomalies are few and different — they are easier to ISOLATE than normal points." '
        'Normal data points cluster together and require many random partitions to isolate. '
        'Anomalous data points are structurally different from the majority and are isolated '
        'in very few partitions.',
        color=PURPLE, styles=styles)
    s.append(sp(6))

    s.append(SubSectionBanner('Key Insight: Path Length as Anomaly Indicator', BODY_W))
    s.append(sp(6))
    s.append(p(
        'When we randomly partition a feature space by selecting a random attribute and a random '
        'split value, <b>anomalous points reach leaf nodes (isolation) much faster</b> than normal '
        'points. This means anomalies have shorter average path lengths in isolation trees. '
        'The algorithm exploits this property directly — no density estimation, no distance '
        'calculation, no assumption about the shape of the normal distribution.',
        'Body', styles))
    s.append(sp(6))

    s.append(SubSectionBanner('Contrast With Other Anomaly Detection Approaches', BODY_W))
    s.append(sp(6))
    comp_data = [
        ['Approach', 'Strategy', 'Weakness vs. IF'],
        ['Isolation Forest', 'Directly isolates anomalies via random partitions', '— (the reference)'],
        ['LOF (Local Outlier Factor)', 'Density estimation — compares point density to neighbours',
         'O(n²) complexity; fails in high dimensions'],
        ['DBSCAN', 'Density-based clustering; outliers are unclustered points',
         'Sensitive to ε and minPts; not probabilistic'],
        ['k-NN Distance', 'Distance to k-th nearest neighbour as anomaly score',
         'O(n²) query; poor in high dimensions'],
        ['Autoencoder (Deep Learning)', 'Reconstructs input; high reconstruction error = anomaly',
         'Requires large dataset; black-box; slow'],
        ['One-Class SVM', 'Learns a hypersphere around normal data',
         'Sensitive to hyperparameters; poor scalability'],
    ]
    cw = [3.6*cm, 7.2*cm, BODY_W - 10.8*cm]
    s.append(styled_table(comp_data[0], comp_data[1:], cw, styles=styles))
    s.append(sp(6))

    s.append(SubSectionBanner('Critical Distinction: Does NOT Model Normal First', BODY_W))
    s.append(sp(6))
    s.append(p(
        'Most anomaly detection algorithms first build a model of "normal" behaviour (a density '
        'estimate, a cluster, a reconstruction model) and then flag deviations from it. '
        'Isolation Forest takes the <b>opposite approach</b>: it directly targets anomalies by '
        'asking "how quickly can this point be isolated?" This means it works well even when '
        'the normal distribution is complex, multimodal, or unknown — which is exactly the '
        'case for SME accounting transactions.', 'Body', styles))
    return s


def section_4(styles):
    s = []
    s.append(SectionBanner('4', 'How Isolation Forest Works — The Algorithm'))
    s.append(sp(10))

    s.append(SubSectionBanner('Step 1 — Random Subsampling', BODY_W))
    s.append(sp(6))
    s.append(p(
        'Draw <i>t</i> random subsamples, each of size <b>ψ (psi)</b>, from the full dataset. '
        'A typical default is ψ = 256. Using subsamples rather than the full dataset is intentional: '
        'it reduces noise from normal-cluster swamping and dramatically improves training speed. '
        'In vousFin, ψ = min(256, n) where n is the total transaction count for that business.',
        'Body', styles))

    s.append(sp(8))
    s.append(SubSectionBanner('Step 2 — Build Isolation Trees (iTrees)', BODY_W))
    s.append(sp(6))
    s.append(p(
        'For each subsample of size ψ, build one <b>isolation tree (iTree)</b> as follows:',
        'Body', styles))
    s.append(bullet([
        'If the current node contains only 1 point, it is a leaf node (point isolated).',
        'If the node has more than 1 point:',
        '  → Randomly select a feature <i>q</i> from all available features.',
        '  → Randomly select a split value <i>p</i> uniformly between min(q) and max(q) in current node.',
        '  → Partition: points where q < p go left; points where q ≥ p go right.',
        '  → Recurse on left and right subsets.',
        'Stop recursion when the node has 1 point OR depth ≥ ceil(log₂(ψ)) — the depth limit.',
        'A forest of <i>t</i> = 50–100 such trees is built (one per subsample).',
    ], styles=styles))

    s.append(sp(8))
    s.append(SubSectionBanner('Step 3 — Path Length Measurement', BODY_W))
    s.append(sp(6))
    s.append(p(
        'For a new test point <b>x</b>, pass it through every iTree in the forest. '
        'For each tree, count the number of edges traversed from root to the leaf node where '
        'x is isolated. This count is the <b>path length h(x)</b> for that tree. '
        'A short path length means x was isolated very quickly, suggesting it is anomalous.',
        'Body', styles))

    s.append(sp(8))
    s.append(SubSectionBanner('Step 4 — Anomaly Score Calculation', BODY_W))
    s.append(sp(6))
    s.append(p(
        'The raw path lengths are averaged across all <i>t</i> trees to get <b>E[h(x)]</b>. '
        'This average is then normalised by the expected path length of a Binary Search Tree '
        'with n nodes, denoted <b>c(n)</b>. The normalisation ensures scores are comparable '
        'across datasets of different sizes.', 'Body', styles))
    s.append(sp(6))

    s.append(FormulaBox([
        's(x, n)  =  2^( −E[h(x)] / c(n) )',
        'where:',
        'h(x)     = path length of point x in one isolation tree',
        'E[h(x)]  = average path length across all t trees',
        'c(n)     = 2·(ln(n−1) + 0.5772156649) − (2·(n−1)/n)',
        'n        = number of training samples (subsample size ψ)',
        '0.5772156649 = Euler–Mascheroni constant (γ)',
    ], BODY_W))
    s.append(sp(8))

    score_data = [
        ['Score Range', 'Interpretation', 'Action'],
        ['~1.0  (close to 1)', 'Highly anomalous — isolated in very few splits', 'Flag as anomaly'],
        ['~0.5  (close to 0.5)', 'Normal — requires average number of splits', 'No action'],
        ['~0.0  (close to 0)', 'Definitely normal — deeply embedded in dense region', 'No action'],
    ]
    s.append(styled_table(score_data[0], score_data[1:],
                          [3.8*cm, 8.0*cm, BODY_W - 11.8*cm], styles=styles))
    s.append(sp(8))

    s.append(SubSectionBanner('Step 5 — Thresholding', BODY_W))
    s.append(sp(6))
    s.append(p(
        'Points whose anomaly score exceeds a <b>threshold</b> are flagged as anomalous. '
        'In vousFin, this threshold is adaptive based on the dataset size: '
        '<b>0.44</b> for fewer than 10 transactions, <b>0.50</b> for 10–19 transactions, '
        'and <b>0.54</b> for 20 or more transactions. '
        'Higher thresholds reduce false positives in larger, well-distributed datasets.',
        'Body', styles))
    return s


def section_5(styles):
    s = []
    s.append(SectionBanner('5', 'Isolation Forest Parameters in vousFin'))
    s.append(sp(10))

    param_data = [
        ['Parameter', 'Value in vousFin', 'Rationale'],
        ['num_trees (t)', '50 trees (small dataset)\n100 trees (large dataset)',
         'More trees → more stable average; 100 trees provides excellent stability for ≥20 txns'],
        ['sample_size (ψ)', 'min(256, n) — uses all data when n < 256',
         'Classical default; for small SME datasets, all data is used to avoid information loss'],
        ['max_depth', 'ceil(log₂(sample_size))',
         'Theoretical optimal — guarantees isolation within expected BST depth'],
        ['contamination', 'Adaptive: 0.44 (<10), 0.50 (10–19), 0.54 (≥20)',
         'Higher threshold when more data = more reliable scores; reduces false positives'],
        ['Hybrid mode', 'Active when n < 20',
         'Blends Isolation Forest scores with heuristic rule scores for small datasets'],
        ['Pure heuristic mode', 'Active when n < 5',
         'Uses only heuristic scoring — too little data for statistical IF to be meaningful'],
    ]
    cw = [4.0*cm, 5.5*cm, BODY_W - 9.5*cm]
    s.append(styled_table(param_data[0], param_data[1:], cw, styles=styles))
    s.append(sp(8))

    s += callout('Adaptive Contamination',
        'The contamination parameter is not a fixed rate of fraud — it is the anomaly score '
        'threshold above which a transaction is flagged. vousFin adapts this threshold based '
        'on dataset size because: with few transactions, the IF score distribution is wider and '
        'noisier, so a lower threshold would produce excessive false positives. With more '
        'transactions the score distribution stabilises, allowing a stricter threshold.',
        color=GREEN, styles=styles)
    return s


def section_6(styles):
    s = []
    s.append(SectionBanner('6', 'Feature Engineering in vousFin'))
    s.append(sp(10))
    s.append(p(
        'Each JournalEntry transaction is transformed into a <b>10-dimensional feature vector</b> '
        'before being passed to the Isolation Forest. These features capture amount magnitude, '
        'temporal patterns, transaction semantics, and network rarity — dimensions that collectively '
        'characterise the "fingerprint" of suspicious transactions.', 'Body', styles))
    s.append(sp(6))

    feat_data = [
        ['#', 'Feature Name', 'Formula / Computation', 'Anomaly Signal'],
        ['1', 'logAmount', 'log(amount + 1)',
         'Captures magnitude scale without extreme value dominance'],
        ['2', 'amountZScore', '(amount − μ) / σ  (clamped to ±5)',
         'Standard deviations from mean — extreme outlier detection'],
        ['3', 'dayOfWeek', 'dayOfWeek / 6  (0=Sun → 1=Sat)',
         'Weekend entries unusual for B2B accounting'],
        ['4', 'hourOfDay', 'hour / 23  (0–1 normalised)',
         'Off-hours recording: midnight, 3 AM entries'],
        ['5', 'monthOfYear', '(month − 1) / 11  (0–1 normalised)',
         'Seasonal anomalies — end-of-quarter clustering'],
        ['6', 'normalizedDate', '(txDate − minDate) / (maxDate − minDate)',
         'Temporal isolation — clusters of sudden entries'],
        ['7', 'transactionTypeIdx', 'TypeIndex / 12  (Income=0, Expense=1, …)',
         'Unusual transaction type for account category'],
        ['8', 'transactionModeIdx', 'cash=0, credit=1, installment=2, partial=3  / 3',
         'Unusual payment mode (cash for large B2B)'],
        ['9', 'accountPairRarity', '1 − (pairFrequency / totalTransactions)',
         'Rare account combinations score near 1.0'],
        ['10', 'dailyVelocity', 'dailyTxCount / avgDailyCount',
         'Unusual burst: 10 entries in one day vs 1/day normal'],
    ]
    cw = [0.5*cm, 3.2*cm, 5.8*cm, BODY_W - 9.5*cm]
    s.append(styled_table(feat_data[0], feat_data[1:], cw, styles=styles))
    s.append(sp(8))

    s.append(SubSectionBanner('Why These Features?', BODY_W))
    s.append(sp(6))
    s.append(bullet([
        '<b>logAmount:</b> Raw amounts can range from PKR 50 to PKR 50,000,000. Log transformation '
        'prevents large-amount transactions from overwhelming all other features.',
        '<b>amountZScore:</b> Complements logAmount by expressing deviation relative to the '
        'business\'s own average — calibrated per business.',
        '<b>Temporal features (dayOfWeek, hourOfDay, monthOfYear):</b> Fraudulent entries are '
        'disproportionately recorded outside business hours or on weekends when oversight is minimal.',
        '<b>accountPairRarity:</b> Legitimate businesses use the same account combinations repeatedly. '
        'A transaction using an account pair that has never appeared before is highly suspicious.',
        '<b>dailyVelocity:</b> Velocity bursts — recording 20 transactions in one hour — are a '
        'classic indicator of backdating, data fabrication, or automated fraud.',
    ], styles=styles))
    return s


def section_7(styles):
    s = []
    s.append(SectionBanner('7', 'Hybrid Heuristic Detection (For Small Datasets)'))
    s.append(sp(10))
    s.append(p(
        'When a business has fewer than 20 transactions, there is insufficient data for the '
        'Isolation Forest\'s statistical model to produce reliable scores. In this mode, '
        'vousFin activates a <b>Hybrid Heuristic Detector</b> that blends IF scores with '
        'deterministic rule-based score boosts. For businesses with fewer than 5 transactions, '
        'the system uses <b>pure heuristic mode</b> — rules only.', 'Body', styles))
    s.append(sp(6))

    rule_data = [
        ['Rule', 'Trigger Condition', 'Score Boost', 'Rationale'],
        ['Extreme Amount', 'Z-score > 3.5σ above mean', '+0.45',
         'Statistical extreme outlier — very likely data entry error or fraud'],
        ['High Amount', 'Z-score > 2.5σ above mean', '+0.30',
         'Significant positive deviation from business average'],
        ['Elevated Amount', 'Z-score > 1.8σ above mean', '+0.15',
         'Above normal range — warrants review'],
        ['Off-Hours Entry', 'Hour < 6 AM or Hour ≥ 23 (11 PM)', '+0.15',
         'Entry recorded outside typical business hours'],
        ['Weekend Transaction', 'Saturday or Sunday', '+0.08',
         'Most B2B transactions occur on weekdays'],
        ['Round Large Amount', 'Amount ≥ PKR 500,000 AND divisible by 100,000', '+0.15',
         'Structuring pattern — artificially rounded large sums'],
        ['Micro Transaction', 'Amount < PKR 50', '+0.28',
         'Test transaction or structuring — artificially small probe entry'],
    ]
    cw = [3.0*cm, 4.2*cm, 2.0*cm, BODY_W - 9.2*cm]
    s.append(styled_table(rule_data[0], rule_data[1:], cw, styles=styles))
    s.append(sp(8))

    s += callout('Hybrid Score Blending',
        'Final score (hybrid mode) = 0.6 × IsolationForestScore + 0.4 × HeuristicScore. '
        'This weighting ensures that even with sparse data, both the statistical model and '
        'the deterministic rules contribute meaningfully to the final verdict. '
        'The heuristic boosts are additive and capped at 1.0.',
        color=AMBER, styles=styles)
    return s


def section_8(styles):
    s = []
    s.append(SectionBanner('8', 'Anomaly Scoring & Classification'))
    s.append(sp(10))
    s.append(p(
        'The raw Isolation Forest score (0.0 – 1.0) is scaled to an integer <b>0–100</b> '
        'for display. This 0–100 score is then mapped to one of five severity tiers, '
        'each with a corresponding fraud risk label and UI badge colour.',
        'Body', styles))
    s.append(sp(6))

    score_data = [
        ['Score Range\n(0–100)', 'Severity Tier', 'Fraud Risk', 'UI Status Label', 'UI Badge Color'],
        ['0 – 43', 'Normal', 'Low', 'Normal', 'Grey'],
        ['44 – 53', 'Low Anomaly', 'Low', 'Suspicious', 'Yellow'],
        ['54 – 67', 'Medium Anomaly', 'Medium', 'Suspicious', 'Amber / Orange'],
        ['68 – 81', 'High Anomaly', 'High', 'Highly Suspicious', 'Orange / Red'],
        ['82 – 100', 'Critical Anomaly', 'Critical', 'Potentially Fraudulent', 'Red'],
    ]
    cw = [2.2*cm, 3.0*cm, 2.2*cm, 4.0*cm, BODY_W - 11.4*cm]
    s.append(styled_table(score_data[0], score_data[1:], cw, styles=styles))
    s.append(sp(8))

    s.append(SubSectionBanner('Anomaly Alert Document Schema (MongoDB)', BODY_W))
    s.append(sp(6))
    schema = '''\
{
  transactionId:  ObjectId,           // Reference to JournalEntry
  businessId:     ObjectId,           // Business owner
  score:          Number (0-100),     // Scaled anomaly score
  severity:       String,             // "Low" | "Medium" | "High" | "Critical"
  fraudRisk:      String,             // "Low" | "Medium" | "High" | "Critical"
  status:         String,             // "Suspicious" | "Highly Suspicious" | "Potentially Fraudulent"
  reasons:        [String],           // Human-readable explanation array
  rawScore:       Number (0.0-1.0),   // Original IF score
  isReviewed:     Boolean,            // Has accountant reviewed?
  reviewedAt:     Date,
  reviewNotes:    String,
  scanId:         String,             // UUID for the scan run
  detectedAt:     Date,               // Timestamp of detection
}'''
    s.append(code_block(schema, styles))
    s.append(sp(6))

    s += callout('Reasons Array',
        'Each flagged transaction includes a human-readable "reasons" array explaining '
        'why it was flagged. Examples: ["Amount is 4.2σ above business average", '
        '"Recorded at 2:34 AM — unusual off-hours entry", '
        '"Account pair (Cash → Suspense) has never appeared before"]. '
        'This transparency is essential for accountant review and audit trail documentation.',
        color=CYAN, styles=styles)
    return s


def section_9(styles):
    s = []
    s.append(SectionBanner('9', 'Why Isolation Forest for vousFin?'))
    s.append(sp(10))

    s.append(SubSectionBanner('9.1  Unsupervised Learning Advantage', BODY_W))
    s.append(sp(6))
    s.append(bullet([
        'SMEs have <b>NO labelled fraud data</b> — they have never tagged transactions as "fraud".',
        'No historical fraud labels are available for new business accounts.',
        'Supervised algorithms (Random Forest, XGBoost, Neural Networks) cannot be trained '
        'without positive fraud examples.',
        'Isolation Forest works entirely <b>without any labels</b> — perfect for cold-start SME scenarios.',
        'Every business starts with a clean, personalised model — no shared global model needed.',
    ], styles=styles))

    s.append(sp(8))
    s.append(SubSectionBanner('9.2  Computational Efficiency', BODY_W))
    s.append(sp(6))
    eff_data = [
        ['Operation', 'Complexity', 'Practical Impact'],
        ['Training (building t trees)', 'O(t · ψ · log ψ)', 'Sub-second for ψ=256, t=100'],
        ['Scoring one transaction', 'O(t · log ψ)', 'Microseconds per transaction'],
        ['Full scan (n transactions)', 'O(t · n · log ψ)', 'Sub-second for n≤500'],
        ['Memory footprint', 'O(t · ψ)', 'Proportional to subsample, not full dataset'],
    ]
    cw = [4.2*cm, 3.8*cm, BODY_W - 8.0*cm]
    s.append(styled_table(eff_data[0], eff_data[1:], cw, styles=styles))

    s.append(sp(8))
    s.append(SubSectionBanner('9.3  Handles Unknown and Novel Fraud Patterns', BODY_W))
    s.append(sp(6))
    s.append(bullet([
        'Does <b>not</b> require prior knowledge of what fraud looks like.',
        'Detects novel, previously unseen anomaly patterns.',
        'Fraud techniques evolve — new forms of fraud are automatically detectable as long as '
        'they manifest as statistical outliers.',
        'Rule-based systems fail against novel patterns; IF adapts automatically.',
    ], styles=styles))

    s.append(sp(8))
    s.append(SubSectionBanner('9.4  Comparison Table — Why NOT Other Algorithms', BODY_W))
    s.append(sp(6))
    why_not = [
        ['Algorithm', 'Why NOT Chosen for vousFin'],
        ['Autoencoder (Deep Learning)',
         'Requires large labelled dataset; high computational cost; GPU preferred; '
         'black-box with no interpretable reason output; overkill for SME transaction counts'],
        ['One-Class SVM',
         'Sensitive to hyperparameters (ν, γ, kernel); poor scalability O(n²)–O(n³); '
         'requires feature scaling; slow prediction in high dimensions'],
        ['LOF (Local Outlier Factor)',
         'O(n²) time complexity; degrades severely in high-dimensional spaces; '
         'no probabilistic output; cannot handle concept drift without full retraining'],
        ['Statistical Z-Score Only',
         'Assumes normality; single-feature; completely misses multivariate patterns '
         '(e.g., normal amount + unusual time + rare account pair)'],
        ['K-Means Anomaly Detection',
         'Requires knowing number of clusters k in advance; sensitive to random init; '
         'distance-to-centroid not calibrated as anomaly probability'],
        ['Random Forest (Supervised)',
         'Requires labelled fraud examples — impossible for new SMEs with zero fraud history; '
         'label imbalance (fraud is rare) causes severe bias without sophisticated resampling'],
        ['DBSCAN Clustering',
         'Parameters ε and minPts extremely sensitive; fails in varying density regions; '
         'no online update; core/border/noise classification not probabilistic'],
    ]
    cw = [4.2*cm, BODY_W - 4.2*cm]
    s.append(styled_table(why_not[0], why_not[1:], cw, styles=styles))

    s.append(sp(8))
    s.append(SubSectionBanner('9.5  Specific vousFin Advantages', BODY_W))
    s.append(sp(6))
    s.append(bullet([
        '<b>Trains on each business\'s OWN data</b> → personalised normal behaviour baseline.',
        '<b>Works with as few as 5 transactions</b> → suitable for brand-new SME accounts.',
        '<b>Adaptive contamination factor</b> → threshold adjusts to dataset size automatically.',
        '<b>Hybrid heuristic fallback</b> → produces meaningful results even for 2 transactions.',
        '<b>No external model file</b> → model is rebuilt fresh each scan using live DB data.',
        '<b>Human-readable reasons</b> → accountant knows exactly why a transaction was flagged.',
        '<b>Pure JavaScript implementation</b> → no Python runtime, no model serialisation, '
        'no inter-process communication overhead.',
    ], styles=styles))
    return s


def section_10(styles):
    s = []
    s.append(SectionBanner('10', 'Multi-Tier Query Fallback System'))
    s.append(sp(10))
    s.append(p(
        'To ensure no business is skipped due to data staleness or status mismatches, '
        'vousFin implements a <b>3-tier fallback query system</b> for fetching transactions '
        'before each scan. Each tier is tried sequentially until a non-empty result set '
        'is obtained.', 'Body', styles))
    s.append(sp(6))

    tier_data = [
        ['Tier', 'Query Scope', 'Status Filter', 'Purpose'],
        ['Tier 1 (Strictest)',
         'Last 90 days',
         'posted, settled, partially_settled',
         'Captures only verified, finalised transactions — most reliable data quality'],
        ['Tier 2',
         'Last 90 days',
         'Any status (no filter)',
         'Catches draft, pending, and overdue transactions not yet finalised'],
        ['Tier 3 (Most Permissive)',
         'All-time (no date limit)',
         'Any status',
         'Catches businesses whose entire transaction history predates the 90-day window'],
    ]
    cw = [2.2*cm, 2.8*cm, 4.2*cm, BODY_W - 9.2*cm]
    s.append(styled_table(tier_data[0], tier_data[1:], cw, styles=styles))
    s.append(sp(8))

    s += callout('Why 3 Tiers?',
        'A new SME might record all their transactions historically in one batch. '
        'If all entries are dated 6 months ago, Tier 1 returns 0 results. '
        'Tier 3 ensures these businesses are never skipped. '
        'This guarantees that even a business with exactly 2 total transactions '
        'receives at least a heuristic-mode scan.',
        color=GREEN, styles=styles)
    return s


def section_11(styles):
    s = []
    s.append(SectionBanner('11', 'Detection Pipeline — End-to-End Flow'))
    s.append(sp(10))

    steps = [
        ('1', 'User Trigger',
         'User clicks "Run Scan" on the Anomaly Detection page. '
         'Frontend sends POST /api/v1/ai/anomaly-scan with businessId.'),
        ('2', 'Transaction Fetch',
         'Backend executes the 3-tier fallback query against MongoDB JournalEntry collection. '
         'Returns up to all transactions matching the business, ordered by date descending.'),
        ('3', 'Feature Extraction',
         'For each transaction, compute the 10-feature vector: '
         '[logAmount, amountZScore, dayOfWeek, hourOfDay, monthOfYear, normalizedDate, '
         'transactionTypeIdx, transactionModeIdx, accountPairRarity, dailyVelocity].'),
        ('4', 'Model Selection',
         'n ≥ 20 → Full Isolation Forest (t=100 trees). '
         '5 ≤ n < 20 → Hybrid mode (0.6×IF + 0.4×Heuristic). '
         'n < 5 → Pure heuristic mode. '),
        ('5', 'Model Training',
         'Isolation Forest trains on the feature matrix using t random subsamples of size ψ. '
         'Each iTree built by recursive random partitioning to depth ceil(log₂(ψ)).'),
        ('6', 'Scoring',
         'Each transaction scored: s(x,n) = 2^(−E[h(x)] / c(n)). '
         'Score scaled to 0–100 integer. Reasons array populated from feature analysis.'),
        ('7', 'Threshold Application',
         'Adaptive threshold applied: 0.44 (<10 txns), 0.50 (10–19), 0.54 (≥20). '
         'Transactions above threshold are flagged as anomalies.'),
        ('8', 'Alert Persistence',
         'Each flagged transaction saved as AnomalyAlert document in MongoDB '
         'with score, severity, fraudRisk, reasons, scanId, detectedAt.'),
        ('9', 'Response',
         'API returns: { anomalies: [...], totalScanned: n, anomaliesFound: k, '
         'scanId: uuid, message: "Scan complete." }'),
        ('10', 'Frontend Display',
         'React frontend renders: score badges (colour-coded), severity chips, '
         'fraud risk level, reasons list, Review / Dismiss action buttons.'),
    ]

    step_data = [[
        Paragraph(f'<b><font color="#FFFFFF">{num}</font></b>', ParagraphStyle(
            'StepNum', fontName='Helvetica-Bold', fontSize=9, textColor=WHITE, alignment=TA_CENTER)),
        [Paragraph(f'<b>{title}</b>', styles['BodyBold']),
         Paragraph(desc, styles['Body'])],
    ] for num, title, desc in steps]

    t = Table(step_data, colWidths=[0.8*cm, BODY_W - 0.8*cm])
    style_cmds = [
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (0,-1), 3),
        ('RIGHTPADDING', (0,0), (0,-1), 3),
        ('LEFTPADDING', (1,0), (1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-2), 0.3, MGRAY),
    ]
    # Alternating row backgrounds
    for i in range(len(steps)):
        bg = HexColor('#F0F7FF') if i % 2 == 0 else WHITE
        style_cmds.append(('BACKGROUND', (1,i), (1,i), bg))
        style_cmds.append(('BACKGROUND', (0,i), (0,i), BRAND))
    t.setStyle(TableStyle(style_cmds))
    s.append(t)
    return s


def section_12(styles):
    s = []
    s.append(SectionBanner('12', 'Implementation Stack'))
    s.append(sp(10))

    stack_data = [
        ['Layer', 'Technology', 'Role'],
        ['Runtime', 'Node.js 20 LTS', 'Server runtime — no Python dependency'],
        ['Web Framework', 'Express.js 4', 'REST API server'],
        ['ML Algorithm', 'Custom pure-JS Isolation Forest',
         'Implemented in isolationForest.service.js'],
        ['Database', 'MongoDB 7 + Mongoose ODM', 'JournalEntry + AnomalyAlert storage'],
        ['Frontend', 'React 19 + Vite 8', 'UI for scan results and anomaly review'],
        ['State Management', 'Zustand 5', 'Alert state, scan status'],
        ['Data Fetching', 'TanStack Query 5', 'API caching, refetch on scan completion'],
        ['Scheduling', 'node-cron', 'Background scan every 6 hours (0 */6 * * *)'],
        ['Feature Engineering', 'anomalyDetection.service.js', 'Computes 10-feature vector per transaction'],
        ['Styling', 'Tailwind CSS 3.4', 'Severity badge colours, score visualisation'],
    ]
    cw = [2.6*cm, 4.0*cm, BODY_W - 6.6*cm]
    s.append(styled_table(stack_data[0], stack_data[1:], cw, styles=styles))
    s.append(sp(8))

    s.append(SubSectionBanner('Key Source Files', BODY_W))
    s.append(sp(6))
    file_data = [
        ['File', 'Purpose'],
        ['services/isolationForest.service.js',
         'Core Isolation Forest implementation: iTree building, path length scoring, '
         'anomaly score formula, forest ensemble'],
        ['services/anomalyDetection.service.js',
         'Feature engineering (10 features), model selection logic, '
         'hybrid mode blending, alert persistence'],
        ['services/anomalyAlert.service.js',
         'CRUD for AnomalyAlert documents: create, list, mark reviewed, dismiss'],
        ['routes/ai.routes.js',
         'REST endpoints: POST /anomaly-scan, GET /anomaly-alerts, PATCH /anomaly-alerts/:id'],
        ['models/AnomalyAlert.model.js',
         'Mongoose schema for anomaly alert documents with all scoring metadata'],
        ['src/pages/ai/AnomalyDetectionPage.jsx',
         'React page: trigger scan, display alerts table, score badges, review modals'],
        ['src/hooks/useAnomalyAlerts.js',
         'TanStack Query hook for fetching and mutating anomaly alerts'],
    ]
    cw = [5.5*cm, BODY_W - 5.5*cm]
    s.append(styled_table(file_data[0], file_data[1:], cw, styles=styles))
    s.append(sp(8))

    s.append(SubSectionBanner('Scheduled Automatic Scanning', BODY_W))
    s.append(sp(6))
    s += callout('node-cron Schedule',
        'The anomaly detection engine runs automatically every 6 hours for ALL active businesses: '
        'cron.schedule("0 */6 * * *", async () => { await anomalyDetectionService.scanAllBusinesses(); }). '
        'This ensures continuous monitoring without requiring manual user action. '
        'Users may also trigger an on-demand scan at any time via the UI.',
        color=PURPLE, styles=styles)
    return s


def section_13(styles):
    s = []
    s.append(SectionBanner('13', 'Academic References'))
    s.append(sp(10))

    refs = [
        ('[1]', 'Liu, F.T., Ting, K.M., Zhou, Z.H. (2008). "Isolation Forest." '
         '<i>Eighth IEEE International Conference on Data Mining (ICDM 2008)</i>, pp. 413–422. '
         'DOI: 10.1109/ICDM.2008.17',
         'Primary: Original Isolation Forest paper — algorithm, proof, complexity analysis.'),
        ('[2]', 'Liu, F.T., Ting, K.M., Zhou, Z.H. (2012). "Isolation-Based Anomaly Detection." '
         '<i>ACM Transactions on Knowledge Discovery from Data</i>, 6(1), Article 3. '
         'DOI: 10.1145/2133360.2133363',
         'Extended journal version: formal scoring formula derivation, c(n) proof.'),
        ('[3]', 'Dal Pozzolo, A., Caelen, O., Johnson, R.A., Bontempi, G. (2015). '
         '"Calibrating probability with undersampling for unbalanced classification." '
         '<i>IEEE Symposium Series on Computational Intelligence (SSCI)</i>. '
         'Credit Card Fraud Dataset, Université Libre de Bruxelles (ULB).',
         'Dataset: Credit Card Fraud Detection — feature engineering benchmark.'),
        ('[4]', 'Lopez-Rojas, E., Elmir, A., Axelsson, S. (2016). "PaySim: A financial mobile '
         'money simulator for fraud detection." <i>28th European Modeling and Simulation Symposium</i>. '
         'kaggle.com/datasets/ealaxi/paysim1',
         'Dataset: PaySim — validates transaction velocity and amount pattern features.'),
        ('[5]', 'Breunig, M.M., Kriegel, H.P., Ng, R.T., Sander, J. (2000). "LOF: Identifying '
         'Density-Based Local Outliers." <i>ACM SIGMOD Conference</i>, pp. 93–104.',
         'Comparison: LOF algorithm — contrasted with Isolation Forest in Section 3.'),
        ('[6]', 'Chandola, V., Banerjee, A., Kumar, V. (2009). "Anomaly Detection: A Survey." '
         '<i>ACM Computing Surveys</i>, 41(3), Article 15. DOI: 10.1145/1541880.1541882',
         'Survey: Comprehensive taxonomy of anomaly detection methods — contextual framing.'),
        ('[7]', 'Pedregosa, F., et al. (2011). "Scikit-learn: Machine Learning in Python." '
         '<i>Journal of Machine Learning Research</i>, 12, pp. 2825–2830.',
         'Reference: sklearn IsolationForest implementation — algorithm validation reference.'),
        ('[8]', 'IEEE Computational Intelligence Society. (2019). "IEEE-CIS Fraud Detection." '
         'Kaggle Competition Dataset. kaggle.com/c/ieee-fraud-detection',
         'Dataset: Real-world e-commerce fraud — cross-validates account-pair rarity signal.'),
    ]

    for ref_num, citation, note in refs:
        ref_data = [[
            Paragraph(f'<b>{ref_num}</b>', styles['BodyBold']),
            [Paragraph(citation, styles['Body']),
             Paragraph(f'<i><font color="#64748B">Role: {note}</font></i>', styles['Small'])],
        ]]
        t = Table(ref_data, colWidths=[0.9*cm, BODY_W - 0.9*cm])
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LINEBELOW', (0,0), (-1,-1), 0.3, MGRAY),
        ]))
        s.append(t)
        s.append(sp(2))

    s.append(sp(16))
    s += callout('Note on Implementation',
        'The vousFin Isolation Forest implementation is a ground-up pure-JavaScript port '
        'of the algorithm as described in references [1] and [2]. It does not depend on '
        'scikit-learn, TensorFlow, or any Python library. The mathematical scoring formula '
        's(x,n) = 2^(−E[h(x)]/c(n)) is implemented verbatim from reference [2].',
        color=NAVY, styles=styles)
    return s


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN BUILD
# ═══════════════════════════════════════════════════════════════════════════
def main():
    global _STYLES
    _STYLES = build_styles()

    doc = IFDoc(OUT)
    story = []

    # ── Cover ──
    story.extend(build_cover(_STYLES))
    story.append(NextPageTemplate('Body'))
    story.append(PageBreak())

    # ── TOC ──
    story.extend(build_toc(_STYLES))
    story.append(PageBreak())

    # ── Sections ──
    all_sections = [
        section_1, section_2, section_3, section_4,
        section_5, section_6, section_7, section_8,
        section_9, section_10, section_11, section_12, section_13,
    ]

    for i, fn in enumerate(all_sections):
        story.extend(fn(_STYLES))
        if i < len(all_sections) - 1:
            story.append(PageBreak())

    doc.build(story)
    size = os.path.getsize(OUT)
    print(f"SUCCESS: {OUT}")
    print(f"Size: {size:,} bytes  ({size/1024/1024:.2f} MB)")


if __name__ == '__main__':
    main()
