import matplotlib.pyplot as plt
import seaborn as sns

def plot_timezone_bar_chart(df):
    """
    Plot a bar chart for the distribution of airports by time zone.
    """
    timezone_counts = df['tz'].value_counts()
    plt.figure(figsize=(12, 6))
    sns.barplot(x=timezone_counts.index, y=timezone_counts.values, palette="coolwarm")
    plt.xticks(rotation=45)
    plt.xlabel("Time Zones")
    plt.ylabel("Number of Airports")
    plt.title("Time Zones Distribution of Airports")
    plt.show()

def plot_histogram_euclidean(df):
    """
    Plot a histogram for Euclidean distances from JFK.
    """
    plt.figure(figsize=(10, 6))
    plt.hist(df['euclidean_distance'], bins=50, color='blue')
    plt.xlabel("Euclidean Distance from JFK")
    plt.ylabel("Number of Airports")
    plt.title("Distribution of Euclidean Distances from JFK")
    plt.show()

def plot_histogram_geodesic(df):
    """
    Plot a histogram for Geodesic distances from JFK.
    """
    plt.figure(figsize=(10, 6))
    plt.hist(df['geodesic_distance'], bins=50, color='orange')
    plt.xlabel("Geodesic Distance from JFK (km)")
    plt.ylabel("Number of Airports")
    plt.title("Distribution of Geodesic Distances from JFK")
    plt.show()

def plot_histogram_flight_time(df):
    """
    Plot a histogram for Estimated Flight Times from JFK.
    """
    plt.figure(figsize=(10, 6))
    plt.hist(df['estimated_flight_time'], bins=50, color='purple', edgecolor='black')
    plt.xlabel('Estimated Flight Time (hours)')
    plt.ylabel('Number of Airports')
    plt.title('Distribution of Estimated Flight Times from JFK')
    plt.show()
