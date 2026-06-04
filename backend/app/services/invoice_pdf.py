"""Generate simple invoice PDF documents for email attachment."""
import io
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from app.models.invoice import Invoice
from app.models.customer import Customer
from app.models.company import Company


def generate_invoice_pdf(invoice: Invoice, customer: Customer | None, company: Company | None) -> bytes:
    """Return raw PDF bytes for a single invoice."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    company_name = company.name if company else "Company"
    elements.append(Paragraph(f"<b>{company_name}</b>", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Invoice # {invoice.invoice_number}", styles["Heading2"]))
    elements.append(Spacer(1, 6))

    # Customer info
    if customer:
        lines = [f"<b>Bill To:</b> {customer.name}"]
        if customer.contact_name:
            lines.append(f"Attn: {customer.contact_name}")
        if customer.address:
            lines.append(customer.address)
        elements.append(Paragraph("<br/>".join(lines), styles["Normal"]))
        elements.append(Spacer(1, 12))

    # Invoice details table
    def _fmt_money(v):
        if v is None:
            return "$0.00"
        return f"${Decimal(v):,.2f}"

    detail_data = [
        ["Invoice Date", str(invoice.invoice_date.strftime("%Y-%m-%d") if invoice.invoice_date else "—")],
        ["Due Date", str(invoice.due_date.strftime("%Y-%m-%d") if invoice.due_date else "—")],
        ["Amount", _fmt_money(invoice.amount)],
        ["Amount Paid", _fmt_money(invoice.amount_paid)],
        ["Balance Due", _fmt_money(invoice.balance)],
        ["Status", invoice.status.value.replace("_", " ").title()],
    ]
    if invoice.po_number:
        detail_data.insert(0, ["PO Number", invoice.po_number])

    t = Table(detail_data, colWidths=[2 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)

    if invoice.notes:
        elements.append(Spacer(1, 18))
        elements.append(Paragraph("<b>Notes:</b>", styles["Normal"]))
        elements.append(Paragraph(invoice.notes, styles["Normal"]))

    doc.build(elements)
    return buf.getvalue()
