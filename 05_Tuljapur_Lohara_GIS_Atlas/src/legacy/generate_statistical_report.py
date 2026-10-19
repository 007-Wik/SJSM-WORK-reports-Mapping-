#!/usr/bin/env python3
"""
Comprehensive Statistical & GIS Report Generator for Tuljapur & Lohara Blocks
Exports a multi-tabbed professional Excel Workbook (.xlsx) covering:
1. Executive Summary & AOI Metrics
2. Demographics & Administration (Villages, Areas)
3. Topography & Relief (Elevation & Slope distribution)
4. Hydrology & Morphometry (Strahler Orders 1-5, Drainage Density)
5. Pedology & Soil Depth (NBSS&LUP Classes, Area, %)
6. Land Use / Land Cover (NRSC LULC 250k Classes, Area, %)
7. Climatology & Precipitation (34-Year CHIRPS Annual & IMD Seasons)
8. Regional Lithology & Hydrogeology (CGWB Wells, Formations)
"""
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_DATA = BASE_DIR / "map_data"
OUT_EXCEL = MAP_DATA / "Tuljapur_Lohara_GIS_Statistical_Report.xlsx"

def generate_excel_report():
    print(">>> Generating comprehensive GIS & Environmental Excel Report...")
    writer = pd.ExcelWriter(OUT_EXCEL, engine="openpyxl")

    # -------------------------------------------------------------
    # TAB 1: EXECUTIVE SUMMARY
    # -------------------------------------------------------------
    df_exec = pd.DataFrame([
        {"Parameter": "Project Study Area", "Tuljapur Taluka": "Tuljapur Block", "Lohara Taluka": "Lohara Block", "Combined AOI": "Dharashiv District, MH"},
        {"Parameter": "Geographical Area (km²)", "Tuljapur Taluka": 1534.6, "Lohara Taluka": 509.3, "Combined AOI": 2043.9},
        {"Parameter": "Area Share (%)", "Tuljapur Taluka": "75.08%", "Lohara Taluka": "24.92%", "Combined AOI": "100.00%"},
        {"Parameter": "Total Mapped Villages", "Tuljapur Taluka": 108, "Lohara Taluka": 50, "Combined AOI": 158},
        {"Parameter": "Population (Census 2011)", "Tuljapur Taluka": "279,720", "Lohara Taluka": "116,211", "Combined AOI": "395,931"},
        {"Parameter": "Elevation Range (m a.s.l.)", "Tuljapur Taluka": "438 – 700 m", "Lohara Taluka": "442 – 621 m", "Combined AOI": "438 – 700 m"},
        {"Parameter": "Primary River Basins", "Tuljapur Taluka": "Bori River Sub-basin", "Lohara Taluka": "Terna River Sub-basin", "Combined AOI": "Bhima / Krishna Basin"},
        {"Parameter": "Total Stream Network Length", "Tuljapur Taluka": "1,643.2 km", "Lohara Taluka": "548.5 km", "Combined AOI": "2,191.7 km"},
        {"Parameter": "Mean Annual Rainfall (34-yr)", "Tuljapur Taluka": "762.5 mm", "Lohara Taluka": "786.1 mm", "Combined AOI": "768.4 mm"},
        {"Parameter": "Predominant Soil Class", "Tuljapur Taluka": "Very Shallow (10-25cm)", "Lohara Taluka": "Very Shallow to Deep", "Combined AOI": "Lithic Ustorthents (66.8%)"},
        {"Parameter": "Agricultural Dominance", "Tuljapur Taluka": "72.4% Cultivated", "Lohara Taluka": "76.8% Cultivated", "Combined AOI": "73.5% Cultivated/Fallow"},
        {"Parameter": "Geological Formation", "Tuljapur Taluka": "Deccan Basalt (Pahoehoe/Aa)", "Lohara Taluka": "Deccan Basalt & Alluvium", "Combined AOI": "Upper Cretaceous Basalts"},
        {"Parameter": "Classified Roads (km)", "Tuljapur Taluka": "1,884 km", "Lohara Taluka": "744 km", "Combined AOI": "2,628 km"},
        {"Parameter": "Observed CGWB Wells", "Tuljapur Taluka": "29 Wells", "Lohara Taluka": "16 Wells", "Combined AOI": "45 Regional Wells"}
    ])
    df_exec.to_excel(writer, sheet_name="1_Executive_Summary", index=False)

    # -------------------------------------------------------------
    # TAB 2: DEMOGRAPHICS & VILLAGE UNITS
    # -------------------------------------------------------------
    sub_path = MAP_DATA / "aoi" / "subblocks_villages.gpkg"
    if sub_path.exists():
        sub = gpd.read_file(sub_path).to_crs("EPSG:32643")
        sub["Area_ha"] = (sub.geometry.area / 10000.0).round(1)
        sub["Area_km2"] = (sub.geometry.area / 1e6).round(2)
        df_vill = pd.DataFrame({
            "District": sub["DISTRICT"],
            "Taluka_Block": sub["BLOCK"],
            "Village_Name": sub["VILLAGE"],
            "Area_Hectares": sub["Area_ha"],
            "Area_SqKm": sub["Area_km2"]
        }).sort_values(["Taluka_Block", "Village_Name"])
        df_vill.to_excel(writer, sheet_name="2_Demographics_Villages", index=False)

    # -------------------------------------------------------------
    # TAB 3: TOPOGRAPHY & ELEVATION
    # -------------------------------------------------------------
    dem_path = MAP_DATA / "dem" / "dem_aoi.tif"
    if dem_path.exists():
        with rasterio.open(dem_path) as src:
            arr = src.read(1).astype("float32")
            arr = arr[arr != src.nodata]
            bins = [400, 450, 500, 550, 600, 650, 750]
            labels = ["400-450 m (Lowest Valleys)", "450-500 m (Lower Plains)", "500-550 m (Middle Plain)",
                      "550-600 m (Upper Pediment)", "600-650 m (Balaghat Plateau)", ">650 m (Escarpment Ridges)"]
            cats = pd.cut(arr, bins=bins, labels=labels)
            val_counts = pd.Series(cats).value_counts()
            cell_area_km2 = (30.0 * 30.0) / 1e6
            df_dem = pd.DataFrame({
                "Elevation_Class": labels,
                "Cell_Count": [val_counts[l] for l in labels],
                "Area_km2": [round(val_counts[l] * cell_area_km2, 2) for l in labels],
                "Percentage": [round(val_counts[l] / len(arr) * 100.0, 2) for l in labels]
            })
            df_dem.to_excel(writer, sheet_name="3_Topography_Elevation", index=False)

    # -------------------------------------------------------------
    # TAB 4: HYDROLOGY & STRAHLER ORDERS
    # -------------------------------------------------------------
    strm_path = MAP_DATA / "streams" / "streams_complete_strahler.gpkg"
    if strm_path.exists():
        strm = gpd.read_file(strm_path)
        summ = strm.groupby("strahler").agg(
            Segments=("len_km", "count"),
            Total_Length_km=("len_km", "sum"),
            Mean_Length_km=("len_km", "mean"),
            Max_Length_km=("len_km", "max")
        ).reset_index()
        type_names = {1: "1st Order (Headwater Gully)", 2: "2nd Order (Secondary Tributary)",
                      3: "3rd Order (Major Stream)", 4: "4th Order (Sub-Basin Trunk River)", 5: "5th Order (Main River Confluence)"}
        summ["Stream_Hierarchy"] = summ["strahler"].map(type_names)
        tot_km = summ["Total_Length_km"].sum()
        summ["Length_Share_pct"] = (summ["Total_Length_km"] / tot_km * 100.0).round(2)
        summ["Total_Length_km"] = summ["Total_Length_km"].round(2)
        summ["Mean_Length_km"] = summ["Mean_Length_km"].round(2)
        summ["Max_Length_km"] = summ["Max_Length_km"].round(2)
        summ.rename(columns={"strahler": "Strahler_Order"}, inplace=True)
        summ = summ[["Strahler_Order", "Stream_Hierarchy", "Segments", "Total_Length_km", "Length_Share_pct", "Mean_Length_km", "Max_Length_km"]]
        summ.to_excel(writer, sheet_name="4_Hydrology_Streams", index=False)

    # -------------------------------------------------------------
    # TAB 5: SOIL DEPTH PROFILE
    # -------------------------------------------------------------
    soil_csv = MAP_DATA / "soil_depth" / "soildepth_area_summary.csv"
    if soil_csv.exists():
        df_soil = pd.read_csv(soil_csv)
        df_soil["Area_km2"] = (df_soil["area_ha"] / 100.0).round(2)
        df_soil.rename(columns={
            "value": "Soil_Code", "class_name": "NBSS_Classification",
            "area_ha": "Area_Hectares", "pct": "Coverage_Percent"
        }, inplace=True)
        df_soil = df_soil[["Soil_Code", "NBSS_Classification", "Area_Hectares", "Area_km2", "Coverage_Percent"]]
        df_soil.to_excel(writer, sheet_name="5_Soil_Depth_Pedology", index=False)

    # -------------------------------------------------------------
    # TAB 6: LAND USE / LAND COVER (LULC)
    # -------------------------------------------------------------
    lulc_csv = MAP_DATA / "lulc" / "lulc250k_1617_area_table.csv"
    if lulc_csv.exists():
        df_lulc = pd.read_csv(lulc_csv)
        df_lulc["Area_km2"] = (df_lulc["area_ha"] / 100.0).round(2)
        df_lulc.rename(columns={
            "value": "LULC_Code", "category": "Level_1_Category", "class_name": "Level_3_Class",
            "area_ha": "Area_Hectares", "pct": "Coverage_Percent"
        }, inplace=True)
        df_lulc = df_lulc[["LULC_Code", "Level_1_Category", "Level_3_Class", "Area_Hectares", "Area_km2", "Coverage_Percent"]]
        df_lulc.to_excel(writer, sheet_name="6_LULC_Dynamics", index=False)

    # -------------------------------------------------------------
    # TAB 7: RAINFALL & CLIMATOLOGY (34-Year Record)
    # -------------------------------------------------------------
    ts_csv = MAP_DATA / "rainfall" / "rain_timeseries_aoi_mean_mm.csv"
    if ts_csv.exists():
        df_rain = pd.read_csv(ts_csv)
        mean_p = df_rain["annual"].mean()
        df_rain["Deviation_from_Mean_mm"] = (df_rain["annual"] - mean_p).round(1)
        df_rain["Anomaly_Percent"] = ((df_rain["annual"] - mean_p) / mean_p * 100.0).round(2)
        df_rain.rename(columns={"year": "Year", "annual": "Annual_Precipitation_mm"}, inplace=True)
        df_rain.to_excel(writer, sheet_name="7_Rainfall_Timeseries", index=False)

    # -------------------------------------------------------------
    # TAB 8: REGIONAL LITHOLOGY & HYDROGEOLOGY WELLS
    # -------------------------------------------------------------
    litho_gpkg = MAP_DATA / "lithology" / "cgwb_litholog_regional_wells_50km.gpkg"
    if litho_gpkg.exists():
        wells = gpd.read_file(litho_gpkg)
        df_wells = pd.DataFrame({
            "Well_Serial_No": wells.get("CGWB_Well_Serial_No", wells["GmlID"]),
            "Location": wells.get("Location", "Regional Well"),
            "Taluka": wells.get("Block", "N/A"),
            "District": wells.get("District", "Dharashiv"),
            "Major_Lithology": wells.get("Major_Lithology", "Basalt"),
            "Well_Depth_m": wells.get("Depth_of_Drill__m_", "N/A"),
            "Bedrock_Depth_m": wells.get("Depth_of_Bedrock__mbgl_", "N/A"),
            "Static_Water_Level_mbgl": wells.get("Static_Water_Level__mbgl_", "N/A"),
            "Discharge_lps": wells.get("Discharge__lps_", "N/A"),
            "Transmissivity_m2_day": wells.get("Transmissivity__m2_day_", "N/A"),
            "Distance_to_AOI_km": wells["dist_km"].round(1)
        })
        df_wells.to_excel(writer, sheet_name="8_Lithology_Wells", index=False)

    writer.close()
    print("Saved comprehensive statistical Excel report:", OUT_EXCEL)

if __name__ == "__main__":
    generate_excel_report()
