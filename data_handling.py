import pandas as pd
import os
from pathlib import Path

def deduplicate_names(file_path):
    #Process CSV file to identify and handle duplicate names.
    
    df = pd.read_csv(file_path)
    
    # find duplicates based on name column
    duplicates = df[df['Name'].duplicated(keep=False)]
    unique_df = df.drop_duplicates(subset=['Name'], keep='first')
    
    # generate stats
    stats = {
        'total_records': len(df),
        'duplicate_count': len(df) - len(unique_df),
    }
    
    return unique_df, stats

#df_clean, stats = deduplicate_names('data/lawyer_data_part_6.csv')

def combine_csv_files(directory='final/'):
    # Find all CSV files
    csv_files = list(Path(directory).glob('*.csv'))
    print(csv_files)
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {directory}")
    
    # read and combine all CSV files
    dfs = []
    total_records = 0
    
    for file in csv_files:
        print(file)
        df = pd.read_csv(file.__str__(), engine='python')
        total_records += len(df)
        dfs.append(df)
    
    combined_df = pd.concat(dfs, ignore_index=True)
    
    unique_df = combined_df.drop_duplicates(subset=['Name'], keep='first')
    
    # Save combined data
    output_csv_path = 'final/final_lawyer_data.csv'
    unique_df.to_csv(output_csv_path, index=False)
    output_excel_path = 'final/final_lawyer_data.xlsx'
    unique_df.to_excel(output_excel_path, index=False)
    
    
    stats = {
        'total_records': total_records,
        'files_processed': len(csv_files),
        'final_records': len(unique_df),
        'duplicates_removed': total_records - len(unique_df)
    }
    
    return output_excel_path, stats


try:
    output_file, stats = combine_csv_files()
    print(f"Files processed: {stats['files_processed']}")
    print(f"Total records: {stats['total_records']}")
    print(f"Final records: {stats['final_records']}")
    print(f"Duplicates removed: {stats['duplicates_removed']}")
    print(f"Combined file saved to: {output_file}")
except Exception as e:
    print(f"Error: {str(e)}")