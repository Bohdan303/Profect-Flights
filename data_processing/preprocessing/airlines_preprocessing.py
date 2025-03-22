def preprocess_airlines(df_airlines):
    if "name" in df_airlines.columns:
        missing_count = df_airlines["name"].isnull().sum()
        if missing_count > 0:
            print(f"Filling {missing_count} missing values in 'name' with 'Unknown'.")
            df_airlines["name"] = df_airlines["name"].fillna("Unknown")
    else:
        print("The 'name' column is not present in airlines data.")
    return df_airlines
