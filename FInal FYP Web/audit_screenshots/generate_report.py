# -*- coding: utf-8 -*-
"""
VousFin Frontend Design & UX Audit Report — Generator

Produces:
    C:/Users/shafi/OneDrive/Desktop/VousFin Smart Accountant/FInal FYP Web/VousFin_Frontend_Audit_Report.pdf

Inputs:
    audit_screenshots/*.png  (real screenshots captured via Chrome MCP)
    Audit analysis derived from static code reading of the React codebase.
"""

import os
from datetime import datetime
from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, PageBreak, KeepTogether,
    Image as RLImage, Table, TableStyle, HRFlowable, ListFlowable, ListItem,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY

# ────────────────────────────────────────────────────────────────────────────
# Paths & constants
# ────────────────────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)
SCREENSHOTS_DIR = BASE
OUTPUT_PDF = os.path.join(PROJECT_ROOT, "VousFin_Frontend_Audit_Report.pdf")

# Brand palette
NAVY      = colors.HexColor("#0B1020")
CHARCOAL  = colors.HexColor("#1E293B")
CYAN      = colors.HexColor("#06B6D4")
BRAND     = colors.HexColor("#2563EB")
GREEN     = colors.HexColor("#10b981")
AMBER     = colors.HexColor("#f59e0b")
RED       = colors.HexColor("#ef4444")
SKY       = colors.HexColor("#0ea5e9")
SLATE_900 = colors.HexColor("#0F172A")
SLATE_700 = colors.HexColor("#334155")
SLATE_600 = colors.HexColor("#475569")
SLATE_500 = colors.HexColor("#64748B")
SLATE_400 = colors.HexColor("#94a3b8")
SLATE_300 = colors.HexColor("#CBD5E1")
SLATE_200 = colors.HexColor("#E2E8F0")
SLATE_100 = colors.HexColor("#F1F5F9")
SLATE_50  = colors.HexColor("#F8FAFC")

PAGE_MARGIN_X = 1.7 * cm
PAGE_MARGIN_Y = 1.7 * cm

# ────────────────────────────────────────────────────────────────────────────
# Style sheet
# ────────────────────────────────────────────────────────────────────────────
ss = getSampleStyleSheet()

def make_styles():
    s = {}
    s["body"] = ParagraphStyle(
        "body", parent=ss["BodyText"],
        fontName="Helvetica", fontSize=10, leading=14,
        textColor=SLATE_700, alignment=TA_JUSTIFY, spaceAfter=6,
    )
    s["body_left"] = ParagraphStyle(
        "body_left", parent=s["body"], alignment=TA_LEFT,
    )
    s["small"] = ParagraphStyle(
        "small", parent=s["body"], fontSize=8.5, leading=12, textColor=SLATE_600,
    )
    s["caption"] = ParagraphStyle(
        "caption", parent=s["body"], fontSize=8.5, leading=11,
        textColor=SLATE_500, alignment=TA_CENTER, italic=True, spaceBefore=2, spaceAfter=10,
    )
    s["h1"] = ParagraphStyle(
        "h1", parent=ss["Heading1"],
        fontName="Helvetica-Bold", fontSize=22, leading=26,
        textColor=NAVY, spaceBefore=4, spaceAfter=12,
    )
    s["h2"] = ParagraphStyle(
        "h2", parent=ss["Heading2"],
        fontName="Helvetica-Bold", fontSize=15, leading=19,
        textColor=BRAND, spaceBefore=14, spaceAfter=8,
    )
    s["h3"] = ParagraphStyle(
        "h3", parent=ss["Heading3"],
        fontName="Helvetica-Bold", fontSize=12, leading=16,
        textColor=CHARCOAL, spaceBefore=10, spaceAfter=4,
    )
    s["h4"] = ParagraphStyle(
        "h4", parent=ss["Heading4"],
        fontName="Helvetica-Bold", fontSize=10.5, leading=14,
        textColor=SLATE_700, spaceBefore=8, spaceAfter=2,
    )
    s["code"] = ParagraphStyle(
        "code", parent=s["body"],
        fontName="Courier", fontSize=8.5, leading=11,
        textColor=SLATE_900, backColor=SLATE_50,
        leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=4, alignment=TA_LEFT,
        borderColor=SLATE_200, borderWidth=0.5, borderPadding=4,
    )
    s["cover_title"] = ParagraphStyle(
        "cover_title", fontName="Helvetica-Bold", fontSize=32, leading=38,
        textColor=NAVY, alignment=TA_LEFT, spaceAfter=6,
    )
    s["cover_subtitle"] = ParagraphStyle(
        "cover_subtitle", fontName="Helvetica", fontSize=14, leading=18,
        textColor=SLATE_600, alignment=TA_LEFT, spaceAfter=14,
    )
    s["cover_meta"] = ParagraphStyle(
        "cover_meta", fontName="Helvetica", fontSize=9.5, leading=13,
        textColor=SLATE_500, alignment=TA_LEFT,
    )
    s["toc_h1"] = ParagraphStyle(
        "toc_h1", fontName="Helvetica-Bold", fontSize=11, leading=18, textColor=NAVY,
        leftIndent=0,
    )
    s["toc_h2"] = ParagraphStyle(
        "toc_h2", fontName="Helvetica", fontSize=9.5, leading=14, textColor=SLATE_600,
        leftIndent=14,
    )
    s["callout_body"] = ParagraphStyle(
        "callout_body", fontName="Helvetica", fontSize=9.5, leading=13,
        textColor=SLATE_700, alignment=TA_LEFT,
    )
    return s

S = make_styles()

# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────
def hr(color=SLATE_200, thickness=0.6):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceBefore=4, spaceAfter=8)

def section_break():
    return [Spacer(1, 4*mm), hr(CYAN, 1.5), Spacer(1, 2*mm)]

def fit_image(filename, max_width_cm=16, max_height_cm=11, caption=None):
    """Embed an image preserving aspect, with optional caption."""
    path = os.path.join(SCREENSHOTS_DIR, filename)
    if not os.path.exists(path):
        return Paragraph(f"<i>[Missing screenshot: {filename}]</i>", S["caption"])
    with PILImage.open(path) as im:
        w, h = im.size
    aspect = h / w
    target_w_cm = max_width_cm
    target_h_cm = target_w_cm * aspect
    if target_h_cm > max_height_cm:
        target_h_cm = max_height_cm
        target_w_cm = target_h_cm / aspect
    img = RLImage(path, width=target_w_cm*cm, height=target_h_cm*cm)
    out = [img]
    if caption:
        out.append(Paragraph(caption, S["caption"]))
    return out

def callout(title, body, color_left=CYAN, bg=SLATE_50, border=SLATE_200):
    """Coloured callout box with title + body text."""
    inner = [
        Paragraph(f"<b>{title}</b>", ParagraphStyle(
            "ct", parent=S["callout_body"], textColor=NAVY, fontName="Helvetica-Bold",
            fontSize=10, spaceAfter=3)),
        Paragraph(body, S["callout_body"]),
    ]
    tbl = Table([[inner]], colWidths=[16*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("LINEBEFORE", (0,0), (0,-1), 3, color_left),
        ("BOX", (0,0), (-1,-1), 0.4, border),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    return tbl

def styled_table(data, col_widths=None, header_bg=NAVY, header_fg=colors.white,
                 zebra=True, body_fg=SLATE_700, font_size=8.5):
    if col_widths is None:
        col_widths = [16*cm / len(data[0])] * len(data[0])
    # Wrap cell strings as Paragraphs for wrapping support
    bs = ParagraphStyle("tcell", parent=S["small"], alignment=TA_LEFT,
                        fontSize=font_size, leading=font_size+3, textColor=body_fg,
                        spaceBefore=0, spaceAfter=0)
    hs = ParagraphStyle("hcell", parent=bs, textColor=header_fg,
                        fontName="Helvetica-Bold")
    wrapped = []
    for r, row in enumerate(data):
        wr = []
        for cell in row:
            if isinstance(cell, str):
                wr.append(Paragraph(cell, hs if r == 0 else bs))
            else:
                wr.append(cell)
        wrapped.append(wr)
    tbl = Table(wrapped, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0,0), (-1,0), header_bg),
        ("TEXTCOLOR",  (0,0), (-1,0), header_fg),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), font_size),
        ("ALIGN",      (0,0), (-1,-1), "LEFT"),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("LINEBELOW",  (0,0), (-1,0), 0.5, SLATE_300),
        ("LINEBELOW",  (0,1), (-1,-2), 0.25, SLATE_200),
        ("BOX",        (0,0), (-1,-1), 0.5, SLATE_300),
    ]
    if zebra:
        for r in range(1, len(data)):
            if r % 2 == 1:
                style.append(("BACKGROUND", (0,r), (-1,r), SLATE_50))
    tbl.setStyle(TableStyle(style))
    return tbl

def code_block(text):
    # Use <font> tags so multiline preserves
    safe = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("\n", "<br/>"))
    return Paragraph(safe, S["code"])

def bullets(items):
    flow = [ListItem(Paragraph(t, S["body_left"]), leftIndent=14, bulletColor=BRAND)
            for t in items]
    return ListFlowable(flow, bulletType="bullet", start="•", leftIndent=18)

# ────────────────────────────────────────────────────────────────────────────
# Page templates
# ────────────────────────────────────────────────────────────────────────────
def draw_chrome(canvas, doc):
    """Header bar + footer with page number — drawn on every page except cover."""
    canvas.saveState()
    w, h = A4
    # Header bar
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 1.0*cm, w, 1.0*cm, fill=1, stroke=0)
    canvas.setFillColor(CYAN)
    canvas.rect(0, h - 1.05*cm, w, 0.05*cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(PAGE_MARGIN_X, h - 0.65*cm, "vousFin")
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(SLATE_300)
    canvas.drawString(PAGE_MARGIN_X + 1.5*cm, h - 0.65*cm,
                      "— Frontend Design & UX Audit Report")
    canvas.setFillColor(SLATE_300)
    canvas.drawRightString(w - PAGE_MARGIN_X, h - 0.65*cm,
                           datetime.now().strftime("May 2026"))
    # Footer
    canvas.setStrokeColor(SLATE_200)
    canvas.setLineWidth(0.4)
    canvas.line(PAGE_MARGIN_X, 1.0*cm, w - PAGE_MARGIN_X, 1.0*cm)
    canvas.setFillColor(SLATE_500)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(PAGE_MARGIN_X, 0.6*cm,
                      "vousFin Smart Accountant  |  Frontend Audit & UX Documentation")
    canvas.drawRightString(w - PAGE_MARGIN_X, 0.6*cm,
                           f"Page {doc.page}")
    canvas.restoreState()

def draw_cover(canvas, doc):
    """Cover page — special chrome (no header, big accent band)."""
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 9*cm, w, 9*cm, fill=1, stroke=0)
    canvas.setFillColor(CYAN)
    canvas.rect(0, h - 9.4*cm, w, 0.4*cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(PAGE_MARGIN_X, h - 1.5*cm,
                      "vousFin — Smart Accountant ERP Platform")
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(SLATE_300)
    canvas.drawString(PAGE_MARGIN_X, h - 2.0*cm,
                      "Senior ERP UX Audit  ·  Frontend Architecture Review")
    # Footer
    canvas.setFillColor(SLATE_500)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - PAGE_MARGIN_X, 0.7*cm,
                           "Internal audit document — for evaluation only")
    canvas.restoreState()

