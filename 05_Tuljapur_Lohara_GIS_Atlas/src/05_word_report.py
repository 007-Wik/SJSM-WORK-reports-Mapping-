#!/usr/bin/env python3
"""
Master Client-Grade GIS & Environmental Word Report Generator (.docx)
Generates an exhaustive, consulting-grade Word Document for Tuljapur & Lohara Blocks:
'docs/Tuljapur_Lohara_Comprehensive_GIS_Environmental_Atlas_Report.docx'

Features:
- Executive Title Page & Metadata
- Executive Summary & Master KPI Table (Tuljapur vs Lohara vs Total AOI)
- 11 Technical Chapters covering all 15 thematic GIS layers
- Embedded High-Resolution Cartographic Maps & Inset Graphics
- Morphometric, Climatological, and Hydrogeological Data Tables
- Complete Strategic Recharge Structure Siting Matrix
- Complete 177-Village Cadastral Directory Annexure
"""

from pathlib import Path
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
import geopandas as gpd
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PROC = BASE_DIR / "data" / "processed" if (BASE_DIR / "data" / "processed" / "aoi" / "aoi_blocks.gpkg").exists() else BASE_DIR / "map_data"
MAP_DATA = DATA_PROC
MAPS_DIR = BASE_DIR / "deliverables" / "maps" if (BASE_DIR / "deliverables" / "maps" / "Tuljapur").exists() else BASE_DIR / "map_data" / "maps"
DELIV_REPORTS = BASE_DIR / "deliverables" / "reports"
DELIV_REPORTS.mkdir(parents=True, exist_ok=True)
OUT_DOCX = DELIV_REPORTS / "Tuljapur_Lohara_Comprehensive_GIS_Environmental_Atlas_Report.docx"

# Color Palette
COLOR_NAVY = RGBColor(30, 27, 75)      # #1E1B4B
COLOR_STEEL = RGBColor(30, 58, 138)    # #1E3A8A
COLOR_DARK = RGBColor(15, 23, 42)      # #0F172A
COLOR_MUTED = RGBColor(71, 85, 105)    # #475569
HEX_NAVY = "1E1B4B"
HEX_LIGHT_BLUE = "F1F5F9"
HEX_ZEBRA = "F8FAFC"
HEX_BORDER = "CBD5E1"


def set_cell_background(cell, hex_color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)


def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def add_custom_heading(doc, text, level):
    h = doc.add_heading(text, level=level)
    run = h.runs[0]
    run.font.name = "Times New Roman"
    if level == 1:
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = COLOR_NAVY
        h.paragraph_format.space_before = Pt(18)
        h.paragraph_format.space_after = Pt(8)
    elif level == 2:
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = COLOR_STEEL
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(6)
    else:
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = COLOR_DARK
        h.paragraph_format.space_before = Pt(8)
        h.paragraph_format.space_after = Pt(4)
    return h


def add_callout_box(doc, text, title="KEY POLICY & WATERSHED FINDING"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "EFF6FF")
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)

    # Set left border thick navy, other borders none
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="none"/>
            <w:left w:val="single" w:sz="36" w:space="0" w:color="{HEX_NAVY}"/>
            <w:bottom w:val="none"/>
            <w:right w:val="none"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    r_title = p.add_run(f"★ {title}\n")
    r_title.font.name = "Times New Roman"
    r_title.font.size = Pt(10.5)
    r_title.font.bold = True
    r_title.font.color.rgb = COLOR_NAVY

    r_body = p.add_run(text)
    r_body.font.name = "Times New Roman"
    r_body.font.size = Pt(9.5)
    r_body.font.color.rgb = COLOR_DARK
    doc.add_paragraph().paragraph_format.space_after = Pt(6)


def format_table(tbl, col_widths=None):
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    # Format Header Row
    for i, cell in enumerate(tbl.rows[0].cells):
        set_cell_background(cell, HEX_NAVY)
        set_cell_margins(cell, top=120, bottom=120, left=140, right=140)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.name = "Times New Roman"
            r.font.size = Pt(9.5)
            r.font.bold = True
            r.font.color.rgb = RGBColor(255, 255, 255)

    # Format Data Rows
    for r_idx, row in enumerate(tbl.rows[1:], start=1):
        is_zebra = (r_idx % 2 == 0)
        bg = HEX_ZEBRA if is_zebra else "FFFFFF"
        for c_idx, cell in enumerate(row.cells):
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
            p = cell.paragraphs[0]
            if c_idx > 0 and any(char.isdigit() for char in p.text):
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.font.name = "Times New Roman"
                r.font.size = Pt(9.0)
                r.font.color.rgb = COLOR_DARK

    if col_widths:
        for row in tbl.rows:
            for idx, width in enumerate(col_widths):
                if idx < len(row.cells):
                    row.cells[idx].width = width


def add_figure_image(doc, img_path, caption, width=Inches(6.2)):
    p = Path(img_path)
    if p.exists():
        doc.add_paragraph().paragraph_format.space_before = Pt(8)
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_after = Pt(4)
        run = p_img.add_run()
        run.add_picture(str(p), width=width)

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(12)
        r_cap = p_cap.add_run(caption)
        r_cap.font.name = "Times New Roman"
        r_cap.font.size = Pt(9.0)
        r_cap.font.italic = True
        r_cap.font.color.rgb = COLOR_MUTED
    else:
        print(f"Warning: Image file not found: {img_path}")


