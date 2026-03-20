import os
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import panel as pn
import holoviews as hv
import hvplot.pandas
import hvplot.xarray
from datetime import timedelta
from scipy.stats import binned_statistic_2d
import warnings
import asyncio
import glob
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore")
pn.extension('tabulator')
hv.extension('bokeh')

IR_BASE_PATH = '/data/gpm/a/snesbitt/gpm_mergir'
V2_PATH = '/data/scratch/a/snesbitt/zeng_tracking_v2.parquet'

def get_ir_filepath(time):
    subdir = f"{time.year:04d}-{time.month:02d}"
    hour_str = f"{time.year:04d}{time.month:02d}{time.day:02d}{time.hour:02d}"
    fname = f"merg_{hour_str}_4km-pixel.nc4"
    fpath = os.path.join(IR_BASE_PATH, subdir, fname)
    time_idx = 1 if time.minute >= 30 else 0
    return fpath, time_idx

def get_track_data():
    df = pd.read_parquet(V2_PATH, columns=['start_status', 'meanlat', 'meanlon', 'start_basetime', 'area_0', 'area_4', 'growth_rate'])
    df_plot = df[df['start_status'] == 1].dropna(subset=['meanlat', 'meanlon']).copy()
    
    # Convert to 0-360
    df_plot['meanlon_360'] = df_plot['meanlon'] % 360
    return df_plot

def get_track_file(track_idx):
    import glob
    files = sorted(glob.glob('/data/gpm/a/snesbitt/tracks/mcs_tracks_final_extc_*.nc'))
    counts = [21142, 34497, 32452, 33468, 34431, 33435, 33676, 34664, 34991, 34346, 34106, 33872, 34240, 34366, 33674, 32682, 33995, 33025, 34250, 32843, 32138]
    
    current_cum = 0
    file_idx = 0
    while track_idx >= current_cum + counts[file_idx]:
        current_cum += counts[file_idx]
        file_idx += 1
    local_idx = track_idx - current_cum
    return files[file_idx], local_idx

def load_traj(filename, local_idx):
    with xr.open_dataset(filename) as ds:
        track_ds = ds.isel(tracks=local_idx)
        valid = track_ds['meanlon'].notnull()
        times = track_ds['base_time'].where(valid, drop=True).values
        lats = track_ds['meanlat'].where(valid, drop=True).values
        lons = track_ds['meanlon'].where(valid, drop=True).values
        
        lons_360 = lons % 360
    return pd.DataFrame({'time': times, 'lat': lats, 'lon': lons_360})

def render_holoviews_step(meta, t, traj_df, preloaded_tb=None):
    try:
        current_time = pd.Timestamp(t)

        lon_cen = meta['meanlon_360']
        lat_cen = meta['meanlat']
        
        lon_min, lon_max = lon_cen-5, lon_cen+5
        lat_min, lat_max = lat_cen-5, lat_cen+5
        
        tb = None
        
        if preloaded_tb is not None:
            tb = preloaded_tb
        else:
            fpath, tidx = get_ir_filepath(current_time)
            
            if os.path.exists(fpath):
                with xr.open_dataset(fpath) as ds_ir:
                    ds_step = ds_ir.isel(time=tidx)
                    
                    left, right = lon_min, lon_max
                    if left < 180 and right > 180:
                        tb1 = ds_step['Tb'].sel(lat=slice(lat_min-2, lat_max+2), lon=slice(left, 180)).load()
                        tb2 = ds_step['Tb'].sel(lat=slice(lat_min-2, lat_max+2), lon=slice(-180, right - 360)).load()
                        tb2 = tb2.assign_coords(lon=(tb2.lon + 360))
                        tb = xr.concat([tb1, tb2], dim='lon')
                    elif left >= 180:
                        tb = ds_step['Tb'].sel(lat=slice(lat_min-2, lat_max+2), lon=slice(left - 360, right - 360)).load()
                        tb = tb.assign_coords(lon=(tb.lon + 360))
                    else:
                        tb = ds_step['Tb'].sel(lat=slice(lat_min-2, lat_max+2), lon=slice(left, right)).load()
        
        if tb is not None:
            # We use a PlateCarree projection centered exactly on the storm (lon_cen).
            # This 'relativizes' the coordinates so that the storm is always at x=0,
            # which allows us to use a simple static xlim=(-5, 5) to zoom in perfectly.
            img = tb.hvplot.quadmesh(x='lon', y='lat', cmap='Greys', clim=(190, 300), 
                                  geo=True, coastline=True, projection=ccrs.PlateCarree(central_longitude=lon_cen),
                                  line_alpha=0, line_width=0)
            
            # Contours for convection thresholds (225K = Deep Convection, 241K = Cloud boundary)
            c241 = tb.hvplot.contour(x='lon', y='lat', levels=[241], color='cyan', geo=True)
        else:
            img = hv.Text(lon_cen, lat_cen, "MISSING IR").opts(xlim=(lon_min, lon_max), ylim=(lat_min, lat_max))
            c225, c241 = hv.Curve([]), hv.Curve([])

        # Handle 'wrapping' for storms near the 180/-180 Dateline or 0/360 Prime Meridian.
        # This ensures the yellow trajectory line doesn't 'jump' across the whole map.
        traj_df['lon_plot'] = traj_df['lon']
        if lon_max > 360:
            traj_df.loc[traj_df['lon'] < 180, 'lon_plot'] += 360
        elif lon_min < 0:
            traj_df.loc[traj_df['lon'] > 180, 'lon_plot'] -= 360
            
        line = traj_df.hvplot.paths(x='lon_plot', y='lat', geo=True, color='yellow', line_width=2)
        
        # Current Point
        traj_df['time_dt'] = pd.to_datetime(traj_df['time'])
        nearest_idx = np.argmin(np.abs(traj_df['time_dt'] - current_time))
        
        point_plot = hv.Points([])
        if abs((traj_df['time_dt'].iloc[nearest_idx] - current_time).total_seconds()) < 3600:
            curr_row = traj_df.iloc[[nearest_idx]]
            point_plot = curr_row.hvplot.points(x='lon_plot', y='lat', geo=True, color='none', line_color='red', size=80, marker='o')
        
        plot = img * c225 * c241 * line * point_plot
        return plot.opts(width=1000, height=800, xlim=(-5, 5), ylim=(lat_min, lat_max))
        
    except Exception as e:
        print(f"Error rendering mapping sequence at {t}: {e}")
        return hv.Text(0, 0, f"Error rendering mapping sequence at {t}: {e}").opts(width=1000, height=800)

