# Easy Photo Print LX

A simple right-click photo printing utility for Linux (Nautilus/GNOME).

Select one or more photos in your file manager, right-click → **Scripts → Print Photos…**, choose your layout and page size, and print.

![Easy Photo Print LX](https://img.shields.io/badge/platform-Linux-blue) ![Python](https://img.shields.io/badge/python-3.8%2B-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Features

- **Right-click integration** — works directly from Nautilus (Files)
- **Layout selector** — 1, 2, 4, 8, or 16 photos per page
- **Page sizes** — A4, Letter, A3, 4"×6", 5"×7", 6"×8"
- **Auto orientation** — detects dominant photo orientation and picks the best page+grid combination to minimise white space
- **EXIF-aware** — honours phone camera rotation metadata
- **Fit or Fill** — letterbox (show full photo) or crop to fill the cell
- **Multi-page PDF** — all selected photos across as many pages as needed
- **Printer selector** — lists all CUPS printers; send directly or save as PDF
- **Copies** — set number of copies before printing

---

## Requirements

- Python 3.8+
- [Pillow](https://pillow.readthedocs.io/) (`pip install Pillow`)
- CUPS (`sudo apt install cups`)
- Nautilus file manager (for right-click integration)

---

## Installation

```bash
git clone git@github.com:osmanksonmez/easyPhotoPrintLX.git
cd easyPhotoPrintLX
bash install.sh
```

The installer will:
1. Check/install Pillow
2. Register **Print Photos…** as a Nautilus right-click script
3. Install a `.desktop` launcher so the app appears in application menus

---

## Usage

**Right-click (recommended)**
1. Open Nautilus, select one or more photos
2. Right-click → Scripts → **Print Photos…**
3. Choose layout, page size, and printer → click **Print**

**Command line**
```bash
python3 photo_print_app.py photo1.jpg photo2.jpg ...
```

**No arguments** — opens a file picker dialog.

---

## How auto-orientation works

The app samples up to 10 photos, applies EXIF rotation to get the true orientation, then calculates which combination of page orientation (Portrait/Landscape) and grid direction minimises the log-ratio error between cell shape and photo aspect ratio. For typical portrait phone photos on A4, this picks a landscape page with a 4×2 grid, giving cells at ~0.71 ratio — very close to the standard 3:4 phone photo.

---

## License

MIT
