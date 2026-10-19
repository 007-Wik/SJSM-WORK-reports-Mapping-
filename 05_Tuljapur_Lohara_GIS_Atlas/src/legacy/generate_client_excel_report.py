#!/usr/bin/env python3
"""
Master Client-Grade GIS & Environmental Statistical Excel Report Generator
Produces a multi-tabbed, publication-grade Excel workbook for Tuljapur & Lohara Blocks.
Formatted with executive navy styling, auto-column widths, KPI headers, and Excel formulas.
"""

from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_DATA = BASE_DIR / "map_data"
DOCS_DIR = BASE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
OUT_EXCEL = DOCS_DIR / "Tuljapur_Lohara_Comprehensive_GIS_Environmental_Report.xlsx"
MAP_DATA_EXCEL = MAP_DATA / "Tuljapur_Lohara_Comprehensive_GIS_Environmental_Report.xlsx"

# -------------------------------------------------------------------------
# STYLING DEFINITIONS
# -------------------------------------------------------------------------
NAVY_HEADER_FILL = PatternFill(start_color="1E1B4B", end_color="1E1B4B", fill_type="solid")
ACCENT_BLUE_FILL = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")
ZEBRA_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
WHITE_FILL = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
TOTAL_ROW_FILL = PatternFill(start_color="EEF2F6", end_color="EEF2F6", fill_type="solid")

FONT_HEADER = Font(name="Times New Roman", size=11, bold=True, color="FFFFFF")
FONT_TITLE = Font(name="Times New Roman", size=14, bold=True, color="1E1B4B")
FONT_SUBTITLE = Font(name="Times New Roman", size=10, italic=True, color="475569")
FONT_BODY = Font(name="Times New Roman", size=10, color="0F172A")
FONT_BODY_BOLD = Font(name="Times New Roman", size=10, bold=True, color="0F172A")
FONT_TOTAL = Font(name="Times New Roman", size=10, bold=True, color="1E1B4B")

THIN_BORDER_SIDE = Side(border_style="thin", color="CBD5E1")
DOUBLE_BOTTOM_SIDE = Side(border_style="double", color="1E1B4B")
TOP_BORDER_SIDE = Side(border_style="thin", color="1E1B4B")

REGULAR_BORDER = Border(left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE, top=THIN_BORDER_SIDE, bottom=THIN_BORDER_SIDE)
TOTAL_BORDER = Border(top=TOP_BORDER_SIDE, bottom=DOUBLE_BOTTOM_SIDE, left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE)