def build_word_report():
    print("=" * 70)
    print("GENERATING COMPREHENSIVE CLIENT-GRADE GIS & ENVIRONMENTAL WORD REPORT (.DOCX)")
    print("=" * 70)

    doc = Document()

    # Set page margins to standard 1 inch
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)

    # Set normal style font
    style_normal = doc.styles['Normal']
    style_normal.font.name = "Times New Roman"
    style_normal.font.size = Pt(10.5)
    style_normal.font.color.rgb = COLOR_DARK
    style_normal.paragraph_format.line_spacing = 1.15
    style_normal.paragraph_format.space_after = Pt(6)

    # =========================================================================
    # TITLE PAGE
    # =========================================================================
    p_title_pre = doc.add_paragraph()
    p_title_pre.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title_pre.paragraph_format.space_before = Pt(72)
    r_sub = p_title_pre.add_run("TECHNICAL CONSULTANCY & GIS ATLAS DELIVERABLE\n")
    r_sub.font.size = Pt(11)
    r_sub.font.bold = True
    r_sub.font.color.rgb = COLOR_STEEL

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_after = Pt(12)
    r_main = p_title.add_run("COMPREHENSIVE GEOSPATIAL ATLAS &\nWATERSHED CHARACTERIZATION REPORT")
    r_main.font.size = Pt(22)
    r_main.font.bold = True
    r_main.font.color.rgb = COLOR_NAVY

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(36)
    r_sub2 = p_sub.add_run("Physiographic, Hydrogeological, Climatological & Land Resource Assessment for\nTuljapur and Lohara Blocks, Dharashiv District, Maharashtra")
    r_sub2.font.size = Pt(12.5)
    r_sub2.font.italic = True
    r_sub2.font.color.rgb = COLOR_MUTED

    # Metadata Card Table
    meta_tbl = doc.add_table(rows=6, cols=2)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_info = [
        ("Study Area Extent", "Tuljapur Block (1,500.72 km²) & Lohara Block (543.20 km²) | Total AOI: 2,043.93 km²"),
        ("Administrative Units", "177 Cadastral Villages (Tuljapur: 130 | Lohara: 47), Dharashiv District, MH"),
        ("Coordinate Reference System", "WGS 84 / UTM Zone 43N (EPSG: 32643) | Baseline Survey of India Toposheets"),
        ("Primary Data Repositories", "NRSC / ISRO Bhuvan, Survey of India, Copernicus GLO-30 DEM, CHIRPS, CGWB"),
        ("Specialized Focus", "Rajiv Gandhi National Drinking Water Mission (RGNDWM) 250K Ground Water Prospects"),
        ("Report Version & Date", "Version 2.0 (Final Deliverable) | October 2026")
    ]
    for idx, (lbl, val) in enumerate(meta_info):
        r_row = meta_tbl.rows[idx]
        c0, c1 = r_row.cells[0], r_row.cells[1]
        c0.text = lbl
        c1.text = val
        c0.paragraphs[0].runs[0].font.bold = True
        c0.paragraphs[0].runs[0].font.size = Pt(9.5)
        c0.paragraphs[0].runs[0].font.color.rgb = COLOR_NAVY
        c1.paragraphs[0].runs[0].font.size = Pt(9.5)
        set_cell_background(c0, HEX_LIGHT_BLUE)
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, 80, 80, 100, 100)
        set_cell_margins(c1, 80, 80, 100, 100)

    doc.add_page_break()

    # =========================================================================
    # EXECUTIVE SUMMARY
    # =========================================================================
    add_custom_heading(doc, "EXECUTIVE SUMMARY", level=1)

    p_exec1 = doc.add_paragraph()
    p_exec1.add_run(
        "This comprehensive GIS and Environmental Atlas presents an exhaustive physiographic, hydrogeological, "
        "climatological, and land resource assessment for Tuljapur and Lohara blocks in Dharashiv (formerly Osmanabad) "
        "district, Maharashtra. Encompassing a total geographical area of 2,043.93 km² across 177 cadastral villages, "
        "the study area represents a critical rural agricultural tract within the drought-prone Deccan Trap basalt plateau. "
        "The primary purpose of this atlas is to synthesize multi-satellite remote sensing observations, national geospatial "
        "databases, and ground truth hydrogeological records into an actionable framework for watershed planning, "
        "sustainable irrigation development, and site-specific artificial recharge under the Jal Jeevan Mission (JJM) "
        "and Rajiv Gandhi National Drinking Water Mission (RGNDWM)."
    )

    add_callout_box(
        doc,
        "The study area occupies an extraordinary geographic nexus where four Survey of India 1° × 1° quadrangles (56C, 56B, 47O, and 47N) "
        "converge at exactly 76°00'00\"E and 18°00'00\"N. Approximately 70.1% of the AOI (1,433.9 km²) falls within Sheet 56C (Osmanabad/Sholapur), "
        "16.6% (340.1 km²) within Sheet 56B (Bidar/Latur), 12.9% (262.8 km²) in Sheet 47O (Solapur/Sina Basin), and 0.4% (7.1 km²) in Sheet 47N. "
        "Ten Survey of India 1:50,000 toposheet tiles provide the foundational cadastral basis for all ground water prospects and recharge structures.",
        title="GEOGRAPHICAL NEXUS & RGNDWM FRAMEWORK"
    )

    # Master KPI Table
    add_custom_heading(doc, "Master Study Area KPI Summary", level=2)
    kpi_tbl = doc.add_table(rows=1, cols=5)
    headers = ["Thematic Parameter", "Tuljapur Block", "Lohara Block", "Combined Study Area", "Source Authority"]
    for i, h in enumerate(headers):
        kpi_tbl.rows[0].cells[i].text = h

    kpi_rows = [
        ["Total Geographical Area", "1,500.72 km² (73.4%)", "543.20 km² (26.6%)", "2,043.93 km² (100.0%)", "MahaGIS / SOI Cadastre"],
        ["Cadastral Village Units", "130 Villages", "47 Villages", "177 Villages Total", "Census of India 2011"],
        ["Total Population", "279,720 Persons", "116,211 Persons", "395,931 Persons", "Census 2011 Data"],
        ["Elevation Range (m a.s.l.)", "435.5 – 711.0 m", "514.8 – 669.2 m", "435.5 – 711.0 m", "Copernicus GLO-30 DEM"],
        ["Mean Surface Elevation", "554.6 m a.s.l.", "617.2 m a.s.l.", "560.6 m a.s.l.", "Zonal DEM Extraction"],
        ["Mean Topographic Slope", "1.62° (Very Gentle)", "1.42° (Nearly Level)", "1.57° (Regional Mean)", "DEM Slope horn Algorithm"],
        ["Primary River Basins", "Bori River (Sina / Bhima)", "Terna River (Manjra)", "Bhima & Godavari Divides", "CWC Basin Directory"],
        ["Total Stream Length", "1,608.74 km", "582.98 km", "2,191.73 km", "Strahler Orders 1–5"],
        ["Drainage Density (Dd)", "1.07 km / km²", "1.07 km / km²", "1.07 km / km²", "Hydrological Metric"],
        ["34-Yr Mean Rainfall", "762.5 mm / year", "786.1 mm / year", "768.4 mm / year", "CHIRPS (1991–2024)"],
        ["Monsoon Share (JJAS)", "81.4% (620.7 mm)", "82.8% (650.9 mm)", "81.8% (628.5 mm)", "IMD Monsoon Window"],
        ["Predominant Soil Depth", "Very Shallow (<25 cm | 70.0%)", "Very Shallow (57.7%) & Shallow (33.3%)", "Very Shallow (66.8% AOI)", "NBSS & LUP Soil Survey"],
        ["Predominant Soil Texture", "Clay (Vertisols | 93.5%)", "Clay (Vertisols | 92.4%)", "Clay / Black Soil (93.2%)", "OpenLandMap USDA TT"],
        ["Cultivated Agricultural Land", "72.4% (1,086.5 km²)", "76.8% (417.2 km²)", "73.5% (1,503.7 km²)", "NRSC 1:250k LULC"],
        ["Current Fallow Land", "428.65 km² (28.6%)", "146.61 km² (27.0%)", "575.26 km² (28.2%)", "Multi-temporal Crop Dynamics"],
        ["Forest & Plantation Cover", "9.50 km² (0.6%)", "1.95 km² (0.4%)", "11.45 km² (0.6%)", "FSI Forest Cover Matrix"],
        ["Surface Waterbodies", "62.93 km² (4.2%)", "22.74 km² (4.2%)", "85.67 km² (4.2%)", "NRSC Waterbodies Layer"],
        ["Road Transport Network", "1,328.45 km", "433.13 km", "1,761.58 km", "NH-52 & State Roads (OSM)"],
        ["Major Lithology", "Deccan Basalt (Pahoehoe)", "Deccan Basalt & Alluvium", "Upper Cretaceous Basalts", "Geological Survey of India"],
        ["RGNDWM 1° × 1° Quads", "56C, 47O, 56B, 47N", "56C, 56B", "Quad Nexus (76°E, 18°N)", "NRSC Ground Water Mission"],
        ["SOI 1:50k Toposheet Tiles", "8 Sheets (56C/1, 56C/2, etc.)", "5 Sheets (56C/2, 56B/14, etc.)", "10 Sheets Total", "Survey of India Topo Index"]
    ]

    for row_data in kpi_rows:
        row = kpi_tbl.add_row()
        for i, val in enumerate(row_data):
            row.cells[i].text = val

    format_table(kpi_tbl, [Inches(1.8), Inches(1.2), Inches(1.2), Inches(1.2), Inches(1.1)])

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 1: GEOGRAPHIC SETTING & ADMINISTRATIVE FRAMEWORK
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 1: GEOGRAPHIC SETTING & ADMINISTRATIVE FRAMEWORK", level=1)

    p_ch1 = doc.add_paragraph()
    p_ch1.add_run(
        "Tuljapur and Lohara talukas are located in the southern and eastern sectors of Dharashiv district in the Marathwada "
        "division of Maharashtra. The study area extends from Longitude 75°50'13\"E to 76°34'33\"E and Latitude 17°39'24\"N "
        "to 18°05'57\"N. Tuljapur is the larger taluka, covering 1,500.72 km² (73.42% of the AOI) with its administrative "
        "headquarters at Tuljapur, an ancient temple town perched on the Balaghat plateau scarp. Lohara taluka covers "
        "543.20 km² (26.58% of the AOI) with its headquarters at Lohara (BK), situated on an extensive plateau tableland.\n\n"
        "Together, the two talukas encompass 177 revenue villages (130 in Tuljapur and 47 in Lohara). The district is bordered "
        "by Solapur district to the south and west, Latur district to the east and north-east, and Beed district to the north. "
        "Major connectivity is provided by National Highway 52 (Solapur–Dhule Highway), traversing central Tuljapur, alongside "
        "key State Highways linking Tuljapur to Naldurg, Osmanabad, Omerga, and Aland."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "01_Tuljapur_Study_Area_Map.png",
        "Figure 1.1: Cartographic Study Area Location and Administrative Boundary Map of Tuljapur Block (1,500.72 km²)."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Lohara" / "01_Lohara_Study_Area_Map.png",
        "Figure 1.2: Cartographic Study Area Location and Administrative Boundary Map of Lohara Block (543.20 km²)."
    )

    # =========================================================================
    # CHAPTER 2: PHYSIOGRAPHY & DIGITAL ELEVATION MODELING (DEM)
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 2: PHYSIOGRAPHY & DIGITAL ELEVATION MODELING", level=1)

    p_ch2 = doc.add_paragraph()
    p_ch2.add_run(
        "Physiographically, the study area forms an integral part of the Balaghat Range—a major east-west trending spur of the "
        "Western Ghats that acts as a structural water divide between the Godavari basin to the north and the Bhima (Krishna) "
        "basin to the south. Based on the Copernicus GLO-30 Digital Elevation Model (30 m spatial resolution), elevations across "
        "the AOI span from a minimum of 435.5 m a.s.l. in the incised Bori river valley near Naldurg to a maximum of 711.0 m a.s.l. "
        "on the northern structural ridges near Apsinga and Kamtha in northern Tuljapur.\n\n"
        "Lohara block sits at a substantially higher average elevation (mean 617.2 m a.s.l.) compared to Tuljapur (mean 554.6 m a.s.l.), "
        "as over 73.7% of Lohara occupies the flat tableland between 600 m and 650 m. Tuljapur displays greater physiographic diversity, "
        "with broad undulating pediplains between 500 m and 550 m covering 45.6% of the taluka."
    )

    # Elevation Distribution Table
    add_custom_heading(doc, "Hypsometric Elevation Distribution by Block", level=2)
    dem_tbl = doc.add_table(rows=1, cols=6)
    dem_hdrs = ["Elevation Range", "Hypsometric Classification", "Tuljapur (km²)", "Tuljapur (%)", "Lohara (km²)", "Lohara (%)"]
    for i, h in enumerate(dem_hdrs):
        dem_tbl.rows[0].cells[i].text = h

    dem_rows = [
        ["400 – 450 m", "Lowest Valley Depressions", "0.00", "0.0%", "0.00", "0.0%"],
        ["450 – 500 m", "Lower Valley Plains & Depressions", "146.30", "9.7%", "0.00", "0.0%"],
        ["500 – 550 m", "Middle Undulating Pediplain", "684.70", "45.6%", "3.60", "0.7%"],
        ["550 – 600 m", "Upper Pediment & Plateau Flanks", "344.80", "23.0%", "107.20", "19.7%"],
        ["600 – 650 m", "Balaghat Main Plateau Tableland", "272.70", "18.2%", "400.20", "73.7%"],
        ["> 650 m", "High Residual Ridges & Escarpments", "52.22", "3.5%", "32.20", "5.9%"],
        ["TOTAL", "Total Block Geographical Area", "1,500.72", "100.0%", "543.20", "100.0%"]
    ]
    for row_data in dem_rows:
        row = dem_tbl.add_row()
        for i, val in enumerate(row_data):
            row.cells[i].text = val
    format_table(dem_tbl, [Inches(1.2), Inches(1.8), Inches(1.0), Inches(0.8), Inches(1.0), Inches(0.8)])

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "08_Tuljapur_DEM_Map.png",
        "Figure 2.1: Digital Elevation Model (Copernicus GLO-30) and Shaded Relief of Tuljapur Block."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "02_Tuljapur_Contour_Map.png",
        "Figure 2.2: Cartographic 10-Meter Topographic Contour Map of Tuljapur Block."
    )

    # =========================================================================
    # CHAPTER 3: SLOPE & TERRAIN RUGGEDNESS
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 3: SLOPE & TERRAIN RUGGEDNESS", level=1)

    p_ch3 = doc.add_paragraph()
    p_ch3.add_run(
        "Topographic slope exerts a decisive control over overland runoff velocity, soil erosion susceptibility, "
        "and infiltration capacity. The regional terrain is dominated by flat to very gentle slopes: 84.2% of Tuljapur "
        "and 95.7% of Lohara exhibit gradients below 3° (0–5% slope). Nearly level tablelands (0–1°) cover 458.8 km² (30.6%) "
        "in Tuljapur and 260.7 km² (48.0%) in Lohara, presenting optimal conditions for agricultural cultivation and low "
        "soil erosion risk.\n\n"
        "Steep escarpments (>10° slope) are confined to the northern Balaghat plateau scarp in Tuljapur (27.0 km² | 1.8%) "
        "around Apsinga and Dhekri, and along incised stream gorges. These steep scarp zones act as major runoff-generating "
        "source catchments that require strict mechanical soil conservation measures such as Continuous Contour Trenches (CCT) "
        "and vegetative barriers."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "10_Tuljapur_Slope_Map.png",
        "Figure 3.1: Topographic Slope Classification Map of Tuljapur Block."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Lohara" / "10_Lohara_Slope_Map.png",
        "Figure 3.2: Topographic Slope Classification Map of Lohara Block."
    )

    # =========================================================================
    # CHAPTER 4: HYDROLOGY & DRAINAGE NETWORK MORPHOMETRY
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 4: HYDROLOGY & DRAINAGE NETWORK MORPHOMETRY", level=1)

    p_ch4 = doc.add_paragraph()
    p_ch4.add_run(
        "The drainage architecture of the study area is bifurcated across two major river sub-basins:\n"
        "1. Bori River Sub-basin (Sina / Bhima / Krishna Basin): Drains the entirety of central, western, and southern Tuljapur, "
        "flowing south-eastwards past Naldurg where the historic Naldurg fort impounds a major perennial reservoir.\n"
        "2. Terna River Sub-basin (Manjra / Godavari Basin): Drains northern Tuljapur and the whole of Lohara block, flowing "
        "eastwards towards the Lower Terna Project and contributing to the Godavari river system.\n\n"
        "A rigorous Strahler stream order analysis derived from the hydrologically conditioned 30 m DEM reveals a total stream "
        "network length of 2,191.73 km comprising 2,230 segments across Orders 1 to 5. The drainage density (Dd) is remarkably "
        "uniform at 1.07 km/km² across both blocks, reflecting mature dendritic drainage developed over horizontally bedded basalt flows."
    )

    # Stream Orders Table
    add_custom_heading(doc, "Strahler Stream Hierarchy Breakdown by Block", level=2)
    strm_tbl = doc.add_table(rows=1, cols=7)
    strm_hdrs = ["Order", "Stream Classification", "Tuljapur (Seg)", "Tuljapur (km)", "Lohara (Seg)", "Lohara (km)", "Total (km)"]
    for i, h in enumerate(strm_hdrs):
        strm_tbl.rows[0].cells[i].text = h

    strm_rows = [
        ["Order 1", "Headwater Ephemeral Gully", "827", "843.66", "310", "305.71", "1,149.37"],
        ["Order 2", "Secondary Tributary", "359", "400.71", "153", "146.96", "547.67"],
        ["Order 3", "Major Drainage Stream", "280", "236.73", "96", "75.76", "312.49"],
        ["Order 4", "Sub-Basin Trunk River", "125", "109.93", "52", "40.37", "150.30"],
        ["Order 5", "Major Confluence Reach", "22", "17.72", "24", "14.18", "31.90"],
        ["TOTAL", "Complete Stream Network", "1,613", "1,608.75", "635", "582.98", "2,191.73"]
    ]
    for row_data in strm_rows:
        row = strm_tbl.add_row()
        for i, val in enumerate(row_data):
            row.cells[i].text = val
    format_table(strm_tbl, [Inches(0.8), Inches(1.8), Inches(0.9), Inches(0.9), Inches(0.9), Inches(0.9), Inches(0.9)])

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "11_Tuljapur_Stream_Order_Map.png",
        "Figure 4.1: Strahler Stream Order Classification Map of Tuljapur Block (Orders 1 to 5)."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Lohara" / "11_Lohara_Stream_Order_Map.png",
        "Figure 4.2: Strahler Stream Order Classification Map of Lohara Block (Orders 1 to 5)."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "16_Tuljapur_Drainage_Density_Map.png",
        "Figure 4.3: Continuous Drainage Density (Dd) Heatmap of Tuljapur Block (50m Metric KDE Stream Concentration)."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Lohara" / "16_Lohara_Drainage_Density_Map.png",
        "Figure 4.4: Continuous Drainage Density (Dd) Heatmap of Lohara Block (50m Metric KDE Stream Concentration)."
    )

    # =========================================================================
    # CHAPTER 5: CLIMATOLOGY & 34-YEAR PRECIPITATION DYNAMICS
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 5: CLIMATOLOGY & PRECIPITATION DYNAMICS", level=1)

    p_ch5 = doc.add_paragraph()
    p_ch5.add_run(
        "The climate of Dharashiv district is semi-arid, characterized by hot dry summers, general dryness throughout the year "
        "except during the southwest monsoon, and erratic precipitation. Analysis of a 34-year gridded precipitation timeseries "
        "(CHIRPS 5.5 km resolution, 1991–2024) indicates a long-term mean annual rainfall of 768.4 mm across the AOI (762.5 mm in "
        "Tuljapur and 786.1 mm in Lohara).\n\n"
        "Precipitation is highly seasonal: over 81.8% (628.5 mm) is received during the four southwest monsoon months (June to September). "
        "Post-monsoon retreating rains (October–November) contribute 13.5% (103.8 mm), while pre-monsoon thunderstorms (March–May) and "
        "winter rains (December–January) contribute 4.4% (34.0 mm) and 0.3% (2.1 mm), respectively.\n\n"
        "The coefficient of variation (CV) is 23.4%, denoting significant inter-annual rainfall variability. Drought anomaly "
        "analysis identifies recurring meteorological deficit years (such as 1997, 2012, and 2015, where precipitation dropped "
        "below 500 mm), underscoring the absolute necessity for decentralized rainwater harvesting and artificial aquifer recharge."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "06_Tuljapur_Rainfall_Isohyet_Map.png",
        "Figure 5.1: 34-Year Mean Annual Rainfall Isohyets and Precipitation Gradient across Tuljapur Block."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Lohara" / "06_Lohara_Rainfall_Isohyet_Map.png",
        "Figure 5.2: 34-Year Mean Annual Rainfall Isohyets and Precipitation Gradient across Lohara Block."
    )

    # =========================================================================
    # CHAPTER 6: PEDOLOGY, SOIL TEXTURE & INFILTRATION
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 6: PEDOLOGY, SOIL TEXTURE & INFILTRATION", level=1)

    p_ch6 = doc.add_paragraph()
    p_ch6.add_run(
        "The pedological mantle across the study area has developed entirely through in-situ weathering of Deccan basalt rock "
        "under alternating wet and dry semi-arid regimes. Based on National Bureau of Soil Survey & Land Use Planning (NBSS&LUP) "
        "and ISRIC SoilGrids datasets, the soils exhibit extreme depth contrasts:\n"
        "1. Very Shallow Soils (10–25 cm depth | Lithic Ustorthents): Cover 1,049.92 km² (70.0%) in Tuljapur and 312.56 km² (57.7%) "
        "in Lohara. These soils are gravelly, highly permeable but possess negligible moisture retention capacity, leaving crops "
        "extremely vulnerable to mid-season dry spells.\n"
        "2. Shallow Soils (25–50 cm depth | Lithic Haplustepts): Cover 131.55 km² (8.8%) in Tuljapur and 180.74 km² (33.3%) in Lohara, "
        "occupying mid-plateau positions.\n"
        "3. Deep to Moderately Deep Soils (>50 cm depth | Typic Chromusterts): Cover 317.60 km² (21.2%) in Tuljapur and 48.73 km² (9.0%) "
        "in Lohara, restricted to low-lying river plains and alluvial terraces.\n\n"
        "Textural classification according to the USDA Soil Texture Triangle indicates an overwhelming dominance of Heavy Clay "
        "(Vertisols) covering 93.2% of the AOI. These montmorillonite-rich clays expand upon wetting and develop deep vertical cracks "
        "during dry periods. Infiltration is rapid when cracks are open but drops drastically to 1.0–5.0 mm/hr once soils become saturated."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "04_Tuljapur_Soil_Depth_Map.png",
        "Figure 6.1: NBSS & LUP Soil Depth Profile Classification Map of Tuljapur Block."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "13_Tuljapur_Soil_Texture_Map.png",
        "Figure 6.2: USDA Soil Texture Classification Map (OpenLandMap TT 250m) of Tuljapur Block."
    )

    # =========================================================================
    # CHAPTER 7: LAND USE / LAND COVER & SEASONAL VEGETATION DYNAMICS
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 7: LAND USE / LAND COVER & VEGETATION DYNAMICS", level=1)

    p_ch7 = doc.add_paragraph()
    p_ch7.add_run(
        "Agriculture is the primary economic livelihood across both blocks, occupying 73.5% (1,503.7 km²) of the total mapped land. "
        "According to NRSC 1:250,000 multi-temporal LULC data:\n"
        "• Kharif Cropland (27.8% | 566.9 km²): Characterized by rainfed soybean, cotton, pigeonpea (tur), and kharif sorghum.\n"
        "• Rabi Cropland (3.5% | 72.2 km²): Winter chickpea (gram), rabi jowar, and wheat supported by residual moisture and well irrigation.\n"
        "• Double / Triple Cropping (14.0% | 285.5 km²): High-intensity cash crops (sugarcane, horticulture, vegetables) along river channels.\n"
        "• Current Fallow (28.2% | 575.3 km²): Arable lands resting due to monsoon rainfall deficits or lack of irrigation access.\n"
        "• Wastelands & Rocky Scrub (20.1% | 410.0 km²): Stony basalt plateau ridges and barren pasture lands.\n\n"
        "Seasonal vegetation dynamics evaluated using Sentinel-2 L2A 10m NDVI composites reveal dramatic seasonal contraction. "
        "Mean NDVI reaches 0.476 in the Kharif season (September 2024 peak biomass), with 38.1% of the land exceeding 0.45 NDVI. "
        "By post-monsoon winter (Rabi season, January 2025), mean NDVI contracts to 0.354, with dense vegetation shrinking to 17.8%, "
        "highlighting intense dependence on groundwater draft during dry winter months."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "03_Tuljapur_LULC_Map.png",
        "Figure 7.1: NRSC Land Use / Land Cover (LULC 1:250,000) Classification Map of Tuljapur Block."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "12_Tuljapur_Seasonal_NDVI_Map.png",
        "Figure 7.2: Sentinel-2 10m Seasonal NDVI Crop Biomass Dynamics (Kharif vs Rabi 2024–2025) of Tuljapur Block."
    )

    # =========================================================================
    # CHAPTER 8: GEOMORPHOLOGY & HYDROGEOLOGICAL LANDFORMS
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 8: GEOMORPHOLOGY & HYDROGEOLOGICAL LANDFORMS", level=1)

    p_ch8 = doc.add_paragraph()
    p_ch8.add_run(
        "Hydrogeomorphological mapping based on NRSC Bhuvan 1:50,000 data reveals four primary landform complexes that dictate "
        "ground water storage and movement:\n"
        "1. Plateau Top Tableland (51.8% | 1,058.4 km²): Flat, elevated basaltic plateaus that generate rapid overland sheet wash. "
        "Ground water prospects are poor to moderate; suitable for continuous contour trenches and surface farm ponds.\n"
        "2. Weathered Pediplain (30.6% | 624.5 km²): Gently sloping undulating plains with saprolitic weathering mantles (3–10 m depth). "
        "Acts as the primary unconfined aquifer zone; excellent siting for percolation tanks and masonry check dams.\n"
        "3. Dissected Escarpment Slopes (8.6% | 175.2 km²): Steep step-like basalt scarp edges with high runoff velocity; requires gully plugs.\n"
        "4. Valley Fill Alluvial Corridors (6.2% | 125.8 km²): Depositional gravel-sand-silt corridors along the Bori and Terna rivers. "
        "Presents the highest groundwater yields in the region; priority zone for subsurface dykes to arrest summer baseflow escape."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "14_Tuljapur_Geomorphology_Map.png",
        "Figure 8.1: NRSC Bhuvan 1:50,000 Geomorphology and Hydrogeomorphic Landforms Map of Tuljapur Block."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Lohara" / "14_Lohara_Geomorphology_Map.png",
        "Figure 8.2: NRSC Bhuvan 1:50,000 Geomorphology and Hydrogeomorphic Landforms Map of Lohara Block."
    )

    # =========================================================================
    # CHAPTER 9: HARD-ROCK LITHOLOGY & CGWB WELL OBSERVATIONS
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 9: HARD-ROCK LITHOLOGY & REGIONAL WELLS", level=1)

    p_ch9 = doc.add_paragraph()
    p_ch9.add_run(
        "Geologically, the entire study area is underlain by the Deccan Volcanic Province (Upper Cretaceous to Eocene basalt flows). "
        "The stratigraphy comprises horizontally bedded lava flows varying from 10 m to 35 m in individual thickness, classified into:\n"
        "• Pahoehoe Flows: Characterized by highly vesicular flow tops, ropy structures, and zeolitic infillings (stilbite, heulandite). "
        "The upper vesicular zones form prime localized aquifers when weathered.\n"
        "• 'Aa' Flows: Characterized by dense, hard, massive basalt cores bounded by fragmented, brecciated flow tops. "
        "Groundwater movement is strictly controlled by vertical cooling joints and regional tectonic lineaments.\n\n"
        "Exploratory well telemetry from the Central Ground Water Board (CGWB) network across 45 regional wells shows static water "
        "levels (SWL) typically fluctuating between 5.5 m and 22.0 m below ground level (mbgl). Well discharge yields vary widely from "
        "0.5 lps in massive unjointed basalt to over 7.5 lps in fractured vesicular interflow contacts, demonstrating the secondary "
        "porosity-controlled nature of hard-rock hydrogeology."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "07_Tuljapur_Lithology_Map.png",
        "Figure 9.1: Geological Lithology and Regional CGWB Well Network Map of Tuljapur Block."
    )

    # =========================================================================
    # CHAPTER 10: RGNDWM 250K GROUND WATER PROSPECTS FRAMEWORK
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 10: RGNDWM 250K GROUND WATER PROSPECTS FRAMEWORK", level=1)

    p_ch10 = doc.add_paragraph()
    p_ch10.add_run(
        "The Rajiv Gandhi National Drinking Water Mission (RGNDWM) Ground Water Prospects Mapping project was executed by the "
        "National Remote Sensing Centre (NRSC / ISRO) in collaboration with state groundwater agencies. Its primary goal is "
        "to provide space-based hydrogeomorphological and structural information for locating sustainable rural drinking water "
        "sources and identifying recharge structure locations on 1:50,000 Survey of India toposheet scales.\n\n"
        "As established in this investigation, Tuljapur and Lohara blocks straddle the intersection of four Survey of India 1° × 1° "
        "master quadrangles (Sheets 56C, 56B, 47O, and 47N) converging at 76°00'00\"E and 18°00'00\"N. The exact 1:50,000 toposheet "
        "matrix encompasses ten tiles, led by Sheet 56C/1 (699.1 km² | 34.2%) and Sheet 56C/2 (551.0 km² | 27.0%)."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "AOI_RGNDWM_250k_Ground_Water_Prospects_Framework_Map.png",
        "Figure 10.1: Master RGNDWM 250K Ground Water Prospects Grid Framework & 1:50,000 Toposheet Matrix Map for the AOI.",
        width=Inches(6.4)
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Tuljapur" / "15_Tuljapur_RGNDWM_250k_Framework_Map.png",
        "Figure 10.2: RGNDWM 250K & 1:50,000 Toposheet Grid Framework Map for Tuljapur Block."
    )

    add_figure_image(
        doc,
        MAPS_DIR / "Lohara" / "15_Lohara_RGNDWM_250k_Framework_Map.png",
        "Figure 10.3: RGNDWM 250K & 1:50,000 Toposheet Grid Framework Map for Lohara Block."
    )

    # =========================================================================
    # CHAPTER 11: WATERSHED RECHARGE SITING & STRATEGIC RECOMMENDATIONS
    # =========================================================================
    add_custom_heading(doc, "CHAPTER 11: WATERSHED RECHARGE SITING & RECOMMENDATIONS", level=1)

    p_ch11 = doc.add_paragraph()
    p_ch11.add_run(
        "Based on the integration of all 15 thematic layers, terrain slopes, stream orders, soil textures, and hydrogeomorphology, "
        "a strategic artificial recharge structure siting matrix has been established to guide field engineering investments under "
        "the Jal Jeevan Mission and watershed development programs:"
    )

    recharge_tbl = doc.add_table(rows=1, cols=4)
    r_hdrs = ["Intervention Type", "Siting Criteria (Stream / Slope / Unit)", "Expected Hydrological Impact", "Priority Target Zones"]
    for i, h in enumerate(r_hdrs):
        recharge_tbl.rows[0].cells[i].text = h

    r_matrix = [
        ["Percolation Tanks (PT)", "3rd to 4th order streams; slope 1–3°; weathered pediplain with >3m saprolite depth", "Augments regional shallow water table (50,000–150,000 m³ storage per tank)", "Andur, Kati, Mangrul, Chikundra, Karla, Tirth"],
        ["Masonry Check Dams (CD)", "2nd to 3rd order streams; slope 1–5°; fractured basalt bedrock bed", "Decelerates flash runoff; creates post-monsoon pooling (10,000–30,000 m³)", "Bori river secondary tributaries, Terna sub-basin"],
        ["Subsurface Dykes (SSD)", "4th to 5th order streams; slope <1°; alluvial valley fill over bedrock bar", "Arrests dry-season subsurface flow egress; maintains dugwell yields till summer", "Naldurg downstream, Bori alluvial neck, Terna channel"],
        ["Continuous Contour Trenches (CCT)", "Upper catchment ridges; slope 5–15°; hard basalt escarpment flanks", "Intercepts overland sheet wash, enhances slope infiltration, prevents siltation", "Apsinga ridge, Kamtha scarp, Balaghat plateau divide"],
        ["Farm Ponds (FP)", "Overland drainage swales; slope <2°; deep black cotton soils (Vertisols)", "Provides critical protective irrigation during mid-monsoon dry spells (2,000–5,000 m³)", "Extensive cultivated plains of central Tuljapur & Lohara"],
        ["Well Recharge Shafts", "Direct well recharge; existing depleted dugwells across settlements", "Bypasses impermeable surface clay; injects filtered rainwater into basalt aquifers", "All 177 Gram Panchayats with critical drinking water wells"]
    ]
    for row_data in r_matrix:
        row = recharge_tbl.add_row()
        for i, val in enumerate(row_data):
            row.cells[i].text = val
    format_table(recharge_tbl, [Inches(1.5), Inches(2.0), Inches(1.5), Inches(1.5)])

    # =========================================================================
    # ANNEXURES: COMPLETE 177-VILLAGE DIRECTORY
    # =========================================================================
    doc.add_page_break()
    add_custom_heading(doc, "ANNEXURE I: COMPLETE 177-VILLAGE CADASTRAL DIRECTORY", level=1)

    p_ann = doc.add_paragraph()
    p_ann.add_run(
        "Complete enumeration of all 177 cadastral revenue village units across Tuljapur Block (130 villages) "
        "and Lohara Block (47 villages), documenting calculated GIS areas in hectares and square kilometers:"
    )

    sub_path = MAP_DATA / "aoi" / "subblocks_villages.gpkg"
    if sub_path.exists():
        sub = gpd.read_file(sub_path).to_crs("EPSG:32643")
        sub_sorted = sub.sort_values(["BLOCK", "VILLAGE"]).reset_index(drop=True)

        v_tbl = doc.add_table(rows=1, cols=5)
        v_hdrs = ["S.No", "Taluka / Block", "Cadastral Village Name", "Area (Hectares)", "Area (km²)"]
        for i, h in enumerate(v_hdrs):
            v_tbl.rows[0].cells[i].text = h

        for idx, r in sub_sorted.iterrows():
            row = v_tbl.add_row()
            row.cells[0].text = str(idx + 1)
            row.cells[1].text = str(r["BLOCK"])
            row.cells[2].text = str(r["VILLAGE"])
            ha = round(r.geometry.area / 10000.0, 1)
            km2 = round(r.geometry.area / 1e6, 2)
            row.cells[3].text = f"{ha:,.1f}"
            row.cells[4].text = f"{km2:,.2f}"

        format_table(v_tbl, [Inches(0.6), Inches(1.2), Inches(2.4), Inches(1.1), Inches(1.1)])

    # Save Word Report (Single Canonical Output in deliverables/reports)
    print(f"Saving Master Word Report to {OUT_DOCX}...")
    try:
        doc.save(OUT_DOCX)
        print("SUCCESS: Master Client-Grade Word Report Created at:", OUT_DOCX)
    except PermissionError:
        fallback = DELIV_REPORTS / "Tuljapur_Lohara_Comprehensive_GIS_Environmental_Atlas_Report_Latest.docx"
        print(f"NOTE: {OUT_DOCX.name} is open in Word. Saved to {fallback.name} instead.")
        doc.save(fallback)
        print("SUCCESS: Master Client-Grade Word Report Created at:", fallback)


if __name__ == "__main__":
    build_word_report()
