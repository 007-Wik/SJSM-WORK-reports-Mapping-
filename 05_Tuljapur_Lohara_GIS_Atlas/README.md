# Dharashiv District GIS & Environmental Atlas (Tuljapur & Lohara Talukas)
**Comprehensive Multi-Thematic GIS Analysis, Cartographic Atlas, and Artificial Recharge Planning**

**Prepared for:** Shramjivi Janata Sahayak Mandal (SJSM)  
**Total Geographical Coverage:** ~2,043.9 km² across 177 Cadastral Villages (Tuljapur: 1,500.7 km², Lohara: 543.2 km²)  

---

## 🎯 FINAL CLIENT DELIVERABLES

| Deliverable Asset | Location / File | Description |
|---|---|---|
| **⭐ Master Environmental Atlas Bundle** | [`deliverables.zip`](./deliverables.zip) | **Comprehensive 246 MB archive** containing all high-resolution 300 DPI thematic cartographic maps across all 16 themes. |
| **⭐ Tuljapur Block Comprehensive Report** | [`deliverables/Tuljapur_Block_Comprehensive_GIS_Environmental_Report.xlsx`](./deliverables/Tuljapur_Block_Comprehensive_GIS_Environmental_Report.xlsx) | Dedicated 14-tab analytical workbook covering 130 villages in Tuljapur Taluka. |
| **⭐ Lohara Block Comprehensive Report** | [`deliverables/Lohara_Block_Comprehensive_GIS_Environmental_Report.xlsx`](./deliverables/Lohara_Block_Comprehensive_GIS_Environmental_Report.xlsx) | Dedicated 14-tab analytical workbook covering 47 villages in Lohara Taluka. |
| **⭐ Thematic Cartographic Map Sheets** | [`deliverables/`](./deliverables/) | 300 DPI transparent-legend thematic maps for DEM, slope, stream order, drainage density, LULC, soil depth, roads, climate, and seasonal NDVI. |
| **Consulting Invoices** | [`Invoice_SJSM_GIS_Mapping_2026.pdf`](./Invoice_SJSM_GIS_Mapping_2026.pdf) & [`.docx`](./Invoice_SJSM_GIS_Mapping_2026.docx) | Formal billing and scope of work sign-off documentation. |

---

## 1. Executive Overview
This repository contains the end-to-end GIS pipeline, spatial processing engine, and publishing framework for **Tuljapur** (1,500.7 km²) and **Lohara** (543.2 km²) Talukas in Dharashiv (formerly Osmanabad) District, Maharashtra.

The project encompasses **16 comprehensive environmental and hydrogeological themes**, delivering client-ready 300 DPI cartographic maps with transparent legends, block-specific Excel reports, and a consulting-grade Word Atlas Report.

---

## 2. Standardized Directory Layout
```
05_Tuljapur_Lohara_GIS_Atlas/
├── deliverables\                               # Final client-facing assets ONLY
│   ├── maps\                                   # 300 DPI Transparent-Legend Cartographic Maps
│   │   ├── Tuljapur\                           # 16 thematic block maps for Tuljapur Taluka
│   │   ├── Lohara\                             # 16 thematic block maps for Lohara Taluka
│   │   └── AOI_RGNDWM_250k_..._Map.png         # Master Regional RGNDWM 250k Quadrangle Map
│   ├── excels\                                 # Comprehensive multi-tab Excel workbooks
│   │   ├── Tuljapur_Block_..._Report.xlsx      # Dedicated 14-tab workbook for Tuljapur (130 villages)
│   │   ├── Lohara_Block_..._Report.xlsx        # Dedicated 14-tab workbook for Lohara (47 villages)
│   │   └── Tuljapur_Lohara_..._Report.xlsx     # Comparative master workbook
│   └── reports\                                # Publishing-grade Consulting Word Reports (.docx)
│       └── Tuljapur_Lohara_..._Atlas_Report.docx
│
├── data\                                       # Geospatial layers & inputs
│   ├── raw\                                    # Raw cadastral boundaries, DEM archives, zip packages
│   └── processed\                              # Hydrologically conditioned GeoPackages and GeoTIFFs
│
├── src\                                        # Standardized 5-Stage Production Pipeline
│   ├── 01_data_download.py                     # Stage 01: Ingestion & AOI extraction (177 villages)
│   ├── 02_gis_analysis.py                      # Stage 02: Spatial processing & layer verification
│   ├── 03_cartographic_maps.py                 # Stage 03: 300 DPI transparent-legend map generation (16 themes)
│   ├── 04_excel_reports.py                     # Stage 04: Dedicated multi-tab client Excel generation
│   ├── 05_word_report.py                       # Stage 05: Client consulting Word Atlas compilation
│   ├── run_pipeline.py                         # Master CLI orchestrator with flags & logging
│   └── legacy\                                 # Archived prototype & intermediate scripts
│
├── docs\                                       # Project documentation & guidelines
├── logs\                                       # Timestamped execution logs (pipeline.log)
├── requirements.txt                            # Python environment dependencies
└── setup_env.bat                               # Automated Conda/Python environment setup script
```

