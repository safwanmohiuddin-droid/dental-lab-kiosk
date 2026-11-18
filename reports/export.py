"""Report downloads (ADR 0038): a formatted Excel workbook for people, a plain CSV for software."""

import csv
import io

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference, Series
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.line import LineProperties
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import engine

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
INK, SOFT, BAND = "1B2340", "565D75", "F6F3EE"  # the app's ink, soft text and paper (ui.css)
COLOURS = [INK, "C2452D", "0F6E56", "854F0B", "7F77DD", "D4537E"]  # chart lines, as on screen
THIN = Side(style="thin", color="9CA3AF")
HEADER_ROW = 6  # title block above it, table below
PAGE_COLUMNS = 14


def title(spec):
    """The report sentence as a heading: "Units used by material per week"."""
    words = [engine.MEASURES[spec.measure][0]]
    if spec.by:
        words.append("by " + engine.DIMENSIONS[spec.by][0].lower())
    if spec.every:
        words.append("per " + engine.GRAINS[spec.every][0].lower())
    return " ".join(words)


def filters(spec):
    picked = [
        (label, value)
        for label, value in (
            ("Department", spec.department),
            ("Category", spec.category),
            ("Material", spec.material),
            ("Person", spec.person),
        )
        if value
    ]
    return "; ".join(f"{label}: {value}" for label, value in picked) or "None"


def _table(report):
    """Header and body exactly as on screen, with a Total column on time reports."""
    if not report.spec.by and not report.spec.every:
        return ["", report.measure_label], [[report.measure_label, report.total]]
    header = [c or "" for c in report.columns]
    body = [[r["label"], *r["values"]] for r in report.rows]
    return header, body


def _number_format(report, body):
    if report.spec.measure == "cost":
        return '#,##0.00;-#,##0.00;"-"'
    whole = all(v is None or v == int(v) for row in body for v in row[1:])
    return '#,##0;-#,##0;"-"' if whole else '#,##0.000;-#,##0.000;"-"'