# ────────────────────────────────────────────────────────────────────────────
# Build doc
# ────────────────────────────────────────────────────────────────────────────
class AuditDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, pagesize=A4,
                         leftMargin=PAGE_MARGIN_X, rightMargin=PAGE_MARGIN_X,
                         topMargin=PAGE_MARGIN_Y + 0.5*cm,
                         bottomMargin=PAGE_MARGIN_Y, **kw)
        cover_frame = Frame(PAGE_MARGIN_X, PAGE_MARGIN_Y,
                            self.width, self.height,
                            id="cover_frame", showBoundary=0)
        body_frame  = Frame(PAGE_MARGIN_X, PAGE_MARGIN_Y,
                            self.width, self.height - 0.5*cm,
                            id="body_frame", showBoundary=0)
        self.addPageTemplates([
            PageTemplate(id="Cover", frames=cover_frame, onPage=draw_cover),
            PageTemplate(id="Body",  frames=body_frame,  onPage=draw_chrome),
        ])
        self._bookmarks = []

    def afterFlowable(self, flowable):
        """Capture headings for PDF outline (sidebar nav in viewers)."""
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            text = flowable.getPlainText()
            level = None
            if style_name == "h1":   level = 0
            elif style_name == "h2": level = 1
            elif style_name == "h3": level = 2
            if level is not None:
                key = f"bm_{len(self._bookmarks)}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=(level >= 2))
                self._bookmarks.append((text, key, level))

# ────────────────────────────────────────────────────────────────────────────
# Section builders
# ────────────────────────────────────────────────────────────────────────────
def cover():
    elems = []
    elems.append(Spacer(1, 4.0*cm))
    elems.append(Paragraph("VousFin Frontend", S["cover_title"]))
    elems.append(Paragraph("Design &amp; UX Audit Report", S["cover_title"]))
    elems.append(Spacer(1, 0.5*cm))
    elems.append(Paragraph(
        "A senior-level review of the React frontend powering "
        "vousFin Smart Accountant — covering architecture, design system, "
        "ERP workflows, AI integration, responsiveness, accessibility, "
        "and enterprise readiness.",
        S["cover_subtitle"]))
    elems.append(Spacer(1, 0.8*cm))
    meta = [
        ["Document",          "Frontend Design &amp; UX Audit"],
        ["Subject",           "vousFin Smart Accountant — Web Frontend (React 19 + Vite)"],
        ["Prepared for",      "FYP Evaluation · Investor Review · UI/UX Review"],
        ["Date",              datetime.now().strftime("%B %Y")],
        ["Audit scope",       "Full frontend code review + live UI screenshots (1440×900)"],
        ["Methodology",       "Static code review · Live browser inspection · UX heuristic analysis"],
        ["Codebase size",     "~70 React components · ~25 pages · Tailwind design tokens"],
    ]
    rows = []
    for k, v in meta:
        rows.append([
            Paragraph(f"<b>{k}</b>", ParagraphStyle("mk", parent=S["small"],
                       textColor=NAVY, fontName="Helvetica-Bold")),
            Paragraph(v, S["small"]),
        ])
    tbl = Table(rows, colWidths=[4*cm, 12*cm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LINEBELOW", (0,0), (-1,-2), 0.3, SLATE_200),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BACKGROUND", (0,0), (-1,-1), colors.white),
    ]))
    elems.append(tbl)
    elems.append(PageBreak())
    return elems

def toc_page():
    elems = []
    elems.append(Paragraph("Table of Contents", S["h1"]))
    elems.append(hr(BRAND, 1.5))
    elems.append(Spacer(1, 4*mm))
    toc = [
        ("1.  Executive Summary",                    "5"),
        ("2.  Frontend Architecture Overview",       "7"),
        ("3.  Design System Analysis",               "11"),
        ("4.  Navigation &amp; Sidebar Analysis",        "14"),
        ("5.  Dashboard Analysis",                   "16"),
        ("6.  Transaction Management UX",            "19"),
        ("7.  AI Features UX Analysis",              "23"),
        ("8.  Financial Reports Analysis",           "27"),
        ("9.  Responsiveness &amp; Mobile Analysis",     "31"),
        ("10. Performance UX Analysis",              "33"),
        ("11. Accessibility &amp; Usability",            "35"),
        ("12. Visual Gallery",                       "37"),
        ("13. Frontend Strengths",                   "44"),
        ("14. Frontend Weaknesses",                  "46"),
        ("15. Enterprise Readiness Assessment",      "48"),
        ("16. Recommended Improvements",             "50"),
        ("17. Final Conclusion",                     "53"),
    ]
    rows = []
    for label, page in toc:
        rows.append([
            Paragraph(label, ParagraphStyle("tl", parent=S["body_left"],
                       fontName="Helvetica-Bold", textColor=NAVY,
                       fontSize=10.5, leading=15)),
            Paragraph(page, ParagraphStyle("tp", parent=S["body_left"],
                       fontName="Helvetica", textColor=SLATE_500,
                       fontSize=10.5, leading=15, alignment=TA_RIGHT)),
        ])
    tbl = Table(rows, colWidths=[14*cm, 2*cm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,0), (-1,-1), 0.25, SLATE_200),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    elems.append(tbl)
    elems.append(Spacer(1, 1*cm))
    elems.append(callout(
        "How to read this report",
        "Sections 1–2 give the executive and architectural overview. Sections 3–11 "
        "go module-by-module through the UI, mixing live screenshots with code "
        "analysis. Section 12 is a pure visual gallery. Sections 13–17 synthesise "
        "strengths, weaknesses, and a prioritised improvement roadmap."))
    elems.append(PageBreak())
    return elems