class MCSApp:
    def __init__(self):
        self.df_plot = get_track_data()
        self.selected_box = (None, None, None, None) # lon_min, lon_max, lat_min, lat_max
        self.selected_track_id = None
        self.tap = None
        
        self.debug_text = pn.pane.Markdown("**Debug Console**: Waiting for click...")
        
        self.current_meta = None
        self.current_traj = None
        self.current_init_time = None
        self.preloaded_plots = {}
        
        print("Initializing Virtual Zarr Engine...")
        self.zarr_ds = xr.open_dataset('reference://', engine='zarr', backend_kwargs={
            "storage_options": {"fo": "/data/gpm/a/snesbitt/gpm_mergir_vzarr/mergir_master.json"},
            "consolidated": False
        })
        print("Zarr engine mounted successfully!")
        
        self.table = pn.widgets.Tabulator(pd.DataFrame(), height=700, sizing_mode='stretch_width', pagination='remote', page_size=25, show_index=False)
        self.table.disabled = False
        self.image_pane = pn.pane.HoloViews()
        self.record_table = pn.widgets.Tabulator(pd.DataFrame(), height=300, sizing_mode='stretch_width', show_index=False)
        
        # Disable editing
        self.table.editors = {col: None for col in ['track_id', 'start_basetime', 'start_lat', 'start_lon_360', 'initial_area', 'final_area', 'growth_rate']}
        self.record_table.editors = {'Property': None, 'Value': None}
        
        self.time_slider = pn.widgets.IntSlider(name='time index relative to start', start=-4, end=4, step=1, value=0, width=400)
        self.btn_prev = pn.widgets.Button(name='◄ Prev', width=80)
        self.btn_next = pn.widgets.Button(name='Next ►', width=80)
        
        self.btn_prev.on_click(self.on_prev)
        self.btn_next.on_click(self.on_next)
        
        self.time_controls = pn.Row(self.btn_prev, self.time_slider, self.btn_next, align='center')
        
        self.image_pane = pn.pane.HoloViews(widgets={'time index relative to start': self.time_slider})
        
        # Select callback for table
        self.table.param.watch(self.on_table_select, 'selection')
        
    def plot_map(self):
        lon_bins = np.arange(0, 361, 1)
        lat_bins = np.arange(-90, 91, 1)
        
        counts, _, _, _ = binned_statistic_2d(
            self.df_plot['meanlon_360'], self.df_plot['meanlat'], None, 
            statistic='count', bins=[lon_bins, lat_bins]
        )
        counts = counts.T
        counts[counts == 0] = np.nan
        
        ds = xr.Dataset(
            {"mcs_count": (["lat", "lon"], counts)},
            coords={
                "lon": lon_bins[:-1] + 0.5,
                "lat": lat_bins[:-1] + 0.5,
            },
        )
        
        map_plot = ds.hvplot.quadmesh(x='lon', y='lat', z='mcs_count', cmap='viridis', 
                                   geo=True, coastline=True, 
                                   projection=ccrs.PlateCarree(central_longitude=180),
                                   xlim=(0, 360), ylim=(-90, 90),
                                   line_alpha=0, line_width=0,
                                   width=900, height=450, title='Global MCS Initiation Counts (0-360)')
        
        # Setup Tap stream for clicking - attach to the quadmesh exactly
        self.tap = hv.streams.Tap(source=map_plot.get(0) if isinstance(map_plot, hv.Overlay) else map_plot, x=np.nan, y=np.nan)
        self.tap.param.watch(self.on_map_click, ['x', 'y'])
        
        return map_plot
        
    def on_map_click(self, *events):
        x, y = self.tap.x, self.tap.y
        if x is None or np.isnan(x) or y is None or np.isnan(y):
            self.debug_text.object = "**Debug Console**: Click ignored (Invalid coordinate)"
            return
            
        x_360 = x % 360
        lon_idx = int(np.floor(x_360))
        lat_idx = int(np.floor(y))
        
        lon_min, lon_max = lon_idx, lon_idx + 1
        lat_min, lat_max = lat_idx, lat_idx + 1
        
        # Filter df
        mask = (self.df_plot['meanlon_360'] >= lon_min) & (self.df_plot['meanlon_360'] <= lon_max) & \
               (self.df_plot['meanlat'] >= lat_min) & (self.df_plot['meanlat'] <= lat_max)
        
        storms = self.df_plot[mask].copy()
        
        self.debug_text.object = f"**Debug Console**: Clicked x={x:.1f}, y={y:.1f} | Box [{lon_min}-{lon_max}, {lat_min}-{lat_max}] | Found {len(storms)} storms."
        
        storms['track_id'] = storms.index
        
        display_df = storms[['track_id', 'start_basetime', 'meanlat', 'meanlon_360', 'area_0', 'area_4', 'growth_rate']].copy()
        display_df['track_id'] = display_df['track_id'].astype(str)
        display_df.rename(columns={
            'meanlat': 'start_lat',
            'meanlon_360': 'start_lon_360',
            'area_0': 'initial_area',
            'area_4': 'final_area'
        }, inplace=True)
        
        self.table.value = display_df
        self.table.selection = []
        self.image_pane.object = None

    async def on_table_select(self, event):
        selection = event.new
        if not selection:
            return
            
        self.image_pane.loading = True
        await asyncio.sleep(0.1) # Yield to push loading state
        
        try:
            row_idx = selection[0]
            display_df = self.table.value
            real_track_id = int(display_df.iloc[row_idx]['track_id'])
            
            self.current_meta = self.df_plot.loc[[real_track_id]].iloc[0]
            fname, l_idx = get_track_file(real_track_id)
            self.current_traj = load_traj(fname, l_idx)
            self.current_init_time = pd.Timestamp(self.current_meta['start_basetime'])
            
            t_start = self.current_init_time - timedelta(hours=4)
            t_end = self.current_init_time + timedelta(hours=4)
            
            lon_cen = self.current_meta['meanlon_360']
            lat_cen = self.current_meta['meanlat']
            lon_min, lon_max = lon_cen-5, lon_cen+5
            lat_min, lat_max = lat_cen-5, lat_cen+5
            
            left, right = lon_min, lon_max
            if left < 180 and right > 180:
                tb1 = self.zarr_ds['Tb'].sel(time=slice(t_start, t_end), lat=slice(lat_min-2, lat_max+2), lon=slice(left, 180)).load()
                tb2 = self.zarr_ds['Tb'].sel(time=slice(t_start, t_end), lat=slice(lat_min-2, lat_max+2), lon=slice(-180, right - 360)).load()
                tb2 = tb2.assign_coords(lon=(tb2.lon + 360))
                tb_block = xr.concat([tb1, tb2], dim='lon')
            else:
                tb_block = self.zarr_ds['Tb'].sel(time=slice(t_start, t_end), lat=slice(lat_min-2, lat_max+2), lon=slice(left, right)).load()
                
            self.preloaded_plots.clear()
            for offset in range(-4, 5):
                t_target = self.current_init_time + timedelta(hours=offset)
                tb_step = tb_block.sel(time=t_target, method='nearest')
                
                plot = render_holoviews_step(self.current_meta, t_target, self.current_traj, tb_step)
                storm_id = self.current_meta.name
                title_str = f"Storm ID {storm_id} - {t_target.strftime('%Y-%m-%d %H:%M')} UTC"
                self.preloaded_plots[offset] = plot.opts(title=title_str)
            
            # Deploy as a HoloMap. This 'flashes' all 9 frames to the browser's memory at once.
            # Once loaded into the DOM, the user can scrub the slider with ZERO lag because
            # no more Python code needs to run to switch frames.
            hmap = hv.HoloMap(self.preloaded_plots, kdims='time index relative to start')
            self.image_pane.object = hmap
            self.time_slider.value = 0
            
            # Update record table
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(V2_PATH)
            row_table = next(pf.iter_batches(batch_size=1, offset=int(real_track_id)))
            row_df = row_table.to_pandas()
            
            transposed_df = row_df.T.reset_index()
            transposed_df.columns = ['Property', 'Value']
            self.record_table.value = transposed_df
            
        except Exception as e:
            self.debug_text.object = f"**Error**: {e}"
        finally:
            self.image_pane.loading = False
            
    def on_prev(self, event):
        if self.time_slider.value > self.time_slider.start:
            self.time_slider.value -= 1
            
    def on_next(self, event):
        if self.time_slider.value < self.time_slider.end:
            self.time_slider.value += 1

    def view(self):
        return pn.Column(
            self.debug_text,
            self.plot_map(),
            pn.Row(self.table, height=700),
            self.time_controls,
            self.image_pane,
            self.record_table
        )

def main():
    app = MCSApp()
    return app.view()
