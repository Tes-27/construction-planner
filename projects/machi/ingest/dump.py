import sys, openpyxl
wb = openpyxl.load_workbook(sys.argv[1], data_only=True)
ws = wb[sys.argv[2]]
a, b = int(sys.argv[3]), int(sys.argv[4])
for r in range(a, b+1):
    cells = []
    for c in range(1, ws.max_column+1):
        v = ws.cell(r, c).value
        if v not in (None, ""):
            cells.append(f"{openpyxl.utils.get_column_letter(c)}={str(v)[:35]!s}")
    if cells: print(r, " ".join(cells))
