# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Replace code-generated figures in the PyAges manuscript DOCX files."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

EMU_PER_MM = 36_000
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


@dataclass(frozen=True)
class FigureReplacement:
    media_name: str
    source_name: str
    width_mm: float
    alt_text: str


REPLACEMENTS = (
    FigureReplacement(
        "image1.png",
        "figure1_pyages_architecture.png",
        110.0,
        "Conceptual organization of PyAges, showing the tracer, LPM, "
        "convolution, and calibration components and their exchanges.",
    ),
    FigureReplacement(
        "image7.png",
        "figure2_shifted_exponential_final.png",
        110.0,
        "Posterior samples for the shifted-exponential benchmark in the "
        "exponential-timescale and shift plane, over the normalized RMS data "
        "misfit surface, with the generating target at 10 and 30 years.",
    ),
    FigureReplacement(
        "image6.png",
        "figure3_holten_final.png",
        165.0,
        "Comparison of PyAges posterior age fractions and 10–90 percent credible "
        "intervals with the four age-class fractions reported by Visser et al. "
        "(2013) for seven Holten wells.",
    ),
    FigureReplacement(
        "image8.png",
        "figure4_ploemeur_final.png",
        165.0,
        "Six-panel comparison of full-record and 2014–2015-only tracer "
        "calibrations for wells F09 and F11 at Ploemeur.",
    ),
    FigureReplacement(
        "image9.png",
        "figureC1_holten_prior_sensitivity.png",
        165.0,
        "Sensitivity of posterior Holten age fractions to a latent-logit uniform "
        "prior and a Dirichlet(1,1,1,1) fraction prior.",
    ),
)


def _relationship_targets(data: bytes) -> dict[str, str]:
    root = ET.fromstring(data)
    return {
        element.attrib["Id"]: element.attrib["Target"]
        for element in root.findall(f"{{{REL_NS}}}Relationship")
    }


def _drawing_blocks(document: str) -> list[tuple[int, int, str]]:
    return [
        (match.start(), match.end(), match.group(0))
        for match in re.finditer(r"<w:drawing\b.*?</w:drawing>", document, re.DOTALL)
    ]


def _update_drawing(block: str, width: int, height: int, alt_text: str) -> str:
    extent_pattern = re.compile(
        r'(<(?:wp:extent|a:ext)\b[^>]*\bcx=")\d+("[^>]*\bcy=")\d+(")'
    )
    block, extent_count = extent_pattern.subn(
        lambda match: (
            f"{match.group(1)}{width}{match.group(2)}{height}{match.group(3)}"
        ),
        block,
    )
    if extent_count < 1:
        raise RuntimeError("Drawing has no editable extent")
    escaped = html.escape(alt_text, quote=True)
    docpr_pattern = re.compile(r'(<wp:docPr\b[^>]*\bdescr=")[^"]*(")')
    block, alt_count = docpr_pattern.subn(
        lambda match: f"{match.group(1)}{escaped}{match.group(2)}", block, count=1
    )
    if alt_count != 1:
        raise RuntimeError("Drawing has no unique wp:docPr description")
    return block


def update_main_document(  # noqa: C901 - transactional DOCX validation is deliberate
    source: Path, output: Path, figure_dir: Path
) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing DOCX: {output}")
    sources = {item.media_name: figure_dir / item.source_name for item in REPLACEMENTS}
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing replacement figure(s): " + ", ".join(missing))

    with zipfile.ZipFile(source) as archive:
        relationships = _relationship_targets(
            archive.read("word/_rels/document.xml.rels")
        )
        document = archive.read("word/document.xml").decode("utf-8")
        blocks = _drawing_blocks(document)
        replacements: dict[str, bytes] = {}
        updated = 0
        for item in REPLACEMENTS:
            figure = sources[item.media_name]
            with Image.open(figure) as image:
                pixel_width, pixel_height = image.size
            width = round(item.width_mm * EMU_PER_MM)
            height = round(width * pixel_height / pixel_width)
            matching = []
            for start, end, block in blocks:
                embed = re.search(r'r:embed="([^"]+)"', block)
                if embed is None:
                    continue
                target = relationships.get(embed.group(1), "")
                if Path(target).name == item.media_name:
                    matching.append((start, end, block))
            if len(matching) != 1:
                raise RuntimeError(
                    f"Expected one drawing for {item.media_name}, found {len(matching)}"
                )
            start, end, block = matching[0]
            replacement = _update_drawing(block, width, height, item.alt_text)
            document = document[:start] + replacement + document[end:]
            delta = len(replacement) - (end - start)
            blocks = [
                (
                    (
                        s + (delta if s > start else 0),
                        e + (delta if s > start else 0),
                        b,
                    )
                    if s != start
                    else (start, start + len(replacement), replacement)
                )
                for s, e, b in blocks
            ]
            replacements[f"word/media/{item.media_name}"] = figure.read_bytes()
            updated += 1

        replacements["word/document.xml"] = document.encode("utf-8")
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=output.parent, suffix=".docx", delete=False
        ) as stream:
            temporary = Path(stream.name)
        try:
            with zipfile.ZipFile(temporary, "w") as destination:
                for info in archive.infolist():
                    destination.writestr(
                        info, replacements.get(info.filename, archive.read(info))
                    )
            temporary.replace(output)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    with zipfile.ZipFile(output) as check:
        if check.testzip() is not None:
            raise RuntimeError("Updated DOCX failed ZIP CRC validation")
        for media_name, expected in replacements.items():
            if (
                media_name.startswith("word/media/")
                and check.read(media_name) != expected
            ):
                raise RuntimeError(f"DOCX media verification failed: {media_name}")
    print(f"Updated {updated} code-generated figures: {output}")


def copy_supplement(source: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing DOCX: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Copied supplementary DOCX failed ZIP CRC validation")
    print(f"Copied supplement unchanged (no drawings found): {output}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-input", type=Path, required=True)
    parser.add_argument("--main-output", type=Path, required=True)
    parser.add_argument("--supplement-input", type=Path, required=True)
    parser.add_argument("--supplement-output", type=Path, required=True)
    parser.add_argument("--figure-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    update_main_document(
        args.main_input.resolve(),
        args.main_output.resolve(),
        args.figure_dir.resolve(),
    )
    copy_supplement(args.supplement_input.resolve(), args.supplement_output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
