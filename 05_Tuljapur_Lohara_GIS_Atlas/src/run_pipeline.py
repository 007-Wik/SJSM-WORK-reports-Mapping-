#!/usr/bin/env python3
"""
Master End-to-End Orchestrator for GIS & Environmental Mapping Pipeline
Usage:
  python src/run_pipeline.py --all           # Execute entire end-to-end pipeline
  python src/run_pipeline.py --download      # Stage 01: Data Ingestion & AOI Extraction
  python src/run_pipeline.py --analysis      # Stage 02: GIS Spatial Processing & Layer Verification
  python src/run_pipeline.py --maps          # Stage 03: 300 DPI Transparent-Legend Cartographic Maps
  python src/run_pipeline.py --excels        # Stage 04: Individual Block Excels & Master Workbook
  python src/run_pipeline.py --word          # Stage 05: Client Consulting-Grade Word Atlas Report
"""
import sys
import time
import logging
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure timestamped logging
log_file = LOG_DIR / "pipeline.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)


def run_stage_01():
    logging.info("Executing Stage 01: Data Download & AOI Ingestion...")
    from importlib import import_module
    mod = import_module("01_data_download")
    mod.extract_aoi_boundaries()


def run_stage_02():
    logging.info("Executing Stage 02: Spatial Processing & GIS Analysis...")
    from importlib import import_module
    mod = import_module("02_gis_analysis")
    mod.run_gis_analysis_verification()


def run_stage_03():
    logging.info("Executing Stage 03: Cartographic Map Generation (300 DPI Transparent-Legend)...")
    from importlib import import_module
    mod = import_module("03_cartographic_maps")
    mod.generate_all_block_maps()


def run_stage_04():
    logging.info("Executing Stage 04: Dedicated Block Excel Reports Generation...")
    from importlib import import_module
    mod = import_module("04_excel_reports")
    mod.generate_both_individual_excels()


def run_stage_05():
    logging.info("Executing Stage 05: Client Consulting Word Atlas Report Generation...")
    from importlib import import_module
    mod = import_module("05_word_report")
    mod.build_word_report()


def main():
    parser = argparse.ArgumentParser(
        description="Master Orchestrator for Dharashiv GIS & Environmental Atlas"
    )
    parser.add_argument("--all", action="store_true", help="Run full end-to-end pipeline (Stages 1–5)")
    parser.add_argument("--download", action="store_true", help="Run Stage 01: Data Download & AOI Extraction")
    parser.add_argument("--analysis", action="store_true", help="Run Stage 02: GIS Spatial Processing")
    parser.add_argument("--maps", action="store_true", help="Run Stage 03: Cartographic Map Generation")
    parser.add_argument("--excels", action="store_true", help="Run Stage 04: Excel Reports Generation")
    parser.add_argument("--word", action="store_true", help="Run Stage 05: Word Report Generation")

    args = parser.parse_args()

    # If no flags passed, show help or run interactive
    if not any([args.all, args.download, args.analysis, args.maps, args.excels, args.word]):
        parser.print_help()
        sys.exit(0)

    start_time = time.time()
    logging.info("Pipeline execution started.")

    try:
        if args.all or args.download:
            run_stage_01()
        if args.all or args.analysis:
            run_stage_02()
        if args.all or args.maps:
            run_stage_03()
        if args.all or args.excels:
            run_stage_04()
        if args.all or args.word:
            run_stage_05()

        elapsed = time.time() - start_time
        logging.info(f"Pipeline execution completed successfully in {elapsed:.1f} seconds.")
    except Exception as e:
        logging.error(f"Pipeline execution failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
