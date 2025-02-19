import matplotlib.pyplot as plt
import seaborn as sns

def plot_timezone_pie_chart(df):
    """
    Plot a pie chart for the time zones distribution of airports.
    """
    timezone_counts = df['tz'].value_counts()
    
    plt.figure(figsize=(8, 8))
    plt.pie(timezone_counts, labels=timezone_counts.index, autopct='%1.1f%%', 
            colors=sns.color_palette("coolwarm", len(timezone_counts)), startangle=90)
    plt.title("Time Zones Distribution of Airports")
    plt.axis('equal')
    plt.show()
    
    # Pie chart with percentages outside and lines pointing to wedges
    plt.figure(figsize=(10, 8))
    wedges, texts, autotexts = plt.pie(
        timezone_counts, labels=timezone_counts.index, autopct='%1.1f%%', 
        colors=sns.color_palette("coolwarm", len(timezone_counts)), startangle=90,
        wedgeprops={'edgecolor': 'black', 'linewidth': 1.5},
        pctdistance=1.1, labeldistance=100
    )
    
    for text in texts:
        text.set_fontsize(12)
        text.set_fontweight('bold')
    
    for autotext in autotexts:
        autotext.set_fontsize(12)
        autotext.set_fontweight('bold')
    
    plt.legend(wedges, timezone_counts.index, title="Time Zones", loc="upper left", bbox_to_anchor=(1, 1))
    plt.title("Time Zones Distribution of Airports")
    plt.axis('equal')
    plt.show()
