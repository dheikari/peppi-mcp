"""Entirely invented transcript content using the inspected column structure.

No real transcript text, names, identifiers, amounts, dates or captured PDF bytes.
The university's public labels describe the format, not an authentic document.
"""

import io

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def row(title, amount=None, grade=None, date=None, indent=11):
    text = " " * indent + title
    for column, value in ((70, f"{amount} op" if amount is not None else ""), (84, grade), (97, date), (113, "INVENTED ASSESSOR" if grade else "")):
        if value:
            text = text.ljust(column) + value
    return text


def pages():
    def header(number):
        return f"Opintosuoritusote\n1.3.2026\nLapin yliopisto\nsivu {number}/3\n"
    table = "Opintosuoritukset".ljust(70) + "Laajuus".ljust(14) + "Arviointi".ljust(13) + "Pvm".ljust(16) + "Arvioija\n"
    return [
        header(1) + "Fictional test document, not an official transcript\n"
        "Name  INVENTED PERSON\nStudent number  INVENTED ID\n"
        "Opiskeluoikeusaika  1.1.2024 - 1.1.2030\n"
        "Tutkinto  Invented degree\nOhjelma  Invented programme\nSuoritettu  3,5 op\n",
        header(2) + table + "Invented degree\n" + "\n".join([
            row("Invented overall group", "3,5", indent=6),
            row("Invented subgroup", "1,5", indent=11),
            row("TEST001V1 Invented title with ä and ö", "0,5", "HYV", "1.2.2026", indent=16),
            " " * 16 + "continued fictional title",
            row("TEST002V1 Invented second course", "1", "4", "2.2.2026", indent=16),
        ]),
        header(3) + table + row("TEST003V1 Invented third course", "2", "3", "3.2.2026") +
        "\nArvosana-asteikon selitykset\n5 = Erinomainen\nHYV = Hyväksytty\nHYL, 0 = Hylätty\n",
    ]


def pdf_bytes(text_pages=None, *, encrypted=False, rotate=False):
    """Minimal selectable-text PDF, generated in memory; never a captured source."""
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Courier"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding")}))
    for text in text_pages if text_pages is not None else pages():
        page = writer.add_blank_page(width=595.28, height=841.89)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        commands = [b"BT /F1 6 Tf 30 790 Td 12 TL"]
        for line in text.splitlines():
            literal = line.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            commands.append(b"(" + literal + b") Tj T*")
        commands.append(b"ET")
        stream = DecodedStreamObject()
        stream.set_data(b"\n".join(commands))
        page[NameObject("/Contents")] = writer._add_object(stream)
        if rotate:
            page.rotate(90)
    if encrypted:
        writer.encrypt("fictional-test-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
