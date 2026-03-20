# Interactive Global Map of MCS Initiations

Welcome! This repository contains the interactive visualization application used to map, filter, and track Mesoscale Convective System (MCS) initiations globally using natively subsetted Parquet track files and high-resolution Virtual Zarr IR imagery.

---

## 🚀 Deployment Guide for Students on Keeling

> **Prerequisites**: You must have a university NetID and access to the Keeling research computing cluster. 

---

### Step 1 — Clone the Repository (first time only)

SSH into Keeling and clone this repository into your home or scratch directory:

```bash
ssh <netid>@keeling.earth.illinois.edu
cd ~   # or cd /data/keeling/a/<netid>/
git clone https://github.com/snesbitt-uiuc/interactive_mcs_map.git
cd interactive_mcs_map
```

---

### Step 2 — Set Up a VS Code Tunnel on Keeling

A **VS Code tunnel** lets you run VS Code in your local browser (or local VS Code app) while all computation executes on Keeling — no VPN needed.

#### 2a. Start the tunnel on Keeling

SSH into Keeling (or open any existing session) and run:

```bash
code tunnel
```

> **First run only**: The CLI will ask you to authenticate with a GitHub or Microsoft account and give the tunnel a name (e.g. `keeling`). Follow the on-screen link to complete authentication in your browser.

After authentication, the terminal will print a URL like:

```
https://vscode.dev/tunnel/keeling
```

Keep this terminal session alive (use `tmux` or `screen` so it persists if your SSH drops):

```bash
# Recommended — run inside a persistent tmux session
tmux new -s tunnel
code tunnel
# Detach with Ctrl-B then D
```

#### 2b. Open the tunnel in your browser

Navigate to **[https://vscode.dev/tunnel/keeling](https://vscode.dev/tunnel/keeling)** (substituting whatever name you chose) in any browser. You now have a full VS Code interface running directly on Keeling.

Open the cloned `interactive_mcs_map/` folder via **File → Open Folder**.

---

### Step 3 — Create and Activate the Conda Environment

Open the **VS Code integrated terminal** (`` Ctrl+` ``) and build the environment from the included spec file:

```bash
conda env create -f environment.yaml
conda activate mcs_map_env
```

This installs all required dependencies: `panel`, `holoviews`, `xarray`, `kerchunk`, `cartopy`, `pyarrow`, `ipywidgets`, and more.

> **This step only needs to be done once.** On future sessions, just re-run `conda activate mcs_map_env`.

Next, register the environment as a Jupyter kernel so VS Code can find it:

```bash
python -m ipykernel install --user --name mcs_map_env --display-name "Python (mcs_map_env)"
```

---

### Step 4 — Select the Python Kernel

1. Open **`Panel_Interactive_Map.ipynb`** in VS Code.
2. Click the kernel selector in the top-right corner of the notebook.
3. Choose **`Python (mcs_map_env)`** from the list.

If the kernel does not appear, reload the VS Code window (**Ctrl+Shift+P → Developer: Reload Window**) and try again.

---

### Step 5 — Launch the App

Run the single notebook cell that ends with `main().servable()`.

The Panel app will render inline inside the notebook output cell. A **"Loading IR Data…"** spinner will appear when storm imagery is being fetched — this typically takes **10–15 seconds** on first load.

---

## 🖥 Using the Interface

| Step | Action | Result |
|------|--------|--------|
| 1 | **Click any 1×1° grid square** on the global map | Filters the storm list to that region |
| 2 | **Click a storm row** in the table below the map | Triggers IR imagery extraction for that event |
| 3 | **Drag the time slider** or use **◄ Prev / Next ►** | Scrubs through the ±4 hour storm lifecycle with zero lag |

The IR viewer shows:
- High-resolution brightness-temperature imagery
- MCS contours at 225 K and 241 K thresholds
- Storm trajectory line and current-position marker

---

## ⚙️ Architecture Notes

- **Data source**: Parquet track file at `/data/scratch/a/snesbitt/zeng_tracking_v2.parquet`
- **IR imagery**: Single-node Virtual Zarr index at `/data/gpm/a/snesbitt/gpm_mergir_vzarr/mergir_master.json` — treating the multi-decade MERG-IR dataset as one high-performance array
- **HoloMap caching**: All 9 sequence frames are pushed to the browser's DOM upfront, making timeline scrubbing instantaneous
- **Dateline handling**: Automatic `PlateCarree` re-centering ensures storms crossing ±180° or 0°/360° render without clipping
- **Do not modify** `panel_interactive_map.py` unless you are developing new feature extensions — all user-facing interactions are controlled from the notebook