# ───── Section 1 — Executive Summary ─────────────────────────────────────────
def section_1():
    e = []
    e.append(Paragraph("1. Executive Summary", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph(
        "vousFin is a full-stack AI-powered accounting ERP that targets "
        "small and medium businesses. The frontend, built with React 19 + Vite + "
        "Tailwind CSS, ships as a dark-themed single-page application with "
        "double-entry bookkeeping, multi-tenant business accounts, AR/AP "
        "workflows, four core financial reports, an LSTM-driven forecast module, "
        "an Isolation Forest anomaly detector, and a globally-available AI "
        "chat assistant. This audit reviews how mature, scalable, and ready "
        "for enterprise/SaaS adoption the frontend currently is.",
        S["body"]))

    e.append(Paragraph("1.1 What VousFin's Frontend Is", S["h2"]))
    e.append(Paragraph(
        "The application presents itself as a modern dark-mode dashboard with "
        "a glass-panel aesthetic — gradient cyan accents on a deep navy "
        "(#0B1020) base, Inter sans-serif typography, and SaaS-style component "
        "patterns familiar from Linear, Stripe Dashboard, and QuickBooks Online. "
        "Architecturally it is a classic SPA: react-router v7 with lazy-loaded "
        "route chunks, TanStack Query for server state, Zustand for client "
        "state (auth + business + AI chat history), Tailwind v3 for styling, "
        "Recharts for analytics, and react-hot-toast for feedback.",
        S["body"]))

    e.append(Paragraph("1.2 Architectural Maturity", S["h2"]))
    e.append(styled_table([
        ["Dimension", "Status", "Notes"],
        ["Component reuse", "Strong",
         "Centralised primitives in <b>components/ui/</b> (Button, Card, KPICard, Badge, "
         "Drawer, Select, EmptyState, SkeletonLoader). Pages compose these consistently."],
        ["Routing &amp; guards", "Strong",
         "<b>RootRedirect</b>, <b>RequireSetup</b>, <b>RequireBusiness</b> guards "
         "deterministically gate the app on auth + business setup state."],
        ["Lazy loading", "Strong",
         "Every page uses <i>React.lazy + Suspense</i> with a unified skeleton fallback."],
        ["State management", "Strong",
         "Server data goes through TanStack Query (5-minute staleTime); client state "
         "(auth, business, AI chat) lives in Zustand singletons."],
        ["Design system",   "Mixed",
         "Custom Tailwind tokens for navy/cyan/glass exist, but financial "
         "semantic tokens (positive / negative / warning) are missing — UI "
         "components hand-roll <i>text-emerald-400 / text-red-400</i>."],
        ["Accessibility",   "Mixed",
         "Buttons and modals expose aria-label/role, DataTable has aria-sort, "
         "but full keyboard navigation and focus-trap on portal panels are "
         "inconsistent."],
        ["Responsiveness",  "Mixed",
         "Sidebar collapses to a Drawer; MobileNav bottom bar covers 5 hot "
         "destinations. Reports tables don't horizontally scroll well at "
         "&lt; 500px width."],
        ["AI integration",  "Strong",
         "Persistent GlobalAIWidget FAB + fullscreen mode; route-aware "
         "suggested prompts; Anomaly &amp; Forecast tabs unified in an AI "
         "Analyst hub."],
    ], col_widths=[3.5*cm, 2.4*cm, 10.1*cm]))

    e.append(Paragraph("1.3 Strengths at a Glance", S["h2"]))
    e.append(bullets([
        "<b>Consistent visual language</b> — dark navy + cyan + glass panels are applied uniformly across 25+ pages.",
        "<b>True ERP information density</b> — KPI grids, tabbed report hubs, AR/AP aging, multi-line journals.",
        "<b>Mature AI UX</b> — a global floating assistant with route-contextual prompts and a fullscreen workspace.",
        "<b>Hub pages</b> — Financial Reports and AI Analyst use mount-once-hide tab strategies to preserve in-tab state and avoid API thrashing.",
        "<b>Portal-rendered overlays</b> — Select and Drawer escape stacking contexts via React Portal, avoiding the classic dropdown-clipping bug.",
    ]))

    e.append(Paragraph("1.4 Weaknesses at a Glance", S["h2"]))
    e.append(bullets([
        "<b>Token bug</b> — local Tailwind overrides <i>emerald.DEFAULT / 2 / 3</i> to cyan/blue, so any class without a numeric suffix renders the wrong colour.",
        "<b>No semantic financial palette</b> — every page invents its own positive/negative colour pair.",
        "<b>KPICard trend label is fake</b> — shows static \"Positive YTD\" / \"Negative YTD\" with no real period-over-period delta.",
        "<b>Two parallel button libraries</b> — <i>common/Button</i> (light, auth flows) vs <i>ui/Button</i> (dark, dashboard) without clear documentation.",
        "<b>No virtualisation</b> — DataTable renders the full row list; will degrade beyond ~2,000 rows.",
        "<b>Reports lack expand/collapse + sticky totals</b> — long account lists scroll past the totals row.",
    ]))

    e.append(Paragraph("1.5 Enterprise Readiness Verdict", S["h2"]))
    e.append(callout(
        "Verdict: Strong FYP / Demo / Investor-ready — Targeted work needed before mid-market SaaS rollout",
        "The frontend is visually polished, architecturally sound, and "
        "functionally comparable to Zoho Books at MVP scale. To stand "
        "alongside QuickBooks Online or Xero on a feature-by-feature basis, "
        "the design system needs semantic financial tokens, the data grid "
        "needs virtualisation, the reports need drill-down + sticky totals, "
        "and accessibility needs a focused pass."))

    e.append(PageBreak())
    return e

# ───── Section 2 — Architecture Overview ─────────────────────────────────────
def section_2():
    e = []
    e.append(Paragraph("2. Frontend Architecture Overview", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph("2.1 Tech Stack", S["h2"]))
    e.append(styled_table([
        ["Concern", "Library", "Version", "Role"],
        ["Framework",      "React",                "19.2",  "Component model"],
        ["Build",          "Vite",                 "8.x",   "Dev server, HMR, code-split build"],
        ["Routing",        "react-router-dom",     "7.x",   "Nested routes, guards, lazy chunks"],
        ["Server state",   "@tanstack/react-query","5.x",   "Caching, retries, invalidations"],
        ["Client state",   "zustand",              "5.x",   "Auth, active business, AI chat singletons"],
        ["Forms",          "react-hook-form + zod","7/4",   "Controlled forms with schema validation"],
        ["Styling",        "tailwindcss",          "3.4",   "Utility-first + custom token theme"],
        ["Charts",         "recharts",             "3.x",   "Line, bar, area, pie for reports + AI"],
        ["Icons",          "lucide-react",         "1.x",   "Outline icon set, tree-shakeable"],
        ["HTTP",           "axios",                "1.x",   "Interceptors for JWT + business header"],
        ["Toasts",         "react-hot-toast",      "2.x",   "Non-blocking feedback"],
        ["Markdown",       "react-markdown",       "10.x",  "AI answer rendering"],
        ["Excel import",   "xlsx (SheetJS)",       "0.18",  "Bulk transaction Excel parsing"],
        ["Dates",          "date-fns",             "4.x",   "ISO/local helpers, period filters"],
    ], col_widths=[3.4*cm, 4.0*cm, 2.4*cm, 6.2*cm]))

    e.append(Paragraph("2.2 Folder Structure", S["h2"]))
    e.append(code_block(
        "src/\n"
        "├── App.jsx                # QueryClient + Router + SessionBootstrap + Toaster\n"
        "├── routes.jsx             # Lazy routes + RequireBusiness / RequireSetup guards\n"
        "├── main.jsx               # Vite entry\n"
        "├── index.css              # Tailwind layers + global utility classes\n"
        "│\n"
        "├── components/\n"
        "│   ├── ui/                # Design-system primitives (dark theme)\n"
        "│   │   ├── Button.jsx     · Card · KPICard · Badge · EmptyState · SkeletonLoader\n"
        "│   │   ├── Drawer.jsx     · Select.jsx (portal) · Input · TextArea · ExportButton\n"
        "│   ├── common/            # LIGHT-theme primitives used by auth flows only\n"
        "│   ├── layout/            # Sidebar · Header · MobileNav · Footer · Breadcrumbs\n"
        "│   ├── modals/Modal.jsx   # Portal-based modal\n"
        "│   ├── tables/DataTable.jsx\n"
        "│   ├── forms/             # TransactionFormModal · AccountFormModal · etc.\n"
        "│   ├── dashboard/         # RevenueExpensesChart · CashFlowTrendChart\n"
        "│   ├── reports/           # Per-report table components + ExportButtons\n"
        "│   ├── charts/            # ForecastChart (LSTM time-series)\n"
        "│   ├── ai/                # AIAssistantChat · AnomalyAlerts · GlobalAIWidget\n"
        "│   └── auth/SessionBootstrap.jsx   # Hydrates auth on app mount\n"
        "│\n"
        "├── layouts/\n"
        "│   ├── AuthLayout.jsx     # Centered card layout for /login /register /forgot\n"
        "│   └── DashboardLayout.jsx# Sidebar + Drawer + Header + Main + MobileNav + AI FAB\n"
        "│\n"
        "├── pages/\n"
        "│   ├── auth/              # Login · Register · ForgotPassword · ResetPassword · VerifyEmail\n"
        "│   ├── business/          # BusinessSetup · BusinessSettings\n"
        "│   ├── dashboard/         # Dashboard.jsx (KPI grid + charts + recent tx)\n"
        "│   ├── accounts/          # AccountsPage (Chart of Accounts list + group)\n"
        "│   ├── transactions/      # TransactionsList (table + filters + form modal)\n"
        "│   ├── parties/           # CustomersList · VendorsList · *Detail · Receivables · Payables\n"
        "│   ├── reports/           # FinancialReportsPage hub + 5 sub-tabs\n"
        "│   └── ai/                # AIAnalystPage hub + Forecast/Anomaly/Assistant sub-tabs\n"
        "│\n"
        "├── hooks/                 # useAccounts · useTransactions · useReports · useAI · useParties\n"
        "├── stores/                # useAuthStore · useBusinessStore · useAIStore\n"
        "├── services/api.js        # Axios instance + interceptors\n"
        "└── utils/                 # cn · formatters · errorHandler · sanitize\n"
    ))

    e.append(Paragraph("2.3 Application Bootstrap Flow", S["h2"]))
    e.append(Paragraph(
        "<b>main.jsx → App → QueryClientProvider → BrowserRouter → SessionBootstrap → AppRoutes.</b> "
        "SessionBootstrap calls the auth store on mount, hydrating any persisted "
        "JWT before the router renders, so guards can deterministically decide "
        "Login vs Setup vs Dashboard.",
        S["body"]))
    e.append(Paragraph(
        "A single <b>QueryClient</b> is instantiated once at the app root with "
        "<i>refetchOnWindowFocus: false</i>, <i>retry: 1</i>, and "
        "<i>staleTime: 5 minutes</i> — meaning the frontend cache aligns with "
        "the 5-minute backend report cache, eliminating redundant refetches.",
        S["body"]))

    e.append(Paragraph("2.4 Routing &amp; Authorization Hierarchy", S["h2"]))
    e.append(code_block(
        "/                                  → RootRedirect → login | setup | dashboard\n"
        "/login                             → AuthLayout > Login\n"
        "/register                          → AuthLayout > Register\n"
        "/forgot-password                   → AuthLayout > ForgotPassword\n"
        "/business/setup                    → RequireSetup > BusinessSetup\n"
        "/* (everything else)               → RequireBusiness > DashboardLayout\n"
        "    /dashboard\n"
        "    /accounts\n"
        "    /transactions\n"
        "    /customers · /customers/:id\n"
        "    /vendors · /vendors/:id\n"
        "    /sales/receivables · /purchases/payables\n"
        "    /financial-reports/:tab          ← hub w/ 5 sub-tabs\n"
        "    /ai-analyst/:tab                 ← hub w/ 3 sub-tabs\n"
        "    /ai/assistant                    ← standalone chat\n"
        "    /business/settings\n"))

    e.append(Paragraph("2.5 State Management Topology", S["h2"]))
    e.append(styled_table([
        ["Store",            "Owns",                                          "Persistence"],
        ["useAuthStore",     "user, token, isAuthenticated, login(), logout()", "localStorage"],
        ["useBusinessStore", "activeBusiness, currency, fetchBusiness()",       "Session"],
        ["useAIStore",       "AI chat messages, loading, sendMessage()",        "Memory (singleton)"],
        ["React Query",      "Transactions, accounts, reports, dashboard, parties", "Memory (5m stale)"],
    ], col_widths=[3.6*cm, 8.0*cm, 4.4*cm]))

    e.append(Paragraph("2.6 Layout System", S["h2"]))
    e.append(Paragraph(
        "<b>DashboardLayout</b> composes three persistent surfaces around an "
        "<i>&lt;Outlet/&gt;</i>: a left <b>Sidebar</b> (collapsible 64→16 width), a "
        "sticky <b>Header</b> with route-derived page title + notification + "
        "profile, and a bottom <b>MobileNav</b> visible below <i>lg</i>. The "
        "<b>GlobalAIWidget</b> is mounted ONCE here so its chat state survives "
        "all route changes.",
        S["body"]))

    e.append(Paragraph("2.7 Scalability Assessment", S["h2"]))
    e.append(bullets([
        "<b>Lazy chunks</b> keep first-paint bundle small — Login alone, Dashboard, every report tab.",
        "<b>Mount-once tab hubs</b> avoid redundant API calls when users switch report or AI tabs.",
        "<b>React Query 5-minute staleTime</b> aligns with backend cache — minimal redundant network.",
        "<b>Pure CSS dark theme</b> via Tailwind tokens means re-theming is a config-only change.",
        "<b>Single QueryClient + Axios singleton</b> = predictable retry, error handling, request cancellation.",
    ]))

    e.append(PageBreak())
    return e

# ───── Section 3 — Design System ─────────────────────────────────────────────
def section_3():
    e = []
    e.append(Paragraph("3. Design System Analysis", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph("3.1 Color Palette (Tailwind tokens)", S["h2"]))
    swatch_rows = [["Token", "Hex", "Purpose"]]
    palette = [
        ("navy.DEFAULT",      "#0B1020", "App background"),
        ("navy.2",            "#111827", "Secondary surface"),
        ("charcoal.DEFAULT",  "#1E293B", "Sidebar / panel bg"),
        ("cyan.DEFAULT",      "#06B6D4", "Primary brand accent"),
        ("cyan.2",            "#2563EB", "Gradient pair"),
        ("emerald.DEFAULT (bug)",  "#06B6D4", "Should be green — currently cyan"),
        ("amber.DEFAULT",     "#F59E0B", "Warning / pending"),
        ("amber.2",           "#FBBF24", "Warning text"),
        ("text.primary",      "#F8FAFC", "Primary text on dark"),
        ("text.secondary",    "#CBD5E1", "Secondary text"),
        ("text.muted",        "#64748B", "Muted / placeholder"),
        ("glass border",      "rgba(6,182,212,0.15)", "Card / panel borders"),
        ("glass-panel bg",    "rgba(255,255,255,0.03)", "Glass-panel fill"),
    ]
    for tok, hexv, role in palette:
        swatch_rows.append([tok, hexv, role])
    e.append(styled_table(swatch_rows, col_widths=[5.0*cm, 4.0*cm, 7.0*cm]))

    e.append(Paragraph("3.2 Typography", S["h2"]))
    e.append(styled_table([
        ["Token", "Family / Size", "Usage"],
        ["Sans serif", "Inter, system-ui, Segoe UI", "All UI text (with fallbacks)"],
        ["Page heading", "font-black text-2xl tracking-tight", "Page titles (Dashboard, Transactions)"],
        ["Section heading", "font-bold text-lg", "In-page sections"],
        ["KPI value", "font-black text-2xl tabular-nums", "Currency &amp; metric displays"],
        ["Label", "uppercase text-xs tracking-wider", "KPI titles, table headers"],
        ["Body", "text-sm text-text-secondary", "Default paragraph text"],
        ["Caption", "text-xs text-text-muted", "Helper text, captions"],
    ], col_widths=[3.6*cm, 5.4*cm, 7.0*cm]))

    e.append(Paragraph("3.3 Component Inventory", S["h2"]))
    e.append(styled_table([
        ["Component", "Variants / Props", "Quality"],
        ["Button",       "5 variants: gradient · outline · ghost · amber · danger; loading; icon",  "Strong"],
        ["Card",         "Glass-panel with optional <i>noPadding</i> prop; hover-scale utility",     "Strong"],
        ["KPICard",      "title, value, format, trend, loading, icon — but trend is fake",          "Mixed"],
        ["Badge",        "5 variants: default · success · warning · danger · info",                  "Strong (cyan-as-emerald visual bug aside)"],
        ["DataTable",    "Sortable, sticky header, zebra, dense, skeleton, empty state",             "Strong"],
        ["Drawer",       "Portal-rendered, position left/right, body scroll lock",                   "Strong"],
        ["Select",       "Custom dropdown via Portal w/ smart vertical flip + group separators",     "Strong"],
        ["Modal",        "Portal modal w/ overlay backdrop + Escape close",                          "Strong"],
        ["SkeletonLoader","Generic count-N rows",                                                    "Standard"],
        ["EmptyState",   "Icon + title + description + optional action",                             "Standard"],
        ["Input · TextArea", "Glass-panel inputs w/ leading icon, error helper",                      "Standard"],
    ], col_widths=[3.5*cm, 8.8*cm, 3.7*cm]))

    e.append(Paragraph("3.4 Spacing &amp; Layout", S["h2"]))
    e.append(Paragraph(
        "The app inherits Tailwind's default 4-px spacing scale. Common rhythm "
        "in pages: <i>space-y-8</i> between major sections, <i>gap-4</i> on KPI grids, "
        "<i>p-6</i> on cards (overridable via the Card <b>noPadding</b> prop). "
        "Pages live inside a centered <i>max-w-7xl mx-auto px-4 sm:px-6 lg:px-8</i> container.",
        S["body"]))

    e.append(Paragraph("3.5 Shadows &amp; Elevation", S["h2"]))
    e.append(styled_table([
        ["Token", "Effect", "Where used"],
        ["shadow-card",     "Soft 1-pt drop", "Default cards (light theme legacy)"],
        ["shadow-elevated", "Larger soft drop", "Modal, Drawer, dropdown panels"],
        ["shadow-glow-cyan",  "Outer cyan glow (0.22 alpha)",  "Active sidebar item, AI accent"],
        ["shadow-glow-em",    "Outer blue glow (0.18 alpha)",  "Gradient buttons"],
    ], col_widths=[4.0*cm, 5.0*cm, 7.0*cm]))

    e.append(Paragraph("3.6 Animation &amp; Motion", S["h2"]))
    e.append(Paragraph(
        "Three custom keyframes: <i>fade-in</i> (200 ms), <i>slide-up</i> (250 ms), "
        "<i>pulse-dot</i> (2 s loop for system-status indicators). Pages mount "
        "with <i>animate-fade-in</i>; hover scales use a <i>hover-scale</i> utility "
        "class. Motion is restrained — no spring physics, no parallax, no "
        "carousel-style attention-grabbers.",
        S["body"]))

    e.append(Paragraph("3.7 Design System Findings", S["h2"]))
    e.append(callout(
        "Critical: The <i>emerald</i> token is a colour-name lie",
        "<i>theme.colors.emerald.DEFAULT</i> is set to #06B6D4 (cyan) — a "
        "visual bug for anyone using <i>text-emerald</i> expecting green. "
        "Tailwind's native green palette only kicks in when a numeric suffix "
        "is used (text-emerald-400 → #34d399). The Badge `success` variant "
        "uses <i>bg-emerald/10 text-emerald-300 border-emerald/20</i>, "
        "rendering it BLUE instead of GREEN.",
        color_left=RED))
    e.append(callout(
        "Missing: Semantic financial tokens",
        "No <i>positive / negative / warning / info</i> design tokens exist. "
        "Every chart, KPI, badge, and inline indicator hand-rolls "
        "<i>text-emerald-400</i> / <i>text-red-400</i> — brittle for future "
        "theme switches or print-friendly variants.",
        color_left=AMBER))

    e.append(PageBreak())
    return e

# ───── Section 4 — Navigation & Sidebar ──────────────────────────────────────
def section_4():
    e = []
    e.append(Paragraph("4. Navigation &amp; Sidebar Analysis", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph(
        "The sidebar is the spine of the ERP — 11 top-level entries across "
        "links and expandable groups, structured to mirror real accounting "
        "concepts: Dashboard → Accounts → Transactions → (Sales / Purchases) "
        "→ Financial Reports → AI Analyst → AI Assistant → Settings.",
        S["body"]))

    e.extend(fit_image("02-dashboard.png", max_width_cm=15.5,
                       caption="Figure 4.1 — Dashboard at 1440×900. Sidebar uses charcoal "
                       "bg, cyan-tinted active-state glow on \"Dashboard\", and grouped "
                       "expandable entries below Transactions."))

    e.append(Paragraph("4.1 Information Architecture", S["h2"]))
    e.append(styled_table([
        ["Entry", "Type", "Sub-items"],
        ["Dashboard",         "Link",  "—"],
        ["Accounts",          "Link",  "—"],
        ["Transactions",      "Link",  "—"],
        ["Sales",             "Group", "Customers · Receivables"],
        ["Purchases",         "Group", "Vendors · Payables"],
        ["Financial Reports", "Group", "Income Statement · Balance Sheet · Cash Flow · Trial Balance · Export"],
        ["AI Analyst",        "Group", "Forecast · Anomaly Detection · AI Insights"],
        ["AI Assistant",      "Link",  "—"],
        ["Settings",          "Link",  "—"],
    ], col_widths=[4.5*cm, 2.5*cm, 9.0*cm]))

    e.append(Paragraph("4.2 Sidebar Mechanics", S["h2"]))
    e.append(bullets([
        "<b>Collapsible</b> — toggles between 256-px (full text) and 80-px (icon-only) widths.",
        "<b>Auto-expand</b> — the group whose child is currently active opens automatically.",
        "<b>Manual override</b> — users can collapse/expand against the default; state is held in a local override map.",
        "<b>Icon-only mode</b> — collapses groups to flat icon lists (no chevron toggle), preserving discoverability.",
        "<b>Mobile</b> — same component re-rendered inside a 288-px <i>Drawer</i> sliding from the left.",
    ]))

    e.append(Paragraph("4.3 Header (Top Bar)", S["h2"]))
    e.append(Paragraph(
        "A sticky 64-px-tall header with backdrop-blur shows three elements: "
        "the hamburger toggle (mobile only), the page title derived from the "
        "URL via prefix matching, and a right cluster with a Bell icon "
        "(notifications placeholder) and a circular avatar showing the user's "
        "first initial in a cyan→emerald gradient.",
        S["body"]))

    e.append(Paragraph("4.4 Mobile Bottom Nav", S["h2"]))
    e.append(Paragraph(
        "On screens below the <i>lg</i> breakpoint (1024-px), a fixed bottom "
        "bar surfaces 5 high-frequency destinations: Home (Dashboard), Txns, "
        "AI, Reports, Settings. This avoids the friction of opening the "
        "drawer for the most common navigations.",
        S["body"]))

    e.extend(fit_image("23-mobile-sidebar-drawer.png", max_width_cm=8,
                       caption="Figure 4.2 — Mobile sidebar Drawer (≤ lg breakpoint). "
                       "Full nav including expandable groups slides over a navy/80 backdrop."))

    e.append(Paragraph("4.5 Findings", S["h2"]))
    e.append(bullets([
        "<b>Discoverability — Strong.</b> Every ERP concept lives where an accountant would expect (Sales/Purchases grouping, Reports under one parent).",
        "<b>Active-state clarity — Strong.</b> Active link gets cyan text, glass-panel background, and a subtle cyan glow.",
        "<b>Breadcrumb absent.</b> Deep pages like /customers/:id show only \"Customer Detail\" in the header — no path back via breadcrumb.",
        "<b>No command palette / quick search.</b> Best-in-class ERP UIs (Linear, NetSuite) offer Cmd-K — absent here.",
    ]))

    e.append(PageBreak())
    return e

# ───── Section 5 — Dashboard ─────────────────────────────────────────────────
def section_5():
    e = []
    e.append(Paragraph("5. Dashboard Analysis", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.extend(fit_image("02-dashboard.png", max_width_cm=16,
                       caption="Figure 5.1 — Dashboard YTD view. Seven KPI cards across two "
                       "rows; below them, twin charts (Revenue vs Expenses bar chart and Cash "
                       "Flow Trend) plus a Recent Transactions panel."))

    e.append(Paragraph("5.1 Composition", S["h2"]))
    e.append(styled_table([
        ["Region", "Content", "Source"],
        ["Header strip",  "Page title + welcome greeting + business name", "useAuthStore + useBusinessStore"],
        ["KPI row 1 (4)", "Revenue, Expenses, Net Profit, Cash Balance", "GET /dashboard/all → kpis"],
        ["KPI row 2 (3)", "Profit Margin %, Accounts Receivable, Accounts Payable", "Same call"],
        ["Chart 1",       "Revenue vs Expenses (monthly bars)", "kpis.revenueVsExpenses[]"],
        ["Chart 2",       "Net Cash Flow Trend (area/line)", "kpis.cashFlowTrend[]"],
        ["Recent Tx",     "Last 5 transactions w/ status badge", "GET /transactions?limit=5"],
        ["System Status", "4 service status pings (AI engine, reconciliation, ledger, reports)", "Static (placeholder)"],
    ], col_widths=[3.4*cm, 8.6*cm, 4.0*cm]))

    e.append(Paragraph("5.2 KPI Card Behaviour", S["h2"]))
    e.append(Paragraph(
        "Each card shows a <b>title</b> (uppercase muted), a <b>value</b> in "
        "Inter Black 24 px with tabular-num spacing, and an icon tinted "
        "<i>text-cyan opacity-50</i> in the top-right. A <i>trend</i> prop is "
        "accepted but currently renders only a coarse static label "
        "(\"Positive YTD\" / \"Negative YTD\") without a magnitude or "
        "comparison value. Best-in-class peers (QuickBooks, Stripe) show a "
        "real <i>+12.5% vs last month</i> with an absolute delta — a gap.",
        S["body"]))

    e.append(Paragraph("5.3 Backend Data Path", S["h2"]))
    e.append(code_block(
        "GET /api/v1/dashboard/all?startDate=2026-01-01&endDate=2026-05-23\n"
        "    │\n"
        "    ├─ reportCache.get('dashboard-all', businessId, params) → if hit, return\n"
        "    └─ Promise.all([\n"
        "          getKPIs(),               # → reportService.getKPISummary  (cached)\n"
        "          getRevenueVsExpensesChart(),  # MongoDB aggregate by month\n"
        "          getCashFlowTrend(),           # MongoDB aggregate by cash account\n"
        "       ])\n"
        "    → reportCache.set(...)  (5 minute TTL, invalidated on every tx write)\n"))

    e.append(Paragraph("5.4 Mobile Dashboard", S["h2"]))
    e.extend(fit_image("21-mobile-dashboard.png", max_width_cm=7,
                       caption="Figure 5.2 — Dashboard at 420-px width. KPI grid collapses "
                       "to 2 columns; charts stack; the AI Assistant button hovers above "
                       "the bottom MobileNav."))

    e.append(Paragraph("5.5 Findings", S["h2"]))
    e.append(bullets([
        "<b>Strengths:</b> Information-dense without feeling cluttered. Currency formatting respects business locale (PKR shown above).",
        "<b>Gap — fake trend.</b> Real period-over-period delta requires backend to surface <i>previousRevenue / previousExpenses</i>.",
        "<b>Gap — no drill-down.</b> Clicking a KPI card does nothing; investors expect KPI → underlying report navigation.",
        "<b>Gap — no AI Insights surface.</b> The dashboard has space for an \"AI noticed…\" callout but currently shows none.",
    ]))

    e.append(PageBreak())
    return e

# ───── Section 6 — Transactions ──────────────────────────────────────────────
def section_6():
    e = []
    e.append(Paragraph("6. Transaction Management UX", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.extend(fit_image("04-transactions.png", max_width_cm=16,
                       caption="Figure 6.1 — Transactions list. KPI strip (Total volume / "
                       "Income / Expenses / count), input methods (Form, NL parse, Excel "
                       "import), filters, and a sortable DataTable beneath."))

    e.append(Paragraph("6.1 Workflows Supported", S["h2"]))
    e.append(styled_table([
        ["Input method", "Trigger", "Notes"],
        ["Form modal",        "\"Record Transaction\" CTA",
         "Standard 1:1 journal — debit + credit dropdowns with grouped account picker"],
        ["Natural-Language",  "Inline NL input on /transactions",
         "Gemini-parsed preview, user confirms before posting"],
        ["Excel import",      "Drag-and-drop xlsx upload",
         "Bulk preview table → confirm → backend creates N journals in batches of 10"],
        ["Installment plan",  "Toggle in form modal",
         "Generates parent + N child entries via /transactions/installment"],
        ["Payment received/made", "Drawer on a Credit Sale/Purchase row",
         "Partial settlement — updates remainingBalance + paymentStatus"],
        ["Reversal",          "\"Reverse\" button on a posted row",
         "GAAP-style counter-entry; original marked REVERSED + linked"],
    ], col_widths=[3.8*cm, 4.6*cm, 7.6*cm]))

    e.append(Paragraph("6.2 Transaction Form Modal", S["h2"]))
    e.extend(fit_image("18-tx-form-modal.png", max_width_cm=15.5,
                       caption="Figure 6.2 — Record Transaction modal. Two-column layout: "
                       "left column for date/amount/accounts, right column for type/mode/"
                       "customer + installment toggle. Account dropdowns are grouped by "
                       "Chart-of-Accounts subtype with account codes shown inline."))

    e.append(Paragraph("6.3 Filters &amp; Search", S["h2"]))
    e.append(Paragraph(
        "Filters include date range, transaction type (Income / Expense / "
        "Credit Sale / etc.), account, payment status, customer, vendor, and "
        "free-text search. The search field hits a Mongo <i>$text</i> index "
        "on the description field (with a regex fallback). Filters debounce "
        "to avoid hammering the API on every keystroke. Filter state persists "
        "in the URL query string so a filtered view is shareable / bookmark-able.",
        S["body"]))

    e.append(Paragraph("6.4 DataTable Capabilities", S["h2"]))
    e.append(bullets([
        "<b>Sortable columns</b> — header click toggles ascending/descending with aria-sort updates.",
        "<b>Sticky header</b> — flag-controlled; useful when long tables scroll past the headings.",
        "<b>Zebra striping</b> — opt-in.",
        "<b>Dense mode</b> — px-4 py-2.5 vs default px-6 py-4.",
        "<b>Custom row key</b> — getRowKey override; falls back to _id, id, or row index.",
        "<b>Skeleton loading</b> — emits N skeleton rows that match column shape.",
        "<b>Empty state</b> — pluggable: pass an emptyIcon + emptyMessage or a full custom emptyState.",
        "<b>Keyboard activation</b> — Enter / Space on a row triggers onRowClick (tabIndex=0 + role=button).",
    ]))

    e.append(Paragraph("6.5 Reversal Workflow", S["h2"]))
    e.append(Paragraph(
        "Each posted transaction row exposes a Reverse button (hidden once "
        "<i>partiallyPaidAmount &gt; 0</i> or already reversed). It opens "
        "<b>TransactionReversalModal</b>: a warning banner, a read-only "
        "summary of the original entry, and a preview table showing the "
        "planned counter-entry with debit/credit flipped. The user can "
        "supply an optional reversal date and reason. Submission calls "
        "<i>POST /transactions/:id/reverse</i> → the new entry posts, the "
        "original gets <i>status: REVERSED</i> and a back-reference in "
        "<i>metadata.reversalId</i>.",
        S["body"]))

    e.append(Paragraph("6.6 Mobile Behaviour", S["h2"]))
    e.extend(fit_image("22-mobile-transactions.png", max_width_cm=7,
                       caption="Figure 6.3 — Transactions list at mobile width. Filters "
                       "collapse vertically; DataTable inherits horizontal scroll. The "
                       "Record Transaction CTA remains accessible above the table."))

    e.append(Paragraph("6.7 Findings", S["h2"]))
    e.append(bullets([
        "<b>Strength — three input methods cover everyone.</b> Power users (Excel), conversational users (NL), and form-driven users all served.",
        "<b>Strength — GAAP-compliant reversal.</b> Original entry stays immutable; reversal is a counter-entry, not a delete.",
        "<b>Gap — no virtualisation.</b> 5,000-row datasets will introduce frame drops on scroll. Recommend react-window or react-virtuoso integration.",
        "<b>Gap — no bulk-actions bar.</b> Multi-select reversal / tag / archive isn't possible.",
        "<b>Gap — no inline edit.</b> All edits route through a modal; spreadsheet-style cell-edit is a familiar accountant pattern.",
    ]))

    e.append(PageBreak())
    return e

# ───── Section 7 — AI ────────────────────────────────────────────────────────
def section_7():
    e = []
    e.append(Paragraph("7. AI Features UX Analysis", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph(
        "vousFin's AI surface is split across four interaction modes: a "
        "<b>Global AI Assistant FAB</b> available on every page, a unified "
        "<b>AI Analyst hub</b> with three sub-tabs (Forecast, Anomalies, "
        "Insights), a standalone <b>AI Assistant page</b>, and AI-augmented "
        "input mechanisms (natural-language transaction entry, Gemini-driven "
        "explanations).",
        S["body"]))

    e.append(Paragraph("7.1 Global AI Widget", S["h2"]))
    e.extend(fit_image("19-ai-widget-open.png", max_width_cm=16,
                       caption="Figure 7.1 — GlobalAIWidget panel open on the Dashboard. "
                       "Cyan bubble for user, glass-panel bubble for AI, route-contextual "
                       "suggested prompts visible above the input bar."))

    e.append(Paragraph(
        "The widget mounts once in DashboardLayout — chat history survives "
        "every route change. It has three states: collapsed FAB, anchored "
        "panel (380×520), and fullscreen. Suggested prompts are "
        "route-contextual: on /transactions it asks about unusual entries, "
        "on /financial-reports it offers to explain the income statement, "
        "on /ai-analyst/anomalies it asks why a flag fired. Markdown answers "
        "render bold/list/code with cyan-accented strong text.",
        S["body"]))

    e.append(Paragraph("7.2 AI Analyst — Forecast", S["h2"]))
    e.extend(fit_image("14-ai-forecast.png", max_width_cm=16,
                       caption="Figure 7.2 — AI Forecast tab. LSTM 6-month projection with "
                       "confidence band, drivers list, and per-period numeric breakdown. "
                       "Time range and granularity controls sit above the chart."))

    e.append(Paragraph(
        "The Forecast tab is wired to a Python LSTM microservice auto-started "
        "by the Node backend (<i>ensureLSTMRunning</i> in server.js). Output "
        "is rendered via Recharts: actual revenue/expense lines plus a "
        "shaded confidence band for the projection horizon.",
        S["body"]))

    e.append(Paragraph("7.3 AI Analyst — Anomalies", S["h2"]))
    e.extend(fit_image("15-ai-anomalies.png", max_width_cm=16,
                       caption="Figure 7.3 — Anomaly Detection. Score badges (Low / Medium "
                       "/ High / Critical), reason chips, review action buttons, and a "
                       "summary header showing total flagged."))

    e.append(Paragraph(
        "Anomalies are detected server-side by a custom JS Isolation Forest "
        "with 10-feature engineering (log-amount, z-score, day-of-week, "
        "hour-of-day, month, normalized-date, type-idx, mode-idx, "
        "account-pair-rarity, daily-velocity). For small datasets a hybrid "
        "heuristic blend kicks in. Results render as colour-coded cards with "
        "score, severity, fraud risk, and a one-click \"Review\" action that "
        "deep-links to the underlying transaction.",
        S["body"]))

    e.append(Paragraph("7.4 AI Analyst — Insights / Assistant", S["h2"]))
    e.extend(fit_image("16-ai-assistant.png", max_width_cm=16,
                       caption="Figure 7.4 — Standalone AI Assistant page. Full-canvas chat "
                       "surface with suggested prompts and markdown-rendered responses."))

    e.append(Paragraph("7.5 Hub Mechanics", S["h2"]))
    e.append(Paragraph(
        "<b>AIAnalystPage</b> implements a <b>mount-once / hide</b> tab "
        "strategy: a tab's component is rendered the first time it is "
        "visited and then kept mounted (hidden via <i>className=\"hidden\"</i>) "
        "on subsequent tab switches. This prevents the anomaly auto-scan and "
        "the forecast auto-run from re-firing on every tab change — a real "
        "API-thrash bug otherwise.",
        S["body"]))

    e.append(Paragraph("7.6 Findings", S["h2"]))
    e.append(bullets([
        "<b>Strength — pervasive AI surface.</b> Floating FAB + dedicated hub + per-page hooks.",
        "<b>Strength — route-contextual prompts.</b> Suggested questions adapt by URL (longest-prefix match).",
        "<b>Strength — markdown rendering with cyan-accented strong text.</b> Answers feel native, not chatbot-y.",
        "<b>Gap — no AI activity history per business.</b> Conversation persists only in memory.",
        "<b>Gap — confidence visualisation on Forecast lacks numeric labels.</b> Band is shaded but exact percentages are not surfaced.",
        "<b>Gap — no inline AI explanation on report rows.</b> The hooks exist; the surface does not.",
    ]))

    e.append(PageBreak())
    return e

# ───── Section 8 — Reports ───────────────────────────────────────────────────
def section_8():
    e = []
    e.append(Paragraph("8. Financial Reports Analysis", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph(
        "Five financial reports live behind a unified <i>/financial-reports/:tab</i> "
        "hub: Income Statement, Balance Sheet, Cash Flow, Trial Balance, "
        "Export. The hub uses mount-once-hide tab semantics: switching tabs "
        "doesn't re-fetch already-loaded reports, so users can A/B compare "
        "without latency.",
        S["body"]))

    e.append(Paragraph("8.1 Income Statement", S["h2"]))
    e.extend(fit_image("09-income-statement.png", max_width_cm=16,
                       caption="Figure 8.1 — Income Statement (P&L). Revenue accounts, "
                       "COGS, Operating Expenses, Gross Profit, and Net Income with period "
                       "controls and Export buttons in the header."))

    e.append(Paragraph("8.2 Balance Sheet", S["h2"]))
    e.extend(fit_image("10-balance-sheet.png", max_width_cm=16,
                       caption="Figure 8.2 — Balance Sheet. Three-section vertical layout "
                       "(Assets, Liabilities, Equity) with a validity indicator confirming "
                       "Assets = Liabilities + Equity at the bottom."))

    e.append(Paragraph("8.3 Cash Flow Statement", S["h2"]))
    e.extend(fit_image("11-cash-flow.png", max_width_cm=16,
                       caption="Figure 8.3 — Cash Flow Statement. Indirect method derived "
                       "from cash/bank account turnover within the selected period."))

    e.append(Paragraph("8.4 Trial Balance", S["h2"]))
    e.extend(fit_image("12-trial-balance.png", max_width_cm=16,
                       caption="Figure 8.4 — Trial Balance as of selected date. All "
                       "accounts in account-code order with debit/credit columns plus a "
                       "balanced/unbalanced indicator on the totals row."))

    e.append(Paragraph("8.5 Export Hub", S["h2"]))
    e.extend(fit_image("13-export.png", max_width_cm=16,
                       caption="Figure 8.5 — Export Reports. PDF and Excel export buttons "
                       "per report (server-rendered via pdfkit and SheetJS respectively)."))

    e.append(Paragraph("8.6 Data Path", S["h2"]))
    e.append(code_block(
        "Income Statement      → /reports/income-statement?startDate&endDate\n"
        "Balance Sheet         → /reports/balance-sheet?asOfDate\n"
        "Cash Flow             → /reports/cash-flow?startDate&endDate\n"
        "Trial Balance         → /reports/trial-balance?asOfDate\n"
        "\n"
        "All four are reportCache-wrapped on the backend (5 min TTL).\n"
        "_getBalancesAsOf() runs a single $facet aggregation against MongoDB,\n"
        "replacing the legacy populate-and-loop-in-JS approach.\n"))

    e.append(Paragraph("8.7 Findings", S["h2"]))
    e.append(bullets([
        "<b>Strength — every GAAP-relevant report covered.</b> P&amp;L, Balance Sheet, Cash Flow, Trial Balance.",
        "<b>Strength — tab persistence.</b> Switching between Balance Sheet and Income Statement is instant after first load.",
        "<b>Strength — balanced indicator.</b> Trial Balance explicitly shows ✓ Balanced when DR == CR.",
        "<b>Gap — no expand/collapse on account groups.</b> Long Asset/Liability lists scroll past totals.",
        "<b>Gap — no sticky totals row.</b> Bottom-of-page totals fall off-screen during scroll.",
        "<b>Gap — no period comparison.</b> Cannot view \"Q1 2026 vs Q1 2025\" side by side.",
        "<b>Gap — no drill-down.</b> Clicking an account line should open its ledger; currently inert.",
        "<b>Gap — no trend indicators</b> next to category subtotals.",
    ]))

    e.append(PageBreak())
    return e

# ───── Section 9 — Responsiveness ────────────────────────────────────────────
def section_9():
    e = []
    e.append(Paragraph("9. Responsiveness &amp; Mobile Analysis", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph(
        "vousFin responds to viewport size via Tailwind's <i>sm / md / lg / "
        "xl / 2xl</i> breakpoints. The <i>lg</i> breakpoint (1024 px) is the "
        "primary pivot: above it, the sidebar is permanent; below, it "
        "collapses to a slide-in Drawer and the MobileNav bottom bar appears.",
        S["body"]))

    e.append(Paragraph("9.1 Side-by-side comparison", S["h2"]))
    tbl = Table([
        [RLImage(os.path.join(SCREENSHOTS_DIR, "21-mobile-dashboard.png"),
                  width=7*cm, height=12.5*cm),
         RLImage(os.path.join(SCREENSHOTS_DIR, "22-mobile-transactions.png"),
                  width=7*cm, height=12.5*cm)],
        ["Dashboard at 420 px", "Transactions at 420 px"],
    ], colWidths=[8*cm, 8*cm])
    tbl.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTSIZE", (0,1), (-1,1), 8.5),
        ("TEXTCOLOR", (0,1), (-1,1), SLATE_500),
        ("BOTTOMPADDING", (0,0), (-1,0), 4),
    ]))
    e.append(tbl)

    e.append(Paragraph("9.2 Adaptive Behaviour", S["h2"]))
    e.append(styled_table([
        ["Element", "≥ lg (≥ 1024 px)", "&lt; lg"],
        ["Sidebar",     "Permanent, 256-px (or 80-px collapsed)", "Hidden until hamburger tap → 288-px Drawer"],
        ["MobileNav",   "Hidden", "Fixed 5-icon bottom bar"],
        ["Header",      "Page title + Bell + avatar + initial", "+ Hamburger menu icon on the left"],
        ["KPI grid",    "4 columns on lg / 3 columns on sm-md", "2 columns; secondary KPI row stacks to single column"],
        ["Charts",      "Side-by-side xl:grid-cols-2", "Vertically stacked"],
        ["Tables",      "Sticky header + horizontal scroll", "Horizontal scroll inside parent; row text-sm"],
        ["Modal",       "Centered, max-w-xl", "Centered, full-width within margin"],
        ["AI FAB",      "Bottom-right, lg:bottom-6", "Bottom-right, bottom-20 (above MobileNav)"],
    ], col_widths=[2.8*cm, 6.6*cm, 6.6*cm]))

    e.append(Paragraph("9.3 Reports on mobile", S["h2"]))
    e.extend(fit_image("24-mobile-income-statement.png", max_width_cm=7,
                       caption="Figure 9.1 — Income Statement at 420-px. Tab strip "
                       "horizontally scrolls; period control wraps; section totals remain "
                       "readable but the dense column layout requires horizontal scroll."))

    e.append(Paragraph("9.4 Findings", S["h2"]))
    e.append(bullets([
        "<b>Strength — Drawer + MobileNav</b> covers thumb-zone ergonomics for mobile.",
        "<b>Strength — KPI grid degrades gracefully</b> (2 columns at 420 px without truncation).",
        "<b>Gap — report tables</b> use horizontal scroll instead of an adaptive card-list mode.",
        "<b>Gap — Transaction filters</b> stack as a tall vertical list on mobile; an accordion would compact this.",
        "<b>Gap — No tablet-specific layout</b> — md (768 px) currently inherits the mobile behaviour, but two-column hybrids would scale better.",
    ]))

    e.append(PageBreak())
    return e

# ───── Section 10 — Performance UX ───────────────────────────────────────────
def section_10():
    e = []
    e.append(Paragraph("10. Performance UX Analysis", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph(
        "Frontend perceived performance is dictated by three forces: bundle "
        "size at first paint, network latency for data, and render cost on "
        "subsequent interactions. vousFin handles the first two well; the "
        "third has a soft ceiling that becomes audible past a few thousand "
        "rows.",
        S["body"]))

    e.append(Paragraph("10.1 Network &amp; Caching", S["h2"]))
    e.append(styled_table([
        ["Layer", "Mechanism", "Effect"],
        ["React Query staleTime",   "5 min default",
         "Revisits to a page within the window skip refetch entirely"],
        ["Backend report cache",     "5 min in-memory TTL, businessId-scoped",
         "Repeated report renders hit memory, not Mongo aggregation"],
        ["Cache invalidation",       "On every tx write",
         "No stale totals after a create / edit / reverse / delete"],
        ["MongoDB $facet aggregation", "_getBalancesAsOf() single pass",
         "Replaces N-document populate + JS loop with one round trip"],
        ["Compound indexes",         "idx_report_core / idx_listing_sorted / idx_ledger_*",
         "Match-stage hits index, no collection scan"],
        ["Text search index",         "{description: 'text'} on JournalEntry",
         "O(1) $text search vs. O(n) regex fallback"],
    ], col_widths=[4.0*cm, 5.0*cm, 7.0*cm]))

    e.append(Paragraph("10.2 Render Performance", S["h2"]))
    e.append(bullets([
        "<b>Lazy routes</b> reduce first-load JS substantially — only Login + auth shell ship in initial chunk.",
        "<b>SkeletonLoader</b> bridges the gap between route mount and data arrival so users never see blank panes.",
        "<b>animate-fade-in</b> (200 ms) softens layout pop on mount.",
        "<b>useMemo + useCallback</b> applied to expensive computations (filter parsing, route-prompt resolution).",
        "<b>No virtualisation yet</b> — DataTable renders every row; scrolling 5K+ rows will frame-drop on mid-range laptops.",
    ]))

    e.append(Paragraph("10.3 Recommendations", S["h2"]))
    e.append(callout(
        "Largest payoff: virtualise DataTable",
        "Adopting <i>react-window</i> or <i>react-virtuoso</i> behind the same "
        "Column API would lift the row-count ceiling from ~2K to ~100K with "
        "constant memory. Sticky-header continues to work via fixed-position. "
        "Estimated effort: ~1 day for a single virtualised list + sortable + "
        "selectable rows.",
        color_left=GREEN))

    e.append(PageBreak())
    return e

# ───── Section 11 — Accessibility ────────────────────────────────────────────
def section_11():
    e = []
    e.append(Paragraph("11. Accessibility &amp; Usability", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph("11.1 What's Present", S["h2"]))
    e.append(bullets([
        "<b>aria-label</b> on icon-only buttons (sidebar toggle, drawer close, AI FAB).",
        "<b>aria-haspopup / aria-expanded</b> on the Select trigger.",
        "<b>aria-sort</b> + clickable headers in DataTable.",
        "<b>role=\"dialog\" + aria-modal=\"true\"</b> on Drawer.",
        "<b>tabIndex + Enter/Space activation</b> on DataTable clickable rows.",
        "<b>Focus ring</b> visible on focusable elements (focus:ring-cyan/30).",
        "<b>sr-only</b> labels for screen readers on icon buttons.",
        "<b>Escape</b> closes Drawer, AI widget (collapse → close), and Select.",
    ]))

    e.append(Paragraph("11.2 What Needs Attention", S["h2"]))
    e.append(bullets([
        "<b>No focus trap inside Modal</b> — tabbing escapes back to the page.",
        "<b>Contrast on muted text</b> — text-muted (#64748B) on dark navy "
        "approaches but doesn't always exceed 4.5:1 WCAG-AA.",
        "<b>Skip-to-content link absent</b> — keyboard-only users tab through the whole sidebar before reaching main.",
        "<b>Toast messages</b> auto-dismiss in 4 s with no \"keep open longer\" option for low-vision users.",
        "<b>No prefers-reduced-motion media query</b> — animations fire regardless of OS preference.",
        "<b>Form errors</b> announce visually but aria-live regions for SR users are inconsistent.",
    ]))

    e.append(Paragraph("11.3 Usability Heuristics", S["h2"]))
    e.append(styled_table([
        ["Heuristic (Nielsen)", "Rating", "Comment"],
        ["Visibility of system status", "Strong",   "Skeletons, toasts, loading spinners everywhere"],
        ["Match real-world (accounting)", "Strong", "Sales / Purchases grouping mirrors the textbook"],
        ["User control &amp; freedom",     "Strong", "Reversal pattern, edit/delete with confirmation, undo via reverse"],
        ["Consistency &amp; standards",    "Strong", "Token-driven; deviations rare"],
        ["Error prevention",              "Mixed",  "Form validation present; bulk-import has preview-before-commit; no \"are you sure?\" on Logout"],
        ["Recognition &gt; recall",        "Strong", "Icons + labels on every nav item, account codes shown in dropdowns"],
        ["Flexibility &amp; efficiency",   "Mixed",  "No keyboard shortcuts or Cmd-K"],
        ["Aesthetic &amp; minimalist",     "Strong", "Dark theme + clean grids — no decoration overload"],
        ["Help users recover from errors", "Mixed",  "Toasts surface error messages; inline form errors clear; no inline help on \"Why is this account disabled?\""],
        ["Help &amp; documentation",       "Weak",   "No in-app help / tour / shortcut sheet"],
    ], col_widths=[4.6*cm, 2.0*cm, 9.4*cm]))

    e.append(PageBreak())
    return e

# ───── Section 12 — Visual Gallery ───────────────────────────────────────────
def section_12():
    e = []
    e.append(Paragraph("12. Visual Gallery", S["h1"]))
    e.append(hr(BRAND, 1.5))
    e.append(Paragraph(
        "A direct, annotated tour of every major surface. Each screenshot "
        "was captured live from <i>http://localhost:5173</i> on May 23, 2026 "
        "at 1440×900 (desktop) or 420×900 (mobile).",
        S["body"]))

    gallery = [
        ("01-login.png",            "Figure 12.1 — Login page. Centered card, gradient Sign In button."),
        ("20-register.png",         "Figure 12.2 — Register page. Same dark theme, additional fields, validation triggers inline."),
        ("02-dashboard.png",        "Figure 12.3 — Dashboard. 7 KPIs, twin charts, recent transactions, system status."),
        ("03-accounts.png",         "Figure 12.4 — Chart of Accounts. Grouped by accountType, running balances on the right."),
        ("04-transactions.png",     "Figure 12.5 — Transactions list. Filter strip, KPI strip, sortable table."),
        ("18-tx-form-modal.png",    "Figure 12.6 — Record Transaction modal. Two-column form, grouped account selects."),
        ("05-customers.png",        "Figure 12.7 — Customers list. AR totals card + searchable table."),
        ("06-receivables.png",      "Figure 12.8 — Receivables. Aging buckets + outstanding invoice table."),
        ("07-vendors.png",          "Figure 12.9 — Vendors list. Mirror of Customers for the AP side."),
        ("08-payables.png",         "Figure 12.10 — Payables. Aging buckets + outstanding bill table."),
        ("09-income-statement.png", "Figure 12.11 — Income Statement. Revenue / COGS / OpEx / Net Income."),
        ("10-balance-sheet.png",    "Figure 12.12 — Balance Sheet. Three-section vertical with balance check."),
        ("11-cash-flow.png",        "Figure 12.13 — Cash Flow Statement. Indirect method, period control."),
        ("12-trial-balance.png",    "Figure 12.14 — Trial Balance. DR/CR per account + totals row."),
        ("13-export.png",           "Figure 12.15 — Export hub. PDF + Excel per report."),
        ("14-ai-forecast.png",      "Figure 12.16 — AI Forecast (LSTM)."),
        ("15-ai-anomalies.png",     "Figure 12.17 — Anomaly Detection (Isolation Forest)."),
        ("16-ai-assistant.png",     "Figure 12.18 — AI Assistant standalone page."),
        ("19-ai-widget-open.png",   "Figure 12.19 — Global AI widget open on Dashboard."),
        ("17-settings.png",         "Figure 12.20 — Business Settings."),
        ("23-mobile-sidebar-drawer.png", "Figure 12.21 — Mobile sidebar Drawer."),
        ("24-mobile-income-statement.png", "Figure 12.22 — Income Statement on mobile."),
    ]
    for i, (fn, cap) in enumerate(gallery):
        e.extend(fit_image(fn, max_width_cm=14.5, max_height_cm=10, caption=cap))
        if i % 2 == 1:
            e.append(PageBreak())
    if len(gallery) % 2 == 1:
        e.append(PageBreak())
    return e

# ───── Section 13 — Strengths ────────────────────────────────────────────────
def section_13():
    e = []
    e.append(Paragraph("13. Frontend Strengths", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph("13.1 Architectural", S["h2"]))
    e.append(bullets([
        "<b>Clear separation of concerns</b> — ui/ (dark dashboard), common/ (light auth), pages/ (domain), layouts/ (chrome).",
        "<b>Auth-flow guards</b> deterministic and centralised in routes.jsx.",
        "<b>Single QueryClient + Axios singleton</b> avoid configuration drift.",
        "<b>Zustand singletons</b> for cross-route state (auth, business, AI chat) — no prop drilling.",
        "<b>React.lazy everywhere</b> — no bloated initial bundle.",
    ]))

    e.append(Paragraph("13.2 Visual &amp; UX", S["h2"]))
    e.append(bullets([
        "<b>Brand-consistent dark theme</b> with cyan + emerald gradients across 25 pages.",
        "<b>Glass-panel aesthetic</b> avoids the \"hand-rolled\" look common to FYP projects.",
        "<b>Information density without clutter</b> — comparable to Zoho Books at MVP scale.",
        "<b>Subtle motion</b> — fade-in on mount, slide-up on bubble, no carousel/parallax noise.",
    ]))

    e.append(Paragraph("13.3 ERP Workflows", S["h2"]))
    e.append(bullets([
        "<b>Three input methods for transactions</b> — form, natural-language, Excel import.",
        "<b>GAAP-compliant reversal</b> — counter-entry pattern, no destructive deletes.",
        "<b>AR/AP first-class</b> — Receivables / Payables / Aging / Settlement engine all surface in UI.",
        "<b>Multi-line journals supported</b> in the schema and form (future-proof for compound entries).",
        "<b>Installment plans</b> render as parent + N child rows with status linkage.",
    ]))

    e.append(Paragraph("13.4 AI Integration", S["h2"]))
    e.append(bullets([
        "<b>GlobalAIWidget</b> persists across navigations — chat doesn't reset on every page.",
        "<b>Route-contextual suggested prompts</b> via longest-prefix matching.",
        "<b>Anomaly + Forecast unified</b> in AI Analyst hub with mount-once-hide.",
        "<b>Markdown-rendered answers</b> with cyan-accented strong text — feels native.",
    ]))

    e.append(PageBreak())
    return e

# ───── Section 14 — Weaknesses ───────────────────────────────────────────────
def section_14():
    e = []
    e.append(Paragraph("14. Frontend Weaknesses", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph("14.1 Design System", S["h2"]))
    e.append(bullets([
        "<b>emerald token is a colour-name lie</b> — DEFAULT/2/3 are cyan/blue, not green.",
        "<b>No semantic financial tokens</b> (positive / negative / warning / info).",
        "<b>No elevation scale</b> beyond shadow-card and shadow-elevated.",
        "<b>No z-index token map</b> — random integer literals across overlays.",
        "<b>Two parallel button libraries</b> (common/ light vs ui/ dark) without documented purpose.",
    ]))

    e.append(Paragraph("14.2 KPI &amp; Trend Display", S["h2"]))
    e.append(bullets([
        "<b>Fake trend label</b> — KPICard \"Positive YTD\" / \"Negative YTD\" with no real delta.",
        "<b>No period-over-period comparison</b> data flowing from backend kpis payload.",
        "<b>No drill-down on KPI click</b> — dead surface for power users.",
    ]))

    e.append(Paragraph("14.3 Data Grid &amp; Tables", S["h2"]))
    e.append(bullets([
        "<b>No virtualisation</b> — DataTable's row ceiling around 2K rows before perceptible scroll lag.",
        "<b>No bulk-actions bar</b> — multi-select reverse / archive / tag impossible.",
        "<b>No inline cell-edit</b> — every change routes through a modal.",
        "<b>No column visibility toggle</b> — users can't hide noisy columns.",
        "<b>No saved views</b> — filters reset on URL change.",
    ]))

    e.append(Paragraph("14.4 Reports", S["h2"]))
    e.append(bullets([
        "<b>No expand/collapse</b> on account groupings in Balance Sheet / Income Statement.",
        "<b>No sticky totals row</b> — bottoms scroll off-screen.",
        "<b>No period comparison</b> — Q1 2026 vs Q1 2025 side-by-side impossible.",
        "<b>No drill-down</b> to underlying journal entries from a report line.",
        "<b>No chart per report</b> — Balance Sheet has no visualisation of the equation.",
        "<b>Cash Flow indirect method</b> shows only \"Net Cash from Operations\" totals; Investing/Financing categories empty.",
    ]))

    e.append(Paragraph("14.5 Forms &amp; Inputs", S["h2"]))
    e.append(bullets([
        "<b>Dense Transaction Form Modal</b> — fits on desktop but is tall on mobile (vertical scroll within modal).",
        "<b>No keyboard navigation between form fields</b> beyond default tab order.",
        "<b>No autocomplete-from-prior-entries</b> on description / reference fields.",
        "<b>No save-as-draft</b> on long forms.",
    ]))

    e.append(Paragraph("14.6 Navigation &amp; Discoverability", S["h2"]))
    e.append(bullets([
        "<b>No breadcrumb component</b> — deep pages show only \"Customer Detail\" with no path back.",
        "<b>No command palette (Cmd-K)</b> — costs power-users a search-by-keyboard workflow.",
        "<b>No recent-activity feed</b> beyond the dashboard's Recent Transactions panel.",
    ]))

    e.append(Paragraph("14.7 Accessibility &amp; Performance", S["h2"]))
    e.append(bullets([
        "<b>No focus trap inside Modal</b>.",
        "<b>No prefers-reduced-motion handling</b>.",
        "<b>No skip-to-content link</b>.",
        "<b>No Lighthouse-budget enforcement</b> in CI.",
        "<b>No service-worker / offline mode</b>.",
    ]))

    e.append(PageBreak())
    return e

# ───── Section 15 — Enterprise Readiness ─────────────────────────────────────
def section_15():
    e = []
    e.append(Paragraph("15. Enterprise Readiness Assessment", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph("15.1 Scorecard", S["h2"]))
    e.append(styled_table([
        ["Dimension", "Score", "Comment"],
        ["Visual maturity",          "8 / 10", "Brand-consistent, dark theme, glass-panel aesthetic"],
        ["Architectural quality",    "8 / 10", "Clean separation, lazy routes, single QueryClient, Zustand singletons"],
        ["ERP feature completeness", "7 / 10", "Core GAAP reports + AR/AP + reversal + AI; drill-down + period compare missing"],
        ["AI UX",                    "8 / 10", "Global + hub + route-contextual; explainability surface incomplete"],
        ["Scalability (data volume)","5 / 10", "No virtualisation; OK to ~2K rows, degrades beyond"],
        ["Responsiveness",           "6 / 10", "Drawer + MobileNav strong; tablet layout + report table cards weak"],
        ["Accessibility",            "5 / 10", "ARIA basics present; focus-trap + prefers-reduced-motion gaps"],
        ["Performance UX",           "8 / 10", "Backend cache + React Query staleTime + skeletons; render ceiling untested"],
        ["SaaS readiness (multi-tenant)", "7 / 10", "Business-scoped queries throughout; no tenant-switching UI in product"],
        ["Investor / Demo readiness","9 / 10", "Looks and feels like a Series-A SaaS dashboard end-to-end"],
    ], col_widths=[5.0*cm, 2.0*cm, 9.0*cm]))

    e.append(Paragraph("15.2 Side-by-side with reference products", S["h2"]))
    e.append(styled_table([
        ["Feature",          "vousFin", "QuickBooks Online", "Xero", "Zoho Books"],
        ["Double-entry ledger",         "Yes", "Yes", "Yes", "Yes"],
        ["AR / AP + aging",             "Yes", "Yes", "Yes", "Yes"],
        ["GAAP reversal pattern",       "Yes", "Yes", "Yes", "Yes"],
        ["AI assistant in-product",     "Yes", "Yes (limited)", "Limited", "Yes (Zia)"],
        ["AI forecasting",              "Yes (LSTM)", "Partial", "No", "Partial"],
        ["Anomaly detection",           "Yes (Isolation Forest)", "Limited", "Limited", "Limited"],
        ["Bulk Excel import",           "Yes", "Yes", "Yes", "Yes"],
        ["Mobile responsive",           "Yes", "Yes (native app)", "Yes (native app)", "Yes (native app)"],
        ["Drill-down from report",      "No",  "Yes", "Yes", "Yes"],
        ["Period comparison",           "No",  "Yes", "Yes", "Yes"],
        ["Custom dashboards",           "No",  "Yes", "Limited", "Yes"],
        ["Multi-currency",              "Schema only", "Yes", "Yes", "Yes"],
        ["Native mobile apps",          "No",  "Yes", "Yes", "Yes"],
    ], col_widths=[4.4*cm, 2.4*cm, 3.0*cm, 2.2*cm, 3.0*cm], font_size=8))

    e.append(Paragraph("15.3 Overall verdict", S["h2"]))
    e.append(callout(
        "Investor / FYP / mid-market SaaS-ready (B). Enterprise-ready (A): four sprints away.",
        "vousFin already feels like a real SaaS product — visually, "
        "architecturally, and behaviourally. To stand alongside QuickBooks "
        "Online / Xero / Zoho Books on feature parity, the gaps are "
        "well-known and small: design-system semantic tokens, real "
        "period-over-period trend, virtualised data grid, expand/collapse "
        "+ drill-down + period-compare on reports, focus-trap + reduced-motion "
        "accessibility passes. Each is a 1–3-day item. The result would be a "
        "frontend indistinguishable from the major commercial peers.",
        color_left=GREEN))

    e.append(PageBreak())
    return e

# ───── Section 16 — Recommended Improvements ─────────────────────────────────
def section_16():
    e = []
    e.append(Paragraph("16. Recommended Improvements", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph(
        "Recommendations are organised by priority (Critical → Low). Each "
        "entry names the file or surface, the action, the rationale, and an "
        "effort estimate.",
        S["body"]))

    e.append(Paragraph("16.1 Critical", S["h2"]))
    e.append(styled_table([
        ["#", "Action", "File / Surface", "Effort"],
        ["C1", "Add semantic financial tokens (positive · negative · warning · info · neutral)",
         "tailwind.config.js", "1 h"],
        ["C2", "Fix Badge `success` variant to use real green (currently renders cyan)",
         "components/ui/Badge.jsx", "15 min"],
        ["C3", "Surface previousValue on /dashboard/all and KPISummary endpoint",
         "report.service.js + dashboard.service.js", "2 h"],
        ["C4", "Wire previousValue into KPICard for real ±% display",
         "components/ui/KPICard.jsx + Dashboard.jsx", "1 h"],
        ["C5", "Add focus-trap inside Modal + Drawer",
         "components/modals/Modal.jsx + components/ui/Drawer.jsx", "2 h"],
    ], col_widths=[1.2*cm, 7.8*cm, 5.4*cm, 1.6*cm]))

    e.append(Paragraph("16.2 High", S["h2"]))
    e.append(styled_table([
        ["#", "Action", "File / Surface", "Effort"],
        ["H1", "Virtualise DataTable (react-window or react-virtuoso)",
         "components/tables/DataTable.jsx", "1 d"],
        ["H2", "Sticky totals row + expand/collapse on account groups",
         "components/reports/BalanceSheetTable.jsx + IncomeStatementTable.jsx", "1 d"],
        ["H3", "Drill-down from report line → ledger view",
         "All report tables + new /ledger/:accountId page", "1.5 d"],
        ["H4", "Period comparison toggle (this period vs same prior period)",
         "Report hub + backend KPI/report endpoints (compute prev period)", "1 d"],
        ["H5", "Bulk-action bar in DataTable (multi-select + actions)",
         "components/tables/DataTable.jsx + TransactionsList.jsx", "1 d"],
        ["H6", "Breadcrumb component for deep detail pages",
         "components/layout/Breadcrumbs.jsx + DashboardLayout.jsx", "0.5 d"],
        ["H7", "Command palette (Cmd-K) with route + transaction-search",
         "New components/CommandPalette.jsx + global hotkey listener", "1 d"],
        ["H8", "AI Insights panel on Dashboard (\"AI noticed…\" callout cards)",
         "pages/dashboard/Dashboard.jsx + new component", "1 d"],
    ], col_widths=[1.2*cm, 7.8*cm, 5.4*cm, 1.6*cm]))

    e.append(Paragraph("16.3 Medium", S["h2"]))
    e.append(styled_table([
        ["#", "Action", "File / Surface", "Effort"],
        ["M1", "Standardize EmptyState + SkeletonLoader usage across all list pages",
         "All list pages",  "1 d"],
        ["M2", "Tablet-specific (md) responsive layout for Reports tables",
         "Report table components", "0.5 d"],
        ["M3", "PageHeader primitive (DRY for h1 + icon + subtitle + action button)",
         "components/ui/PageHeader.jsx + 10 page updates", "0.5 d"],
        ["M4", "StatCard primitive for smaller in-page stats",
         "components/ui/StatCard.jsx + Customer/Vendor detail pages", "0.5 d"],
        ["M5", "Enterprise elevation scale (shadow-e-1 … e-5) + sticky-header shadow",
         "tailwind.config.js + DataTable.jsx", "0.5 d"],
        ["M6", "Z-index token map (dropdown · sticky · drawer · modal · popover · tooltip · toast · ai-fab)",
         "tailwind.config.js + overlay components", "0.5 d"],
        ["M7", "Investing + Financing categorisation in Cash Flow Statement",
         "report.service.js + UI", "0.5 d"],
        ["M8", "prefers-reduced-motion media query",
         "index.css (gate animations)", "30 min"],
        ["M9", "Skip-to-content link in DashboardLayout",
         "layouts/DashboardLayout.jsx", "15 min"],
    ], col_widths=[1.2*cm, 7.8*cm, 5.4*cm, 1.6*cm]))

    e.append(Paragraph("16.4 Low", S["h2"]))
    e.append(styled_table([
        ["#", "Action", "File / Surface", "Effort"],
        ["L1", "Recent activity feed (system-wide, not just transactions)",
         "Dashboard widget", "1 d"],
        ["L2", "Customizable dashboards (drag-and-drop widget layout)",
         "react-grid-layout + persistence", "3 d"],
        ["L3", "Save-as-draft on Transaction Form",
         "TransactionFormModal.jsx + localStorage", "0.5 d"],
        ["L4", "Autocomplete-from-prior-entries on description field",
         "TransactionFormModal.jsx + history API", "0.5 d"],
        ["L5", "In-app help / shortcut sheet (\"?\" overlay)",
         "New help modal", "0.5 d"],
        ["L6", "Service-worker for offline reads",
         "Vite PWA plugin", "1 d"],
        ["L7", "Tour/onboarding (first-run walkthrough)",
         "shepherd.js or similar + product copy", "1.5 d"],
        ["L8", "Native mobile app (React Native or Expo)",
         "New repo / monorepo", "weeks"],
    ], col_widths=[1.2*cm, 7.8*cm, 5.4*cm, 1.6*cm]))

    e.append(Paragraph("16.5 Suggested 4-Sprint Roadmap", S["h2"]))
    e.append(styled_table([
        ["Sprint", "Theme", "Deliverables"],
        ["1", "Design system + KPI truthfulness",
         "C1 · C2 · C3 · C4 · C5 · M3 · M4 · M5 · M6"],
        ["2", "Reports + drill-down",
         "H2 · H3 · H4 · M7"],
        ["3", "Scale &amp; power-user UX",
         "H1 · H5 · H7 · H8 · M1"],
        ["4", "Polish &amp; accessibility",
         "H6 · M2 · M8 · M9 · L1 · L3 · L5"],
    ], col_widths=[1.6*cm, 5.8*cm, 8.6*cm]))

    e.append(PageBreak())
    return e

# ───── Section 17 — Conclusion ───────────────────────────────────────────────
def section_17():
    e = []
    e.append(Paragraph("17. Final Conclusion", S["h1"]))
    e.append(hr(BRAND, 1.5))

    e.append(Paragraph(
        "VousFin's frontend is, today, a confident-feeling React 19 SPA that "
        "presents itself as a professional dark-theme SaaS accounting "
        "platform. It already covers the four core financial reports, AR/AP "
        "workflows, double-entry ledger, multi-input transaction entry, AI "
        "forecasting, and AI anomaly detection — wrapped in a global AI "
        "assistant that travels with the user across every route. The "
        "architecture is sensible (lazy routes, guarded layouts, "
        "single QueryClient, Zustand singletons), the component library is "
        "consistent (a real <i>components/ui/</i> directory), and the visual "
        "language is brand-coherent end-to-end.",
        S["body"]))

    e.append(Paragraph(
        "Where it falls short of QuickBooks Online / Xero / Zoho Books is "
        "predictable and bounded: a missing semantic colour palette, a "
        "KPI trend that shows a label without a number, reports that lack "
        "drill-down + expand-collapse + period-compare, a non-virtualised "
        "data grid, and an accessibility pass that needs to land focus-trap "
        "and reduced-motion. Each gap is well-defined; none is structural; "
        "all together they form a focused 3–4 sprint plan to enterprise-level "
        "polish.",
        S["body"]))

    e.append(Paragraph("17.1 Final Scores", S["h2"]))
    e.append(styled_table([
        ["Score",             "Rating", "Out of"],
        ["Frontend maturity",                 "7.5", "10"],
        ["UX quality",                        "7.5", "10"],
        ["Visual quality",                    "8.5", "10"],
        ["Scalability (architecture)",        "8.0", "10"],
        ["Scalability (data volume)",         "5.0", "10"],
        ["Enterprise readiness",              "7.0", "10"],
        ["Investor / demo readiness",         "9.0", "10"],
        ["Modernization readiness",           "8.5", "10"],
    ], col_widths=[8.0*cm, 4.0*cm, 4.0*cm]))

    e.append(Paragraph("17.2 Modernization Outlook", S["h2"]))
    e.append(callout(
        "VousFin is closer to a commercial-grade SaaS accounting product than its FYP origin suggests.",
        "The structural decisions are right; the remaining work is targeted "
        "polish, not refactoring. With the 4-sprint roadmap in Section 16.5 "
        "executed, the frontend would compare favourably to the three "
        "reference SaaS accounting platforms it currently emulates, and "
        "could plausibly be presented to a paying SME customer or a Series-A "
        "investor as a production candidate.",
        color_left=GREEN))

    e.append(Spacer(1, 1*cm))
    e.append(hr(SLATE_300, 0.5))
    e.append(Spacer(1, 5*mm))
    e.append(Paragraph(
        "<b>End of report.</b>  &nbsp; &nbsp; — vousFin Frontend Design &amp; UX Audit · "
        f"prepared {datetime.now().strftime('%B %Y')}.",
        ParagraphStyle("end", parent=S["caption"], alignment=TA_LEFT,
                       textColor=SLATE_500, fontSize=9)))
    return e

# ────────────────────────────────────────────────────────────────────────────
# Assembly
# ────────────────────────────────────────────────────────────────────────────
def build():
    doc = AuditDoc(OUTPUT_PDF)
    story = []
    story.extend(cover())
    # Switch to Body template for everything after cover
    from reportlab.platypus.doctemplate import NextPageTemplate
    story.insert(0, NextPageTemplate("Cover"))
    story.append(NextPageTemplate("Body"))
    story.extend(toc_page())
    story.extend(section_1())
    story.extend(section_2())
    story.extend(section_3())
    story.extend(section_4())
    story.extend(section_5())
    story.extend(section_6())
    story.extend(section_7())
    story.extend(section_8())
    story.extend(section_9())
    story.extend(section_10())
    story.extend(section_11())
    story.extend(section_12())
    story.extend(section_13())
    story.extend(section_14())
    story.extend(section_15())
    story.extend(section_16())
    story.extend(section_17())
    doc.build(story)
    print(f"OK -> {OUTPUT_PDF}")
    return OUTPUT_PDF

if __name__ == "__main__":
    build()
