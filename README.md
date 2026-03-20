# Interactive Global Map of MCS Initiations

Welcome! This directory contains the interactive visualization application used to map, filter, and track Mesoscale Convective System (MCS) initiations globally using natively subsetted Parquet track files and high-resolution Virtual Zarr IR imagery.

## 🚀 Getting Started on the Keeling Cluster

As an undergraduate researcher, you will be running this interface directly on the Keeling computing cluster. Follow these steps to spin up the application:

### 1. Connecting to Keeling
Ensure you are connected to the university VPN and SSH into Keeling, or use the **JupyterHub / VSCode Remote-SSH** capabilities to open this directory directly on a cluster node.
```bash
ssh <netid>@keeling.earth.illinois.edu
cd /data/keeling/a/snesbitt/python/feng_tracking/interactive_mcs_map/
```

### 2. Environment Setup
The visualization engine requires a highly specific stack of libraries including `panel`, `holoviews`, `xarray`, `kerchunk`, and `cartopy`.
Dr. Nesbitt maintains an active environment named `ba3bt-ssl` that has all dependencies pre-installed. Activate it using:
```bash
conda activate ba3bt-ssl
```
*(Note: If you need a totally sandbox environment, you can alternatively scaffold one using the included `environment.yaml`: `conda env create -f environment.yaml`)*

### 3. Launching the App
The application lives natively inside a Jupyter Notebook:
1. Open the file **`Panel_Interactive_Map.ipynb`** in your Jupyter or VSCode interactive environment.
2. Select the `ba3bt-ssl` Python kernel on the top right.
3. Run the single execution block containing `main().servable()`.

## 🖥 Using the Interface

1. **Global Tracker Map**: Upon executing the cell, the app mounts the global initiation track records from `/data/scratch/a/snesbitt/zeng_tracking_v2.parquet` and renders an interactive global map. **Click any 1x1 degree square** on the map to filter initiations specifically within that geographic region.
2. **Interactive Event Table**: Once a region region is clicked, a dynamically filtered tabular list of storm records will populate below the map. 
3. **High-Res Trajectory Maps**: **Click on any storm row** in the table to trigger the extraction pipeline.
    - The script immediately interrogates a massive, single-node virtual Zarr index (`gpm_mergir_vzarr/mergir_master.json`) to synchronously download and process the high-resolution IR imagery footprint bounds over a 9-hour sequence (-4 to +4 hours offset).
    - A *Loading IR Data...* intercept will appear on the display. This takes approximately 10-15 seconds.
    - Use the **`time index relative to start`** slider or the **`◄ Prev`** / **`Next ►`** buttons to scrub back and forth through the life cycle of the storm with zero lag!

## ⚙️ Architecture Notes
- The core data model dynamically projects all coordinates over the `-180` and `180` Dateline limits and stitches geospatial data automatically using robust underlying `xarray` bounding logic. 
- You should never modify `panel_interactive_map.py` unless you are developing native feature extensions.