def csv_response(report, name):
    """Plain values, no styling: for importing into accounting or other software."""
    header, body = _table(report)
    if report.spec.every:  # time report: add the row total the screen shows
        body = [[r["label"], *r["values"], r["total"]] for r in report.rows]
    out = io.StringIO()
    csv.writer(out).writerows([header, *body])
    response = HttpResponse(out.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{name}.csv"'
    return response


def xlsx_response(report, name, user):
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.sheet_view.showGridLines = False  # the table draws its own lines
    heading = title(report.spec)
    wb.properties.title = heading
    wb.properties.creator = "Material kiosk"

    # Title block: what this is, which dates, which filters, who made it and when.
    now = timezone.localtime().strftime("%d %b %Y %H:%M")
    ws["A1"] = heading
    ws["A1"].font = Font(size=16, bold=True, color=INK)
    ws["A2"] = f"{report.spec.start:%d %b %Y} to {report.spec.end:%d %b %Y}"
    ws["A3"] = f"Filters: {filters(report.spec)}"
    ws["A4"] = f"Downloaded {now} by {user.get_username()}"
    for cell in ("A2", "A3", "A4"):
        ws[cell].font = Font(color=SOFT)

    header, body = _table(report)
    time_report = bool(report.spec.every)  # these have a Total column
    width = len(header)
    numbers = _number_format(report, body)
    first, last = HEADER_ROW + 1, HEADER_ROW + len(body)

    for col, text in enumerate(header, 1):
        cell = ws.cell(HEADER_ROW, col, text)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=INK)
        cell.alignment = Alignment(horizontal="left" if col == 1 else "right", vertical="center")
    ws.row_dimensions[HEADER_ROW].height = 22

    for i, row in enumerate(body):
        r = first + i
        for col, value in enumerate(row, 1):
            # A quiet period is a real zero (the format shows it as "-"), so totals add up.
            cell = ws.cell(r, col, value if col == 1 or value is not None else 0)
            if col > 1:
                cell.number_format = numbers
        if time_report:  # row total as a formula, so edits in Excel still add up
            span = f"B{r}:{get_column_letter(width - 1)}{r}"
            ws.cell(r, width, f"=SUM({span})").number_format = numbers
            ws.cell(r, width).font = Font(bold=True)
        for col in range(1, width + 1):
            cell = ws.cell(r, col)
            cell.border = Border(bottom=Side(style="hair", color="D1D5DB"))
            if i % 2:
                cell.fill = PatternFill("solid", fgColor=BAND)

    # Grand total: bold, single line above, double line below (the accounting convention).
    # Without a breakdown there is only one row, so it is the total already.
    total_row = last + 1 if report.spec.by else last
    if report.spec.by:
        _total_row(ws, total_row, first, last, width, numbers)

    for n, note in enumerate(report.notes):
        ws.cell(total_row + 2 + n, 1, note).font = Font(italic=True, color=SOFT)

    # Readable widths, headers that stay put, and filter buttons on the header row.
    longest = max([len(str(row[0])) for row in body] + [len(header[0]), 10])
    if width > PAGE_COLUMNS:  # column A repeats on every page: wide enough for the title block
        longest = max(longest, len(heading) * 1.5, len(ws["A4"].value))
    ws.column_dimensions["A"].width = min(longest + 2, 50)
    for col in range(2, width + 1):
        ws.column_dimensions[get_column_letter(col)].width = max(12, len(header[col - 1]) + 4)
    ws.freeze_panes = ws.cell(first, 2)
    last_col = get_column_letter(width)
    ws.auto_filter.ref = f"A{HEADER_ROW}:{last_col}{last}"

    # Printing: about 14 columns a page (long time reports run across pages instead of shrinking
    # to unreadable), header row and name column on every page, page numbers in the footer.
    ws.print_area = f"A1:{last_col}{total_row + 1 + len(report.notes)}"
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"
    ws.print_title_cols = "A:A"
    ws.page_setup.orientation = "landscape" if width > 6 else "portrait"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = -(-width // PAGE_COLUMNS), 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.oddFooter.left.text = f"{heading}, downloaded {now}"
    ws.oddFooter.right.text = "Page &P of &N"

    if report.chart and body:
        _chart_sheet(wb, ws, report, heading, width, first, last, numbers)

    wb.calculation.fullCalcOnLoad = True  # formulas have no saved result until calculated
    data = io.BytesIO()
    wb.save(data)
    response = HttpResponse(data.getvalue(), content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{name}.xlsx"'
    return response


def _total_row(ws, row, first, last, width, numbers):
    ws.cell(row, 1, "Total")
    for col in range(2, width + 1):
        letter = get_column_letter(col)
        ws.cell(row, col, f"=SUM({letter}{first}:{letter}{last})").number_format = numbers
    for col in range(1, width + 1):
        cell = ws.cell(row, col)
        cell.font = Font(bold=True)
        cell.border = Border(top=THIN, bottom=Side(style="double", color=INK))


def _chart_sheet(wb, ws, report, heading, width, first, last, numbers):
    """A native Excel chart that reads the Report sheet, so it updates if the numbers change."""
    sheet = wb.create_sheet("Chart")
    if report.spec.every:  # one line per row, top series only, like the screen
        chart = LineChart()
        chart.height = 15
        rows = min(last, first + engine.SERIES - 1)
        periods = width - 1  # leave out the Total column
        for i, r in enumerate(range(first, rows + 1)):
            line = Series(
                Reference(ws, min_col=2, max_col=periods, min_row=r), title=str(ws.cell(r, 1).value)
            )
            line.smooth = False  # a smoothed line dips below zero between real points
            line.graphicalProperties.line.solidFill = COLOURS[i % len(COLOURS)]
            line.graphicalProperties.line.width = 28575  # 2.25 pt
            chart.series.append(line)
        chart.set_categories(Reference(ws, min_col=2, max_col=periods, min_row=HEADER_ROW))
        chart.legend.position = "b"
        value_axis, limit = chart.y_axis, engine.SERIES
    else:
        chart = BarChart()
        chart.type = "bar"  # horizontal bars: long names stay readable
        rows = min(last, first + engine.BARS - 1)
        chart.add_data(
            Reference(ws, min_col=2, min_row=HEADER_ROW, max_row=rows), titles_from_data=True
        )
        chart.set_categories(Reference(ws, min_col=1, min_row=first, max_row=rows))
        chart.series[0].graphicalProperties.solidFill = INK
        chart.series[0].graphicalProperties.line.solidFill = INK
        chart.x_axis.scaling.orientation = "maxMin"  # biggest at the top, as in the table
        chart.y_axis.crosses = "max"  # ...which would otherwise put the value axis on top
        chart.gapWidth = 60
        chart.legend = None
        chart.height = min(15, 3 + 0.8 * (rows - first + 1))  # bars stay bar-shaped
        value_axis, limit = chart.y_axis, engine.BARS
    # openpyxl hides both axes unless told otherwise.
    chart.x_axis.delete = chart.y_axis.delete = False
    value_axis.number_format = numbers.split(";")[0]
    value_axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill="E2DCD2"))
    chart.title = heading if rows == last else f"{heading} (top {limit})"
    chart.title.overlay = False  # title and legend beside the plot, not on top of it
    if chart.legend:
        chart.legend.overlay = False
    chart.roundedCorners = False
    chart.width = 25  # fills a landscape page
    sheet.add_chart(chart, "A1")
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = sheet.page_setup.fitToHeight = 1
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
