"""Write manuscript_candidate.pdf: manuscript.pdf with document metadata and
pdfTeX inclusion keys (/PTEX.FileName, /PTEX.InfoDict, /PTEX.PageNumber)
removed, then check that the text contains no identifying strings.

    .venv/bin/python paper/icaps27_multisolver_final/make_candidate.py
"""
import getpass
import re
import socket
import subprocess
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

HERE = Path(__file__).resolve().parent
src, dst = HERE / "manuscript.pdf", HERE / "manuscript_candidate.pdf"
w = PdfWriter(clone_from=PdfReader(src))
removed = 0
for page in w.pages:
    xo = page.get("/Resources", {}).get("/XObject", {})
    for name in list(xo.keys()):
        obj = xo[name].get_object()
        for k in ("/PTEX.FileName", "/PTEX.InfoDict", "/PTEX.PageNumber"):
            if NameObject(k) in obj:
                del obj[NameObject(k)]
                removed += 1
w._info = None  # drop the document information dictionary
w.add_metadata({"/Producer": "pdfTeX"})
with open(dst, "wb") as f:
    w.write(f)
raw = dst.read_bytes()
txt = subprocess.run(["pdftotext", str(dst), "-"], capture_output=True, text=True).stdout
ident = [getpass.getuser(), socket.gethostname(), str(Path.home())]
ident += [subprocess.run(["git", "config", k], capture_output=True, text=True).stdout.strip() for k in ("user.email", "user.name")]
hay = (txt + raw.decode("latin-1")).lower()
bad = [x for x in ident if x and x.lower() in hay]  # identity read at run time; none hard-coded here
print(f"{dst.name}: {len(PdfReader(dst).pages)} pages, {removed} PTEX keys removed, identifying strings: {len(bad)}")
raise SystemExit(1 if bad else 0)
