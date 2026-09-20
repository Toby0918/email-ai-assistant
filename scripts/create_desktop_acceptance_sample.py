"""Generate the synthetic XLSX fixture used for manual application acceptance."""
from pathlib import Path
from openpyxl import Workbook


def main():
    project = Path(__file__).resolve().parents[1]
    destination = project / "Build" / "desktop-mail-acceptance"
    destination.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Synthetic order"
    sheet.append(["Product", "Synthetic faucet"])
    sheet.append(["Quantity", "1200 pcs"])
    sheet.append(["Delivery", "Not confirmed; verify before replying"])
    sheet.append(["Price", "Not agreed"])
    sheet.column_dimensions["A"].width = 20
    sheet.column_dimensions["B"].width = 55
    path = destination / "synthetic-order.xlsx"
    workbook.save(path)
    workbook.close()
    print(path)


if __name__ == "__main__":
    main()
