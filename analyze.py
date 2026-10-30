import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import Button, CheckButtons

# 1. Data Loading and Preprocessing
def load_and_prep_data(filepath='utd_parking_data.csv'):
    df = pd.read_csv(filepath)
    df['Scrape Time'] = pd.to_datetime(df['Scrape Time'])
    df['Scrape Time'] = df['Scrape Time'].dt.tz_localize('UTC').dt.tz_convert('America/Chicago')
    df = df.sort_values('Scrape Time')
    return df

# 2. Dashboard Class for State Management
class ParkingDashboard:
    def __init__(self, df):
        self.df = df
        self.fig, self.ax = plt.subplots(figsize=(12, 7.5))
        
        # Adjust layout: top margin protects buttons, left protects filters
        plt.subplots_adjust(left=0.22, top=0.85, bottom=0.15, right=0.82)
        
        # State variables
        self.line = None
        self.peak_scatter = None
        self.current_trend_data = None
        self.current_garage = 'PS3'
        self.current_view_type = 'Trend'
        self.tooltip_lookup = {}  
        self.last_hovered_idx = None  
        self.ui_axes = [] 
        
        self.unique_levels = sorted(self.df['Level'].unique())
        self.unique_options = sorted(self.df['Option'].unique())
        self.trend_options = ['24h Rolling Avg']
        
        # Setup Annotation for Hover Tooltips 
        self.annot = self.ax.annotate(
            "", xy=(0,0), xytext=(20,20),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="gray", alpha=0.9),
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3"),
            zorder=100
        )
        self.annot.set_visible(False)
        
        self.fig.canvas.mpl_connect("motion_notify_event", self.hover)
        
        self.setup_ui_elements()
        self.hook_savefig() 
        self.plot_garage_trend('PS3')

    def hook_savefig(self):
        """Intercepts fig.savefig to hide UI elements and tooltips before writing to disk."""
        original_savefig = self.fig.savefig
        
        def custom_savefig(*args, **kwargs):
            ui_states = {ax: ax.get_visible() for ax in self.ui_axes}
            annot_state = self.annot.get_visible() if self.annot else False
            
            for ax in self.ui_axes:
                ax.set_visible(False)
            if self.annot:
                self.annot.set_visible(False)
                
            try:
                original_savefig(*args, **kwargs)
            finally:
                for ax, state in ui_states.items():
                    ax.set_visible(state)
                if self.annot:
                    self.annot.set_visible(annot_state)
                    
        self.fig.savefig = custom_savefig

    def setup_ui_elements(self):
        """Creates the interactive UI buttons in a single row and sidebar checkboxes."""
        # --- TOP BUTTONS (Single Row) ---
        # PS3 Group
        ax_btn_ps3 = plt.axes([0.05, 0.92, 0.12, 0.05])
        ax_btn_lvl_ps3 = plt.axes([0.19, 0.92, 0.12, 0.05])
        ax_btn_pmt_ps3 = plt.axes([0.33, 0.92, 0.12, 0.05])
        
        # PS4 Group
        ax_btn_ps4 = plt.axes([0.52, 0.92, 0.12, 0.05])
        ax_btn_lvl_ps4 = plt.axes([0.66, 0.92, 0.12, 0.05])
        ax_btn_pmt_ps4 = plt.axes([0.80, 0.92, 0.12, 0.05])

        self.btn_ps3 = Button(ax_btn_ps3, 'PS3 Trend')
        self.btn_lvl_ps3 = Button(ax_btn_lvl_ps3, 'PS3 by Level')
        self.btn_pmt_ps3 = Button(ax_btn_pmt_ps3, 'PS3 by Permit')

        self.btn_ps4 = Button(ax_btn_ps4, 'PS4 Trend')
        self.btn_lvl_ps4 = Button(ax_btn_lvl_ps4, 'PS4 by Level')
        self.btn_pmt_ps4 = Button(ax_btn_pmt_ps4, 'PS4 by Permit')

        self.btn_ps3.on_clicked(lambda event: self.plot_garage_trend('PS3'))
        self.btn_ps4.on_clicked(lambda event: self.plot_garage_trend('PS4'))
        self.btn_lvl_ps3.on_clicked(lambda event: self.plot_capacity_by_level('PS3'))
        self.btn_lvl_ps4.on_clicked(lambda event: self.plot_capacity_by_level('PS4'))
        self.btn_pmt_ps3.on_clicked(lambda event: self.plot_capacity_by_permit('PS3'))
        self.btn_pmt_ps4.on_clicked(lambda event: self.plot_capacity_by_permit('PS4'))

        # --- SIDEBAR FILTERS (Checkboxes) ---
        self.ax_chk_levels = plt.axes([0.02, 0.55, 0.14, 0.25])
        self.ax_chk_levels.set_title('Filter by Level', fontweight='bold')
        self.chk_levels = CheckButtons(
            self.ax_chk_levels, 
            [f'Level {l}' for l in self.unique_levels], 
            [True] * len(self.unique_levels)
        )
        
        self.ax_chk_options = plt.axes([0.02, 0.25, 0.14, 0.25])
        self.ax_chk_options.set_title('Filter by Permit', fontweight='bold')
        self.chk_options = CheckButtons(
            self.ax_chk_options, 
            self.unique_options, 
            [True] * len(self.unique_options)
        )
        
        self.ax_chk_trends = plt.axes([0.02, 0.10, 0.14, 0.10])
        self.ax_chk_trends.set_title('Trendlines', fontweight='bold')
        self.chk_trends = CheckButtons(
            self.ax_chk_trends, 
            self.trend_options, 
            [False]
        )

        self.chk_levels.on_clicked(self.on_filter_changed)
        self.chk_options.on_clicked(self.on_filter_changed)
        self.chk_trends.on_clicked(self.on_filter_changed)
        
        # Store all created UI axes for the save hook
        self.ui_axes = [
            ax_btn_ps3, ax_btn_lvl_ps3, ax_btn_pmt_ps3,
            ax_btn_ps4, ax_btn_lvl_ps4, ax_btn_pmt_ps4,
            self.ax_chk_levels, self.ax_chk_options, self.ax_chk_trends
        ]

    def on_filter_changed(self, label):
        if self.current_view_type == 'Trend':
            self.plot_garage_trend(self.current_garage)

    def get_active_filters(self):
        active_levels = [l for l, state in zip(self.unique_levels, self.chk_levels.get_status()) if state]
        active_options = [o for o, state in zip(self.unique_options, self.chk_options.get_status()) if state]
        active_trends = [t for t, state in zip(self.trend_options, self.chk_trends.get_status()) if state]
        return active_levels, active_options, active_trends

    def plot_garage_trend(self, garage_name):
        self.ax.clear()
        self.current_garage = garage_name
        self.current_view_type = 'Trend'
        self.last_hovered_idx = None 
        
        self.ax_chk_levels.set_visible(True)
        self.ax_chk_options.set_visible(True)
        self.ax_chk_trends.set_visible(True)
        
        active_levels, active_options, active_trends = self.get_active_filters()
        
        garage_df = self.df[
            (self.df['Garage'] == garage_name) & 
            (self.df['Level'].isin(active_levels)) & 
            (self.df['Option'].isin(active_options))
        ]
        
        self.current_trend_data = garage_df.groupby('Scrape Time')['Available Spaces'].sum().reset_index()
        
        if not garage_df.empty:
            self.tooltip_lookup = (
                garage_df.groupby(['Scrape Time', 'Level'])['Available Spaces']
                .sum()
                .unstack(fill_value=0)
                .to_dict('index')
            )
        else:
            self.tooltip_lookup = {}
            
        self.line, = self.ax.plot(
            self.current_trend_data['Scrape Time'], 
            self.current_trend_data['Available Spaces'], 
            color='tab:blue', linestyle='None', marker='o', markersize=3, 
            label=f'{garage_name} Filtered Capacity',
            zorder=3
        )
        
        if not self.current_trend_data.empty:
            if '24h Rolling Avg' in active_trends:
                rolling_df = self.current_trend_data.set_index('Scrape Time').sort_index()
                
                # Compute rolling average globally to preserve accuracy at the edges
                rolling_series = rolling_df['Available Spaces'].rolling('24h').mean()
                
                # Determine bounds for the first and last full days
                min_time = self.current_trend_data['Scrape Time'].min()
                max_time = self.current_trend_data['Scrape Time'].max()
                
                first_full_day_start = min_time.normalize() + pd.Timedelta(days=1)
                last_full_day_end = max_time.normalize() - pd.Timedelta(seconds=1)
                
                # Slice to hide partial days
                if first_full_day_start <= last_full_day_end:
                    rolling_series = rolling_series.loc[first_full_day_start:last_full_day_end]
                
                self.ax.plot(
                    rolling_series.index, rolling_series.values, 
                    color='purple', linewidth=2.5, label='24h Rolling Avg', zorder=4
                )
        
        if not self.current_trend_data.empty:
            self.current_trend_data['Date'] = self.current_trend_data['Scrape Time'].dt.date
            daily_min_idx = self.current_trend_data.groupby('Date')['Available Spaces'].idxmin()
            peak_points = self.current_trend_data.loc[daily_min_idx]
            
            self.peak_scatter = self.ax.scatter(
                peak_points['Scrape Time'], 
                peak_points['Available Spaces'],
                color='red', marker='*', s=150, zorder=5, label='Daily Peak (Lowest Capacity)'
            )
        
        self.ax.set_title(f'Parking Trends Over Time (CDT): {garage_name}', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('Time', fontsize=12)
        self.ax.set_ylabel('Available Spaces (Based on Filters)', fontsize=12)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S', tz=self.df['Scrape Time'].dt.tz))
        for tick in self.ax.get_xticklabels():
            tick.set_rotation(45)
            
        self.ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1))
        
        self.annot = self.ax.annotate(
            "", xy=(0,0), xytext=(20,20), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="gray", alpha=0.9),
            arrowprops=dict(arrowstyle="->"), zorder=100
        )
        self.annot.set_visible(False)
        plt.draw()

    def plot_capacity_by_level(self, garage_name):
        self.ax.clear()
        self.line = None 
        self.current_garage = garage_name
        self.current_view_type = 'By_Level'
        
        self.ax_chk_levels.set_visible(False)
        self.ax_chk_options.set_visible(False)
        self.ax_chk_trends.set_visible(False)
        
        garage_df = self.df[self.df['Garage'] == garage_name]
        level_data = garage_df.groupby('Level')['Available Spaces'].mean().reset_index()
        
        self.ax.bar(level_data['Level'].astype(str), level_data['Available Spaces'], color='tab:orange')
        self.ax.set_title(f'Average Available Capacity by Level: {garage_name}', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('Garage Level', fontsize=12)
        self.ax.set_ylabel('Avg. Available Spaces', fontsize=12)
        self.ax.grid(axis='y', linestyle='--', alpha=0.7)
        plt.draw()

    def plot_capacity_by_permit(self, garage_name):
        self.ax.clear()
        self.line = None
        self.current_garage = garage_name
        self.current_view_type = 'By_Permit'
        
        self.ax_chk_levels.set_visible(False)
        self.ax_chk_options.set_visible(False)
        self.ax_chk_trends.set_visible(False)
        
        garage_df = self.df[self.df['Garage'] == garage_name]
        permit_data = garage_df.groupby('Option')['Available Spaces'].mean().reset_index()
        
        self.ax.bar(permit_data['Option'], permit_data['Available Spaces'], color='tab:green')
        self.ax.set_title(f'Average Available Capacity by Permit Type: {garage_name}', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('Permit Type', fontsize=12)
        self.ax.set_ylabel('Avg. Available Spaces', fontsize=12)
        self.ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        for tick in self.ax.get_xticklabels():
            tick.set_rotation(15)
        plt.draw()

    def update_annot(self, ind, event):
        idx = ind["ind"][0]
        hovered_time = self.current_trend_data.iloc[idx]['Scrape Time']
        
        level_caps = self.tooltip_lookup.get(hovered_time, {})
        
        text_lines = [f"Time: {hovered_time.strftime('%H:%M:%S on %Y-%m-%d')}"]
        text_lines.append("-" * 25)
        
        if not level_caps:
            text_lines.append("No spaces match filter criteria")
        else:
            for level in sorted(level_caps.keys()):
                text_lines.append(f"Level {level}: {level_caps[level]} spaces")
        
        x, y = self.line.get_data()
        self.annot.xy = (x[idx], y[idx])
        self.annot.set_text("\n".join(text_lines))
        
        _, fig_height = self.fig.canvas.get_width_height()
        if event.y > fig_height * 0.70:
            self.annot.xytext = (20, -110) 
        else:
            self.annot.xytext = (20, 20)

    def hover(self, event):
        if self.line is None:
            return 
            
        vis = self.annot.get_visible()
        if event.inaxes == self.ax:
            cont, ind = self.line.contains(event)
            if cont:
                idx = ind["ind"][0]
                if self.last_hovered_idx == idx and vis:
                    return 
                    
                self.last_hovered_idx = idx
                self.update_annot(ind, event)
                self.annot.set_visible(True)
                self.fig.canvas.draw_idle()
            else:
                if vis:
                    self.last_hovered_idx = None
                    self.annot.set_visible(False)
                    self.fig.canvas.draw_idle()

def main():
    try:
        df = load_and_prep_data('utd_parking_data.csv')
    except FileNotFoundError:
        print("Error: Could not find 'utd_parking_data.csv'.")
        return
        
    dashboard = ParkingDashboard(df)
    plt.show()

if __name__ == "__main__":
    main()