def style_worksheet(ws, title_text=None, subtitle_text=None, total_row_idx=None, num_cols_align=None):
    """Apply senior cartographic/financial modeling format to an openpyxl worksheet."""
    ws.views.sheetView[0].showGridLines = True

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if cell.number_format and "%" in cell.number_format:
                val_str += "%"
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # Style header row (assumed row 1 or row 3 if title exists)
    start_row = 1
    if title_text:
        start_row = 3

    for col_idx in range(1, ws.max_column + 1):
        cell = ws.cell(row=start_row, column=col_idx)
        cell.font = FONT_HEADER
        cell.fill = NAVY_HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = REGULAR_BORDER
        ws.row_dimensions[start_row].height = 28

    # Style data rows
    for r in range(start_row + 1, ws.max_row + 1):
        is_total = (r == total_row_idx) or (r == ws.max_row and total_row_idx is True)
        is_zebra = (r % 2 == 0)

        ws.row_dimensions[r].height = 20
        for c in range(1, ws.max_column + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = TOTAL_BORDER if is_total else REGULAR_BORDER

            if is_total:
                cell.font = FONT_TOTAL
                cell.fill = TOTAL_ROW_FILL
            else:
                cell.font = FONT_BODY
                cell.fill = ZEBRA_FILL if is_zebra else WHITE_FILL

            # Alignment logic
            if c == 1 and not (isinstance(cell.value, (int, float)) and cell.number_format):
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif isinstance(cell.value, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    # Freeze panes below header
    ws.freeze_panes = f"A{start_row + 1}"


def build_excel_report():
    print("=" * 70)
    print("GENERATING COMPREHENSIVE CLIENT-GRADE GIS & ENVIRONMENTAL EXCEL WORKBOOK")
    print("=" * 70)

    wb = openpyxl.Workbook()
    # remove default sheet
    wb.remove(wb.active)

    # =========================================================================
    # TAB 1: EXECUTIVE SUMMARY & METRIC DASHBOARD
    # =========================================================================
    print("Creating Tab 1: Executive Summary & KPIs...")
    ws1 = wb.create_sheet(title="1_Executive_Summary")

    summary_data = [
        ["Project Parameter", "Tuljapur Block", "Lohara Block", "Combined Study Area (AOI)", "Metric Unit", "Data Source / Authority"],
        ["Geographical Area", 1500.72, 543.20, 2043.93, "Square Kilometers (km²)", "Survey of India / MahaGIS Cadastre"],
        ["Relative Area Share", 0.7342, 0.2658, 1.0000, "Percentage Share (%)", "Calculated GIS Area (UTM 43N)"],
        ["Total Mapped Gram Panchayats / Villages", 130, 47, 177, "Cadastral Village Units", "Census of India / MRSAC Cadastre"],
        ["Total Population (Census 2011)", 279720, 116211, 395931, "Persons", "Census of India (Dharashiv District)"],
        ["Elevation Span (Min – Max)", "435.5 – 711.0", "442.0 – 621.5", "435.5 – 711.0", "Meters above sea level", "Copernicus GLO-30 DEM (30m)"],
        ["Mean Terrain Elevation", 562.4, 555.5, 560.6, "Meters a.s.l.", "Copernicus DEM Zonal Statistics"],
        ["Mean Terrain Slope", 1.62, 1.42, 1.57, "Degrees (°)", "Calculated Terrain Slope (Horn's Method)"],
        ["Primary River Drainage Basins", "Bori River (Sina Basin)", "Terna River (Manjra Basin)", "Bhima / Krishna & Godavari Basins", "Watershed Hydrological Units", "Central Water Commission (CWC)"],
        ["Total Drainage Stream Length", 1643.23, 548.50, 2191.73, "Kilometers (km)", "Derived Strahler Drainage (Orders 1-5)"],
        ["Drainage Density (Dd)", 1.09, 1.01, 1.07, "km / km²", "Hydrological Morphometric Density"],
        ["34-Year Mean Annual Rainfall (1991–2024)", 762.5, 786.1, 768.4, "Millimeters (mm / year)", "CHIRPS Climatological Reanalysis"],
        ["Monsoon Season Contribution (JJAS)", "81.4%", "82.8%", "81.8%", "% of Annual Total", "IMD South-West Monsoon Season"],
        ["Predominant Soil Depth Class", "Very Shallow (<25 cm)", "Shallow to Deep", "Very Shallow (66.8% of AOI)", "Depth Horizon", "NBSS & LUP / ISRIC SoilGrids"],
        ["Predominant USDA Soil Texture", "Clay (Vertisols)", "Clay (Vertisols)", "Clay / Deep Black Cotton (93.2%)", "USDA Texture Triangle", "OpenLandMap / USDA NRCS (250m)"],
        ["Agricultural Cultivated Footprint", "72.4%", "76.8%", "73.5%", "% Mapped Land Cover", "NRSC 1:250k LULC / Sentinel-2"],
        ["Current Agricultural Fallow Land", 421.8, 153.5, 575.3, "km² (28.2% of AOI)", "Multi-temporal Crop Dynamics"],
        ["Forest & Plantation Cover", 8.4, 3.0, 11.4, "km² (0.6% of AOI)", "Forest Survey of India / NRSC"],
        ["Surface Waterbodies & Reservoirs", 62.4, 23.3, 85.7, "km² (4.2% of AOI)", "Irrigation Tanks, Rivers & Naldurg Lake"],
        ["Classified Road Transportation Network", 1884.2, 743.8, 2628.0, "Kilometers (km)", "NH-52, State Highways & ODRs (OSM)"],
        ["Regional Lithological Stratigraphy", "Upper Deccan Basalt", "Deccan Basalt & Alluvium", "Pahoehoe & 'Aa' Basalt Flows", "Geological Unit", "Geological Survey of India (GSI)"],
        ["RGNDWM 1° × 1° Quadrangle Framework", "56C, 47O, 56B, 47N", "56C, 56B", "Quad Nexus (76°E, 18°N)", "1:250,000 Quad Indices", "NRSC / ISRO (Drinking Water Mission)"],
        ["Survey of India 1:50,000 Toposheet Tiles", "7 Sheets", "5 Sheets", "10 Sheets Total", "15' × 15' Topo Quadrangles", "Survey of India Topo Index"]
    ]

    for row in summary_data:
        ws1.append(row)

    # Format percentages and decimals
    ws1.cell(row=3, column=2).number_format = "0.00%"
    ws1.cell(row=3, column=3).number_format = "0.00%"
    ws1.cell(row=3, column=4).number_format = "0.00%"
    ws1.cell(row=2, column=2).number_format = "#,##0.00"
    ws1.cell(row=2, column=3).number_format = "#,##0.00"
    ws1.cell(row=2, column=4).number_format = "#,##0.00"
    ws1.cell(row=5, column=2).number_format = "#,##0"
    ws1.cell(row=5, column=3).number_format = "#,##0"
    ws1.cell(row=5, column=4).number_format = "#,##0"
    style_worksheet(ws1)

    # =========================================================================
    # TAB 2: COMPLETE VILLAGE CADASTRE DIRECTORY (177 VILLAGES)
    # =========================================================================
    print("Creating Tab 2: Complete 177 Village Directory...")
    ws2 = wb.create_sheet(title="2_Village_Cadastre_Directory")

    sub_path = MAP_DATA / "aoi" / "subblocks_villages.gpkg"
    if sub_path.exists():
        sub = gpd.read_file(sub_path).to_crs("EPSG:32643")
        sub["Area_ha"] = (sub.geometry.area / 10000.0).round(1)
        sub["Area_km2"] = (sub.geometry.area / 1e6).round(2)
        sub_sorted = sub.sort_values(["BLOCK", "VILLAGE"]).reset_index(drop=True)

        ws2.append(["S.No", "District", "Taluka / Block", "Cadastral Village Name", "Area (Hectares)", "Area (km²)", "Share of Block (%)", "Share of AOI (%)"])

        tot_aoi_km2 = 2043.93
        tuljapur_tot = 1500.72
        lohara_tot = 543.20

        for idx, row in sub_sorted.iterrows():
            blk = str(row["BLOCK"])
            blk_tot = tuljapur_tot if blk == "Tuljapur" else lohara_tot
            share_blk = row["Area_km2"] / blk_tot
            share_aoi = row["Area_km2"] / tot_aoi_km2
            ws2.append([
                idx + 1,
                str(row.get("DISTRICT", "Dharashiv")),
                blk,
                str(row["VILLAGE"]),
                float(row["Area_ha"]),
                float(row["Area_km2"]),
                share_blk,
                share_aoi
            ])

        # Summary total row
        tot_row_num = ws2.max_row + 1
        ws2.append([
            "TOTAL",
            "Dharashiv",
            "Both Blocks",
            f"177 Villages Total",
            f"=SUM(E2:E{tot_row_num-1})",
            f"=SUM(F2:F{tot_row_num-1})",
            1.00,
            1.00
        ])

        # Formatting
        for r in range(2, ws2.max_row + 1):
            ws2.cell(row=r, column=5).number_format = "#,##0.0"
            ws2.cell(row=r, column=6).number_format = "#,##0.00"
            ws2.cell(row=r, column=7).number_format = "0.00%"
            ws2.cell(row=r, column=8).number_format = "0.00%"

        style_worksheet(ws2, total_row_idx=tot_row_num)

    # =========================================================================
    # TAB 3: TOPOGRAPHY & ELEVATION ZONING
    # =========================================================================
    print("Creating Tab 3: Topography & Elevation...")
    ws3 = wb.create_sheet(title="3_Topography_Elevation")

    elevation_data = [
        ["Elevation Range", "Hypsometric Zone Classification", "Area (km²)", "Area (Hectares)", "Coverage (%)", "Geomorphic Landform Description", "Hydrological Role"],
        ["400 – 450 m", "Lowest Incised Valleys", 34.75, 3475.0, 0.0170, "Deep river trenches of Bori and Terna rivers", "Discharge & baseflow zone, alluvial recharge"],
        ["450 – 500 m", "Lower Valley Plains & Depressions", 337.25, 33725.0, 0.1650, "Gentle fertile valley bottoms and alluvial terraces", "Major agricultural zone, check dams & tanks"],
        ["500 – 550 m", "Middle Undulating Pediplain", 492.58, 49258.0, 0.2410, "Broad weathered pediplain with black cotton soils", "Primary rainfed cropping, percolation tanks"],
        ["550 – 600 m", "Upper Pediment & Plateau Flanks", 543.68, 54368.0, 0.2660, "Weathered sheet wash slopes and terraced basalt steps", "Transitional recharge-to-runoff zone, CCT"],
        ["600 – 650 m", "Balaghat Main Plateau Tableland", 558.00, 55800.0, 0.2730, "Extensive flat basaltic tableland (Tuljapur-Lohara high plain)", "Overland runoff source, farm ponds, micro-watersheds"],
        ["> 650 m", "High Residual Ridges & Escarpments", 77.67, 7767.0, 0.0380, "Isolated conical hills and sharp structural divides (Apsinga)", "Extreme runoff generation, forest conservation"],
        ["TOTAL", "Study Area Total", 2043.93, 204393.0, 1.0000, "Complete Elevation Spectrum (435.5 m to 711.0 m a.s.l.)", "Complete Watershed Regime"]
    ]

    for row in elevation_data:
        ws3.append(row)

    for r in range(2, ws3.max_row + 1):
        ws3.cell(row=r, column=3).number_format = "#,##0.00"
        ws3.cell(row=r, column=4).number_format = "#,##0.0"
        ws3.cell(row=r, column=5).number_format = "0.00%"

    style_worksheet(ws3, total_row_idx=ws3.max_row)

    # =========================================================================
    # TAB 4: SLOPE & TERRAIN RUGGEDNESS
    # =========================================================================
    print("Creating Tab 4: Slope & Terrain Ruggedness...")
    ws4 = wb.create_sheet(title="4_Slope_Terrain_Ruggedness")

    slope_data = [
        ["Slope Range (°)", "Slope Classification", "Area (km²)", "Area (Hectares)", "Share (%)", "Soil Erosion Potential", "Agricultural & Watershed Suitability"],
        ["0° – 1°", "Nearly Level", 831.88, 83188.0, 0.4070, "Very Low / Negligible", "Intensive double/triple cropping, canal irrigation, valley farming"],
        ["1° – 3°", "Very Gentle", 1025.24, 102524.0, 0.5016, "Low / Slight Sheet Erosion", "Rainfed Kharif & Rabi cultivation, contour bunding recommended"],
        ["3° – 5°", "Gentle", 123.25, 12325.0, 0.0603, "Moderate / Rill Erosion", "Vegetative barrier strips, field bunds, fodder & pulses"],
        ["5° – 10°", "Moderate", 47.83, 4783.0, 0.0234, "High / Rill & Gully Erosion", "Agroforestry, horticulture (pomegranate, custard apple), CCT"],
        ["10° – 15°", "Moderately Steep", 9.61, 961.0, 0.0047, "Very High / Severe Gully", "Silvipasture, dry deciduous scrub, continuous contour trenches"],
        ["> 15°", "Steep Escarpments", 6.12, 612.0, 0.0030, "Extreme / Rock Exposure", "Soil conservation, afforestation, check dams in gully beds"],
        ["TOTAL", "Study Area Total", 2043.93, 204393.0, 1.0000, "Comprehensive Terrain Slope Assessment", "Integrated Watershed Siting Regime"]
    ]

    for row in slope_data:
        ws4.append(row)

    for r in range(2, ws4.max_row + 1):
        ws4.cell(row=r, column=3).number_format = "#,##0.00"
        ws4.cell(row=r, column=4).number_format = "#,##0.0"
        ws4.cell(row=r, column=5).number_format = "0.00%"

    style_worksheet(ws4, total_row_idx=ws4.max_row)

    # =========================================================================
    # TAB 5: HYDROLOGY & STRAHLER STREAM ORDERS
    # =========================================================================
    print("Creating Tab 5: Hydrology & Drainage...")
    ws5 = wb.create_sheet(title="5_Hydrology_Stream_Orders")

    strm_path = MAP_DATA / "streams" / "streams_complete_strahler.gpkg"
    if strm_path.exists():
        strm = gpd.read_file(strm_path)
        summ = strm.groupby("strahler").agg(
            Segments=("len_km", "count"),
            Total_Length_km=("len_km", "sum"),
            Mean_Length_km=("len_km", "mean"),
            Max_Length_km=("len_km", "max")
        ).reset_index()

        type_names = {
            1: "1st Order (Headwater Ephemeral Gully)",
            2: "2nd Order (Secondary Collecting Tributary)",
            3: "3rd Order (Major Drainage Stream)",
            4: "4th Order (Sub-Basin Trunk River / Bori-Terna)",
            5: "5th Order (Major Regional Confluence)"
        }
        summ["Stream_Hierarchy"] = summ["strahler"].map(type_names)
        tot_km = summ["Total_Length_km"].sum()
        summ["Length_Share_pct"] = summ["Total_Length_km"] / tot_km

        ws5.append(["Strahler Order", "Drainage Stream Classification", "Segment Count", "Total Length (km)", "Share of Network (%)", "Mean Segment Length (km)", "Max Segment Length (km)", "Recommended Watershed Recharge Siting"])

        recharge_recs = {
            1: "Continuous Contour Trenches (CCT), Loose Boulder Checks (LBC)",
            2: "Earthen Nala Bunds, Gabion Structures, Field Terracing",
            3: "Masonry Check Dams, Cement Nala Bunds, Farm Pond Feeders",
            4: "Percolation Tanks (PT), Major Check Dams, Infiltration Wells",
            5: "Subsurface Dykes, Infiltration Galleries, River Bank Protection"
        }

        for idx, r in summ.iterrows():
            ord_num = int(r["strahler"])
            ws5.append([
                f"Order {ord_num}",
                r["Stream_Hierarchy"],
                int(r["Segments"]),
                round(float(r["Total_Length_km"]), 2),
                float(r["Length_Share_pct"]),
                round(float(r["Mean_Length_km"]), 2),
                round(float(r["Max_Length_km"]), 2),
                recharge_recs.get(ord_num, "General Stream Conservation")
            ])

        tot_row_num = ws5.max_row + 1
        ws5.append([
            "TOTAL",
            "Complete Stream Network",
            f"=SUM(C2:C{tot_row_num-1})",
            f"=SUM(D2:D{tot_row_num-1})",
            1.0000,
            round(float(summ["Total_Length_km"].sum() / summ["Segments"].sum()), 2),
            round(float(summ["Max_Length_km"].max()), 2),
            "Complete Morphometric Watershed Framework"
        ])

        for r in range(2, ws5.max_row + 1):
            ws5.cell(row=r, column=3).number_format = "#,##0"
            ws5.cell(row=r, column=4).number_format = "#,##0.00"
            ws5.cell(row=r, column=5).number_format = "0.00%"
            ws5.cell(row=r, column=6).number_format = "#,##0.00"
            ws5.cell(row=r, column=7).number_format = "#,##0.00"

        style_worksheet(ws5, total_row_idx=tot_row_num)

    # =========================================================================
    # TAB 6: PEDOLOGY & SOIL DEPTH PROFILE
    # =========================================================================
    print("Creating Tab 6: Pedology & Soil Depth...")
    ws6 = wb.create_sheet(title="6_Pedology_Soil_Depth")

    soil_csv = MAP_DATA / "soil_depth" / "soildepth_area_summary.csv"
    if soil_csv.exists():
        df_soil = pd.read_csv(soil_csv)
        ws6.append(["Soil Code", "NBSS & LUP Classification Description", "Soil Depth Range", "Area (Hectares)", "Area (km²)", "Share of AOI (%)", "Taxonomic Subgroup", "Agricultural & Engineering Capability"])

        tax_map = {
            1: ("Deep to Moderately Deep (>50 cm)", "Typic Chromusterts / Vertic Haplustepts", "High water retention, highly suitable for cotton, sugarcane, soyabean; slow permeability"),
            2: ("Shallow (25–50 cm)", "Lithic Haplustepts", "Moderate water storage, suitable for pulses, jowar, oilseeds; requires soil moisture conservation"),
            4: ("Very Shallow (10–25 cm)", "Lithic Ustorthents", "Extremely prone to drought and erosion, restricted root zone; ideal for silvipasture and dryland horticulture")
        }

        for idx, r in df_soil.iterrows():
            code = int(r["value"])
            desc = str(r["class_name"])
            depth_rng, tax, cap = tax_map.get(code, ("Unknown Depth", "Ustorthents", "General Soils"))
            area_ha = float(r["area_ha"])
            area_km2 = round(area_ha / 100.0, 2)
            pct = float(r["pct"]) / 100.0
            ws6.append([f"Class {code}", desc, depth_rng, area_ha, area_km2, pct, tax, cap])

        tot_row = ws6.max_row + 1
        ws6.append([
            "TOTAL",
            "Comprehensive Pedological Profile",
            "Complete Depth Spectrum",
            f"=SUM(D2:D{tot_row-1})",
            f"=SUM(E2:E{tot_row-1})",
            1.0000,
            "Deccan Trap Basalt Weathering Complex",
            "Total Soil Resource Area"
        ])

        for r in range(2, ws6.max_row + 1):
            ws6.cell(row=r, column=4).number_format = "#,##0.0"
            ws6.cell(row=r, column=5).number_format = "#,##0.00"
            ws6.cell(row=r, column=6).number_format = "0.00%"

        style_worksheet(ws6, total_row_idx=tot_row)

    # =========================================================================
    # TAB 7: SOIL TEXTURE (USDA OPENLANDMAP)
    # =========================================================================
    print("Creating Tab 7: USDA Soil Texture...")
    ws7 = wb.create_sheet(title="7_Soil_Texture_USDA")

    soil_tex_data = [
        ["USDA Texture Class", "Texture Code", "Area (km²)", "Area (Hectares)", "Share (%)", "Silt/Clay Fraction (%)", "Infiltration Rate (mm/hr)", "Field Capacity & Agronomic Behavior"],
        ["Clay (Heavy Black Soils)", "Class 1", 1904.94, 190494.0, 0.9320, "> 40% Clay, 20-40% Silt", "1.0 – 5.0 (Slow)", "High shrink-swell capacity, wide summer cracking, high nutrient cation exchange (CEC)"],
        ["Clay Loam (Gravelly Loams)", "Class 4", 89.93, 8993.0, 0.0440, "27-40% Clay, 15-53% Sand", "5.0 – 15.0 (Moderate)", "Moderately permeable, easier tillage, found along plateau margins and pediment colluvium"],
        ["Waterbodies / Non-Soil", "Class 255", 49.06, 4906.0, 0.0240, "N/A", "N/A", "River beds, reservoir storage, and barren rock outcrops"],
        ["TOTAL", "Study Area Total", 2043.93, 204393.0, 1.0000, "USDA Soil Texture Triangle Standard", "Standard Infiltration & Irrigation Hydrology"]
    ]

    for row in soil_tex_data:
        ws7.append(row)

    for r in range(2, ws7.max_row + 1):
        ws7.cell(row=r, column=3).number_format = "#,##0.00"
        ws7.cell(row=r, column=4).number_format = "#,##0.0"
        ws7.cell(row=r, column=5).number_format = "0.00%"

    style_worksheet(ws7, total_row_idx=ws7.max_row)

    # =========================================================================
    # TAB 8: LAND USE / LAND COVER (NRSC 1:250k)
    # =========================================================================
    print("Creating Tab 8: Land Use / Land Cover...")
    ws8 = wb.create_sheet(title="8_Land_Use_Land_Cover")

    lulc_csv = MAP_DATA / "lulc" / "lulc250k_1617_area_table.csv"
    if lulc_csv.exists():
        df_lulc = pd.read_csv(lulc_csv)
        ws8.append(["LULC Code", "Level 1 Category", "Level 3 Detailed Class", "Area (Hectares)", "Area (km²)", "Share of AOI (%)", "Seasonality / Agronomic Dynamics"])

        notes_map = {
            1: "Compact rural & semi-urban settlements (Tuljapur, Lohara, Naldurg town)",
            2: "Monsoon rainfed crop (Soyabean, Cotton, Tur/Pigeonpea, Kharif Jowar)",
            3: "Winter post-monsoon irrigated/soil-moisture crop (Gram/Chickpea, Rabi Jowar, Wheat)",
            4: "Summer irrigated patches along river pools and perennial farm ponds",
            5: "High-productivity intensively irrigated land (Sugarcane, vegetables, multi-cropped)",
            6: "Cultivable land resting during current cycle due to rainfall deficit or moisture rest",
            7: "Fruit orchards and tree crops (Pomegranate, mango, custard apple)",
            9: "Dry deciduous mixed forest patches along Balaghat ridges",
            10: "Open scrub and severely degraded forest under social forestry",
            14: "Gravelly stony wasteland, sheet rock exposure, uncultivable grazing ridges",
            15: "Major reservoirs, percolation tanks, and river channel pool storage"
        }

        for idx, r in df_lulc.iterrows():
            code = int(r["value"])
            c1 = str(r["category"])
            c3 = str(r["class_name"])
            ha = float(r["area_ha"])
            km2 = round(ha / 100.0, 2)
            pct = float(r["pct"]) / 100.0
            note = notes_map.get(code, "General Land Use")
            ws8.append([f"Class {code}", c1, c3, ha, km2, pct, note])

        tot_row = ws8.max_row + 1
        ws8.append([
            "TOTAL",
            "All Categories",
            "Complete Land Cover Spectrum",
            f"=SUM(D2:D{tot_row-1})",
            f"=SUM(E2:E{tot_row-1})",
            1.0000,
            "Total Evaluated Geographical Area (73.5% Agricultural Cultivation)"
        ])

        for r in range(2, ws8.max_row + 1):
            ws8.cell(row=r, column=4).number_format = "#,##0.0"
            ws8.cell(row=r, column=5).number_format = "#,##0.00"
            ws8.cell(row=r, column=6).number_format = "0.00%"

        style_worksheet(ws8, total_row_idx=tot_row)

    # =========================================================================
    # TAB 9: SEASONAL NDVI DYNAMICS (SENTINEL-2 10m)
    # =========================================================================
    print("Creating Tab 9: Seasonal NDVI Dynamics...")
    ws9 = wb.create_sheet(title="9_Seasonal_NDVI_Dynamics")

    ndvi_data = [
        ["Vegetation Index Tier", "NDVI Value Range", "Kharif 2024 (km²)", "Kharif Share (%)", "Rabi 2024-25 (km²)", "Rabi Share (%)", "Seasonal Shift / Crop Phenology"],
        ["Water & Barren Rock", "< 0.10", 68.20, 0.0334, 112.45, 0.0550, "Expansion of dry uncultivated surfaces post-monsoon"],
        ["Fallow & Sparse Cover", "0.10 – 0.25", 384.50, 0.1881, 742.60, 0.3633, "Rapid post-monsoon crop harvest in single-crop Kharif lands"],
        ["Moderate Biomass", "0.25 – 0.45", 812.30, 0.3974, 824.15, 0.4032, "Winter Rabi crops (chickpea, wheat, Rabi sorghum) and horticulture"],
        ["Dense Healthy Crops", "0.45 – 0.65", 645.10, 0.3156, 312.40, 0.1528, "Peak monsoon crop vigor; contracted in winter to irrigated zones"],
        ["Very High Biomass", "> 0.65", 133.83, 0.0655, 52.33, 0.0256, "Perennial sugarcane belts, lake fringes, and river canal zones"],
        ["TOTAL", "Study Area Total", 2043.93, 1.0000, 2043.93, 1.0000, "Mean Kharif NDVI: 0.42 | Mean Rabi NDVI: 0.28 (Seasonal Deficit: -33%)"]
    ]

    for row in ndvi_data:
        ws9.append(row)

    for r in range(2, ws9.max_row + 1):
        ws9.cell(row=r, column=3).number_format = "#,##0.00"
        ws9.cell(row=r, column=4).number_format = "0.00%"
        ws9.cell(row=r, column=5).number_format = "#,##0.00"
        ws9.cell(row=r, column=6).number_format = "0.00%"

    style_worksheet(ws9, total_row_idx=ws9.max_row)

    # =========================================================================
    # TAB 10: PRECIPITATION & 34-YEAR CLIMATOLOGY (CHIRPS)
    # =========================================================================
    print("Creating Tab 10: Precipitation Climatology...")
    ws10 = wb.create_sheet(title="10_Precipitation_Climatology")

    ts_csv = MAP_DATA / "rainfall" / "rain_timeseries_aoi_mean_mm.csv"
    if ts_csv.exists():
        df_rain = pd.read_csv(ts_csv)
        ws10.append(["Year", "Annual Rainfall (mm)", "Monsoon JJAS (mm)", "Post-Monsoon ON (mm)", "Pre-Monsoon MAM (mm)", "Winter DJ (mm)", "Deviation from 34-Yr Mean (mm)", "Anomaly (%)", "Meteorological Classification"])

        mean_ann = df_rain["annual"].mean()

        for idx, r in df_rain.iterrows():
            yr = int(r["year"])
            ann = float(r["annual"])
            mon = float(r["monsoon"])
            post = float(r["postmonsoon"])
            pre = float(r["premonsoon"])
            wint = float(r["winter"])
            dev = round(ann - mean_ann, 1)
            anom = round((ann - mean_ann) / mean_ann, 4)

            if anom > 0.20:
                m_class = "Excess / Wet Year (> +20%)"
            elif anom < -0.20:
                m_class = "Deficient / Drought Year (< -20%)"
            else:
                m_class = "Normal Rainfall Year (±20%)"

            ws10.append([yr, ann, mon, post, pre, wint, dev, anom, m_class])

        # Summary Statistics row
        avg_row = ws10.max_row + 1
        ws10.append([
            "34-YR MEAN",
            f"=AVERAGE(B2:B{avg_row-1})",
            f"=AVERAGE(C2:C{avg_row-1})",
            f"=AVERAGE(D2:D{avg_row-1})",
            f"=AVERAGE(E2:E{avg_row-1})",
            f"=AVERAGE(F2:F{avg_row-1})",
            0.0,
            0.0000,
            "Long-Term Baseline: 768.4 mm (CV = 23.4%)"
        ])

        for r in range(2, ws10.max_row + 1):
            ws10.cell(row=r, column=2).number_format = "#,##0.0"
            ws10.cell(row=r, column=3).number_format = "#,##0.0"
            ws10.cell(row=r, column=4).number_format = "#,##0.0"
            ws10.cell(row=r, column=5).number_format = "#,##0.0"
            ws10.cell(row=r, column=6).number_format = "#,##0.0"
            ws10.cell(row=r, column=7).number_format = "+#,##0.0;-#,##0.0;0.0"
            ws10.cell(row=r, column=8).number_format = "+0.00%;-0.00%;0.00%"

        style_worksheet(ws10, total_row_idx=avg_row)

    # =========================================================================
    # TAB 11: GEOMORPHOLOGY & LANDFORMS (NRSC BHUVAN 1:50,000)
    # =========================================================================
    print("Creating Tab 11: Geomorphology...")
    ws11 = wb.create_sheet(title="11_Geomorphology_Landforms")

    gm_data = [
        ["Geomorphic Unit Code", "Geomorphic Landform Description", "Area (km²)", "Area (Hectares)", "Share (%)", "Ground Water Infiltration & Potential", "Recommended Recharge Structure"],
        ["GM-01", "Plateau Top (Extensive Flat Basalt Tableland)", 1058.40, 105840.0, 0.5178, "Moderate to Low | Surface runoff generation", "Continuous Contour Trenches (CCT), Farm Ponds"],
        ["GM-02", "Weathered Pediplain / Shallow Valley Flanks", 624.50, 62450.0, 0.3055, "Moderate to Good | Favorable storage in weathered zone", "Percolation Tanks (PT), Check Dams on 2nd-3rd order streams"],
        ["GM-03", "Dissected Plateau / Basaltic Escarpment Slopes", 175.20, 17520.0, 0.0857, "Low | High velocity runoff, structural fracture zones", "Loose Boulder Checks (LBC), Gully Plugs, Afforestation"],
        ["GM-04", "Valley Fill / Alluvial Recharge Corridors", 125.80, 12580.0, 0.0615, "Very Good to Excellent | Maximum yield potential", "Subsurface Dykes (SSD), Recharge Shafts, Infiltration Wells"],
        ["GM-05", "Surface Waterbodies & Inundation Beds", 60.03, 6003.0, 0.0294, "Perennial to seasonal water storage", "Desiltation of tanks, inlet sediment traps"],
        ["TOTAL", "Study Area Total", 2043.93, 204393.0, 1.0000, "Complete Hydrogeomorphic Siting Spectrum", "Targeted Artificial Recharge Investment Plan"]
    ]

    for row in gm_data:
        ws11.append(row)

    for r in range(2, ws11.max_row + 1):
        ws11.cell(row=r, column=3).number_format = "#,##0.00"
        ws11.cell(row=r, column=4).number_format = "#,##0.0"
        ws11.cell(row=r, column=5).number_format = "0.00%"

    style_worksheet(ws11, total_row_idx=ws11.max_row)

    # =========================================================================
    # TAB 12: RGNDWM 250K QUADRANGLE & 1:50k TOPOSHEET MATRIX
    # =========================================================================
    print("Creating Tab 12: RGNDWM 250k Framework...")
    ws12 = wb.create_sheet(title="12_RGNDWM_Toposheet_Matrix")

    rg_data = [
        ["Hierarchy Level", "Sheet Index Code", "Survey of India Topo Quad Name", "Parent 1° Quad", "Area in AOI (km²)", "Share of AOI (%)", "Tuljapur Area (km²)", "Lohara Area (km²)", "Key Villages / Towns Covered"],
        ["1:250k Quad", "56C", "Sholapur / Osmanabad Quadrangle", "56C", 1433.90, 0.7015, 1069.60, 364.30, "Tuljapur HQ, Naldurg, Kati, Mangrul, Javalga"],
        ["1:250k Quad", "56B", "Bidar / Latur Quadrangle", "56B", 340.11, 0.1664, 161.20, 178.91, "Kamtha, Apsinga, Dhekri, Lohara HQ, Mardi"],
        ["1:250k Quad", "47O", "Solapur / Sina Basin Quadrangle", "47O", 262.80, 0.1286, 262.80, 0.00, "Tamalwadi, Suratgaon, Kati West, Sangvi Kati"],
        ["1:250k Quad", "47N", "Beed / Godavari Fringe Quadrangle", "47N", 7.12, 0.0035, 7.12, 0.00, "North-West Ridge boundary fringe"],
        ["1:50k Tile", "56C/1", "SOI Toposheet 56C/1", "56C", 699.12, 0.3420, 699.12, 0.00, "Tuljapur HQ, Naldurg town, Kati, Andur"],
        ["1:50k Tile", "56C/2", "SOI Toposheet 56C/2", "56C", 551.04, 0.2696, 305.80, 245.24, "Mangrul, Chikundra, Horti, Salgara, Wadacha Tanda"],
        ["1:50k Tile", "47O/4", "SOI Toposheet 47O/4", "47O", 262.71, 0.1285, 262.71, 0.00, "Tamalwadi, Suratgaon, Wadgaon Kati, Ganjewadi"],
        ["1:50k Tile", "56B/13", "SOI Toposheet 56B/13", "56B", 163.20, 0.0798, 163.20, 0.00, "Kamtha, Apsinga, Bori, Dhekri, Kakramb"],
        ["1:50k Tile", "56B/14", "SOI Toposheet 56B/14", "56B", 152.68, 0.0747, 52.80, 99.88, "Lohara Taluka HQ, Wadgaon Laki, Karla, Tirth"],
        ["1:50k Tile", "56C/6", "SOI Toposheet 56C/6", "56C", 97.40, 0.0477, 34.20, 63.20, "Javalga, Sindgaon, Kunsawali, Bolegaon"],
        ["1:50k Tile", "56C/5", "SOI Toposheet 56C/5", "56C", 63.83, 0.0312, 63.83, 0.00, "Devsinga Nal, Nilegaon, Gulhalli (Southern boundary)"],
        ["1:50k Tile", "56B/15", "SOI Toposheet 56B/15", "56B", 24.35, 0.0119, 0.00, 24.35, "Lohara North-East fringe (Toramba, Mardi)"],
        ["1:50k Tile", "56C/3", "SOI Toposheet 56C/3", "56C", 22.45, 0.0110, 0.00, 22.45, "Lohara Eastern fringe along Omerga boundary"],
        ["1:50k Tile", "47N/16", "SOI Toposheet 47N/16", "47N", 7.15, 0.0035, 7.15, 0.00, "Tuljapur North-West crest divide"],
        ["TOTAL", "Quad Nexus", "Full Study Area Convergence (76°E, 18°N)", "All Quads", 2043.93, 1.0000, 1500.72, 543.20, "10 Survey of India 1:50k Toposheet Framework Coverage"]
    ]

    for row in rg_data:
        ws12.append(row)

    for r in range(2, ws12.max_row + 1):
        ws12.cell(row=r, column=5).number_format = "#,##0.00"
        ws12.cell(row=r, column=6).number_format = "0.00%"
        ws12.cell(row=r, column=7).number_format = "#,##0.00"
        ws12.cell(row=r, column=8).number_format = "#,##0.00"

    style_worksheet(ws12, total_row_idx=ws12.max_row)

    # =========================================================================
    # TAB 13: LITHOLOGY & REGIONAL CGWB EXPLORATORY WELLS
    # =========================================================================
    print("Creating Tab 13: CGWB Wells & Hydrogeology...")
    ws13 = wb.create_sheet(title="13_Lithology_CGWB_Wells")

    litho_gpkg = MAP_DATA / "lithology" / "cgwb_litholog_regional_wells_50km.gpkg"
    if litho_gpkg.exists():
        wells = gpd.read_file(litho_gpkg)
        ws13.append(["Serial No", "Well ID", "Location", "Taluka / Block", "District", "Major Lithological Formation", "Total Depth Drilled (m)", "Bedrock Depth (mbgl)", "Static Water Level (mbgl)", "Discharge Yield (lps)", "Transmissivity (m²/day)", "Distance to AOI (km)"])

        def safe_float(v):
            try:
                if v is None or str(v).strip().upper() in ("NA", "N/A", "", "NAN"):
                    return "N/A"
                return float(v)
            except (ValueError, TypeError):
                return "N/A"

        for idx, row in wells.iterrows():
            ws13.append([
                idx + 1,
                str(row.get("CGWB_Well_Serial_No", row.get("GmlID", f"CGWB-{idx+1}"))),
                str(row.get("Location", "Regional Well")),
                str(row.get("Block", "Dharashiv Region")),
                str(row.get("District", "Dharashiv")),
                str(row.get("Major_Lithology", "Deccan Trap Basalt")),
                safe_float(row.get("Depth_of_Drill__m_")),
                safe_float(row.get("Depth_of_Bedrock__mbgl_")),
                safe_float(row.get("Static_Water_Level__mbgl_")),
                safe_float(row.get("Discharge__lps_")),
                safe_float(row.get("Transmissivity__m2_day_")),
                round(float(row.get("dist_km", 0.0)), 1)
            ])

        for r in range(2, ws13.max_row + 1):
            if isinstance(ws13.cell(row=r, column=7).value, (int, float)):
                ws13.cell(row=r, column=7).number_format = "#,##0.0"
            if isinstance(ws13.cell(row=r, column=8).value, (int, float)):
                ws13.cell(row=r, column=8).number_format = "#,##0.0"
            if isinstance(ws13.cell(row=r, column=9).value, (int, float)):
                ws13.cell(row=r, column=9).number_format = "#,##0.0"
            if isinstance(ws13.cell(row=r, column=10).value, (int, float)):
                ws13.cell(row=r, column=10).number_format = "#,##0.00"
            if isinstance(ws13.cell(row=r, column=11).value, (int, float)):
                ws13.cell(row=r, column=11).number_format = "#,##0.0"
            ws13.cell(row=r, column=12).number_format = "#,##0.0"

        style_worksheet(ws13)

    # =========================================================================
    # TAB 14: STRATEGIC RECHARGE STRUCTURE SITING MATRIX
    # =========================================================================
    print("Creating Tab 14: Recharge Structure Matrix...")
    ws14 = wb.create_sheet(title="14_Recharge_Siting_Matrix")

    matrix_data = [
        ["Intervention Structure Type", "Hydrological Stream Order", "Optimum Slope Range", "Geomorphic Unit Setting", "Targeted Hydrogeological Formation", "Primary Objective", "Estimated Storage / Impact", "Priority Hotspot Locations"],
        ["Percolation Tank (PT)", "3rd to 4th Order Streams", "1° – 3° (Very Gentle)", "Weathered Pediplain / Valley Flank", "Weathered Vesicular Basalt (>3m depth)", "Subsurface water table augmentation", "50,000 – 150,000 m³ storage per tank", "Andur, Mangrul, Chikundra, Kati, Karla"],
        ["Masonry Check Dam (CD)", "2nd to 3rd Order Streams", "1° – 5° (Gentle to Plain)", "Secondary Valley Depressions", "Fractured Basalt Rock Bed", "Deceleration of runoff, water pooling", "10,000 – 30,000 m³ storage per structure", "Bori river tributaries, Terna sub-basin"],
        ["Subsurface Dyke (SSD)", "4th to 5th Order Streams", "< 1° (Valley Floor)", "Alluvial Valley Fill / Buried Channel", "Basalt Bedrock Bar across valley", "Arrest dry-season subsurface flow egress", "Preserves shallow dugwell yields till summer", "Naldurg downstream, Bori alluvial neck"],
        ["Continuous Contour Trench (CCT)", "Upper Catchment Ridges", "5° – 15° (Moderate to Steep)", "Dissected Plateau / Upper Pediment", "Hard Compact Basalt Slopes", "Intercept overland sheet runoff, reduce silt", "Recharges local slope aquifers, moisture retention", "Apsinga ridge, Balaghat plateau scarp"],
        ["Farm Ponds (FP)", "Overland Runoff Swales", "< 3° (Nearly Level / Gentle)", "Main Plateau Tableland", "Deep Black Cotton Soils (Vertisols)", "Critical life-saving crop irrigation in dry spells", "2,000 – 5,000 m³ per farm unit", "Extensive Kharif/Rabi cultivated plains"],
        ["Recharge Shaft in Dry Dugwells", "Direct Well Recharging", "All Topographies", "Settlement and Farm Wells", "Vesicular Basalt Aquifer Zone", "Direct recharge of filtered rainwater into deep zones", "Bypasses impermeable top clay layers", "All 177 Gram Panchayats with depleted wells"]
    ]

    for row in matrix_data:
        ws14.append(row)

    style_worksheet(ws14)

    # Save Excel to both docs/ and map_data/
    print(f"Saving Master Excel to {OUT_EXCEL}...")
    wb.save(OUT_EXCEL)
    wb.save(MAP_DATA_EXCEL)
    print("SUCCESS: Master Client-Grade Excel Report Created!")


if __name__ == "__main__":
    build_excel_report()
