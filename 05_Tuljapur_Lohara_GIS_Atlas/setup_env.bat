@echo off
REM Setup virtual environment and install dependencies
echo Checking virtual environment...
if not exist "venv" (
    echo Creating Python virtual environment in venv...
    python -m venv venv
)
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Upgrading pip and installing required packages...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ========================================================
echo Environment setup finished!
echo.
echo NEXT STEPS:
echo 1. Extract AOI (already completed, but re-runnable anytime):
echo    python prepare_aoi.py
echo.
echo 2. Authenticate Earth Engine:
echo    earthengine authenticate
echo.
echo 3. Run mapping data downloader:
echo    python tuljapur_lohara_map_data.py --project YOUR_GCP_PROJECT --themes all
echo ========================================================
pause