---

## 3. The 16 Standardized Environmental Themes
Both Tuljapur and Lohara Talukas are mapped across 16 synchronized thematic layers:

| Layer # | Thematic Layer | Resolution / Scale | Primary Data Source |
|:---:|:---|:---:|:---|
| **01** | Study Area & Cadastral Village Boundaries | 1:50,000 | Survey of India / Cadastral |
| **02** | 10m High-Resolution Topographic Contours | 10 m interval | Copernicus GLO-30 DEM |
| **03** | Annual Land Use / Land Cover (LULC) | 10 m | Esri / Impact Observatory |
| **04** | Soil Depth Classification | 1:250,000 | NBSS&LUP / ICAR |
| **05** | Transportation & Road Network | Vector (OSM) | OpenStreetMap (ODbL) |
| **06** | Annual Precipitation & 10mm Isohyets | 5 km gridded | IMD / CHIRPS Climatology |
| **07** | Basalt Lithology & Regional CGWB Wells | 1:250,000 / Wells | CGWB / GSI Quadrangle |
| **08** | Digital Elevation Model (DEM) & Relief | 30 m | Copernicus DEM GLO-30 |
| **09** | Administrative Village Cadastral Map | 177 units | Government of Maharashtra |
| **10** | Topographic Slope Classification (%) | 30 m | Horn Algorithm (Copernicus DEM) |
| **11** | Strahler Drainage Network (Orders 1–5) | D8 extraction | Hydrologically conditioned DEM |
| **12** | Seasonal NDVI Crop Biomass Dynamics | 10 m | Sentinel-2 L2A (2024–2025) |
| **13** | Soil Texture Classification | 1:50,000 | NBSS&LUP Soil Resource Map |
| **14** | Hydrogeomorphological Units | 1:50,000 | NRSC Bhuvan / GSI |
| **15** | RGNDWM 250k Ground Water Prospects Grid | 1° × 1° / 15' × 15' | NRSC / ISRO Quadrangle Index |
| **16** | Continuous Drainage Density Heatmap (KDE) | 50 m metric KDE | WhiteboxTools D8 Hydro Network |

---

## 4. Execution Guide

You can run individual stages or execute the full end-to-end pipeline using `run_pipeline.py`:

```bash
# Execute entire end-to-end pipeline (Stages 1 through 5)
python src/run_pipeline.py --all

# Run individual pipeline stages:
python src/run_pipeline.py --download     # Stage 01: Extract boundaries & ingest AOI
python src/run_pipeline.py --analysis     # Stage 02: Process spatial layers & verify health
python src/run_pipeline.py --maps         # Stage 03: Re-render all 300 DPI transparent-legend maps
python src/run_pipeline.py --excels       # Stage 04: Re-generate individual & master Excel workbooks
python src/run_pipeline.py --word         # Stage 05: Re-compile client Word Atlas report
```

All execution outputs, timestamps, and warnings are logged to [`logs/pipeline.log`](file:///e:/MAPPING%20WORK/logs/pipeline.log).
