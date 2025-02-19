
import pandas as pd
from timezonefinder import TimezoneFinder
import pytz

def load_data(csv_path="airports.csv"):
    """
    Load and preprocess the airports data.
    
    - Reads the CSV file.
    - Renames columns.
    - Fills in missing timezone data using TimezoneFinder.
    - Drops any rows with missing values.
    
    Parameters:
        csv_path (str): Path to the airports CSV file.
        
    Returns:
        pd.DataFrame: Preprocessed DataFrame.
    """
    df = pd.read_csv(csv_path, delimiter=",")
    df.columns = ["FAA", "name", "lat", "lon", "alt", "tz", "dst", "tzone"]
    
    # Create a TimezoneFinder object
    tf = TimezoneFinder()
    
    def get_timezone_data(row):
        try:
            if pd.isna(row['tz']) or pd.isna(row['dst']) or pd.isna(row['tzone']):
                timezone = tf.timezone_at(lng=row['lon'], lat=row['lat'])
                if timezone:
                    tz_obj = pytz.timezone(timezone)
                    now = pd.Timestamp.now(tz=pytz.utc)
                    local_now = now.astimezone(tz_obj)
                    tz_offset = local_now.utcoffset().total_seconds() / 3600  # Convert seconds to hours
                    dst_active = "A" if local_now.dst() != pd.Timedelta(0) else "N"
                    return pd.Series([tz_offset, dst_active, timezone], index=['tz', 'dst', 'tzone'])
        except Exception as e:
            pass
        
        return pd.Series([row['tz'], row['dst'], row['tzone']], index=['tz', 'dst', 'tzone'])
    
    df[['tz', 'dst', 'tzone']] = df.apply(get_timezone_data, axis=1)
    df = df.dropna()
    return df
