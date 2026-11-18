# 0038. Report exports: a formatted Excel workbook, plain CSV, and print to PDF

- Status: Accepted (owner, 2026-11-18)
- Date: 2026-11-18

## Context
The owner wants any report the builder makes to download in a professional, Excel-style format.
The old export wrote bare values: no title, dates, filters, totals or formatting, so it needed
tidying before anyone could read, print or forward it.

## Decision
- **Excel (`reports/export.py`)** follows common report conventions:
  - a title block: the report sentence as a heading, dates, filters, who downloaded it and when;
  - a dark header row with filter buttons, frozen header and name column, light zebra bands,
    no gridlines;
  - numbers stored as numbers with a format per measure (money `#,##0.00`, whole units `#,##0`,
    zeros shown as `-`);
  - totals as `SUM` formulas (row totals on time reports, a grand total with a single line above
    and a double line below), so edits in Excel still add up;
  - print-ready: landscape when wide, one page wide, header row repeated on every page, page
    numbers in the footer;
  - a native Excel chart on a second sheet that reads the table.
- **CSV** stays plain values with no styling: it is for accounting and other software.
- **PDF** is the browser's own "Print or save as PDF" with print styles. It needs no PDF
  library, and the page and the PDF can never disagree.
- Explicit cell styles, not an Excel "Table": they look the same in Excel, LibreOffice, Google
  Sheets and Numbers.

## Alternatives considered
- A server-side PDF library (WeasyPrint, ReportLab): a heavy dependency (WeasyPrint needs system
  libraries) and a second layout to keep in step with the page.
- Typed totals instead of formulas: simpler, but they go stale when someone edits a cell.
- XlsxWriter: good formatting support, but openpyxl is already a dependency (imports).

## Consequences
A formula has no stored result until a spreadsheet app calculates it; the workbook asks for a
full calculation on open. Viewers that never calculate (some file previews) show the total
cells empty; the CSV and the page always have the numbers.

## Interview angle
"Two audiences, two formats: people get a formatted workbook with live totals, software gets a
plain CSV. PDF is the browser's print, so it can't drift from the screen."
