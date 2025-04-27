import pandas as pd
import matplotlib.pyplot as plt
import argparse
from datetime import datetime
import os

def plot_transaction_types(df, output_dir='./plots'):
    """Create a pie chart of transaction types (MINT vs TRANSFER)"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Count transaction types
    type_counts = df['type'].value_counts()
    
    # Create pie chart
    plt.figure(figsize=(8, 6))
    plt.pie(type_counts, labels=type_counts.index, autopct='%1.1f%%', startangle=90, colors=['#3498db', '#e74c3c'])
    plt.title('Distribution of Transaction Types')
    plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
    plt.savefig(f'{output_dir}/transaction_types_pie.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved pie chart to {output_dir}/transaction_types_pie.png")

def plot_transactions_over_time(df, output_dir='./plots'):
    """Create a line chart of transactions over time"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Make sure we have a date column
    if 'date' not in df.columns:
        print("No date column found in the data")
        return
    
    # Convert to datetime if it's not already
    df['date'] = pd.to_datetime(df['date'])
    
    # Group by date and count transactions
    daily_counts = df.groupby(['date', 'type']).size().unstack().fillna(0)
    
    # In case we don't have both types on every day
    if 'MINT' not in daily_counts.columns:
        daily_counts['MINT'] = 0
    if 'TRANSFER' not in daily_counts.columns:
        daily_counts['TRANSFER'] = 0
    
    # Plot
    plt.figure(figsize=(12, 6))
    daily_counts.plot(kind='line', ax=plt.gca(), marker='o')
    plt.title('NFT Transactions Over Time')
    plt.xlabel('Date')
    plt.ylabel('Number of Transactions')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(['Mints', 'Transfers'])
    plt.tight_layout()
    plt.savefig(f'{output_dir}/transactions_over_time.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved time series plot to {output_dir}/transactions_over_time.png")

def plot_top_receivers(df, output_dir='./plots', top_n=10):
    """Create a bar chart of top NFT receivers"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Filter out the zero address
    ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
    receivers = df[df['to'].str.lower() != ZERO_ADDRESS.lower()]
    
    # Get top receivers
    top_receivers = receivers['to'].value_counts().head(top_n)
    
    # Create shortened labels (first 6 and last 4 chars of address)
    labels = [f"{addr[:6]}...{addr[-4:]}" for addr in top_receivers.index]
    
    # Plot
    plt.figure(figsize=(12, 6))
    bars = plt.bar(range(len(top_receivers)), top_receivers.values, color='#3498db')
    plt.xticks(range(len(top_receivers)), labels, rotation=45, ha='right')
    plt.title(f'Top {top_n} NFT Receivers')
    plt.xlabel('Address')
    plt.ylabel('Number of NFTs Received')
    plt.grid(True, axis='y', linestyle='--', alpha=0.7)
    
    # Add count labels on top of each bar
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                 f'{height:.0f}', ha='center', va='bottom')
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/top_receivers.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved top receivers plot to {output_dir}/top_receivers.png")

def main():
    parser = argparse.ArgumentParser(description='Generate visualizations from NFT transaction data')
    parser.add_argument('--input', default='transactions.csv', help='Input CSV file with transaction data')
    parser.add_argument('--output-dir', default='./plots', help='Directory to save output plots')
    parser.add_argument('--top-n', type=int, default=10, help='Number of top receivers to show')
    
    args = parser.parse_args()
    
    # Load the transaction data
    try:
        df = pd.read_csv(args.input)
        print(f"Loaded {len(df)} transaction records from {args.input}")
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return
    
    # Generate plots
    plot_transaction_types(df, output_dir=args.output_dir)
    plot_transactions_over_time(df, output_dir=args.output_dir)
    plot_top_receivers(df, output_dir=args.output_dir, top_n=args.top_n)
    
    print("Visualization complete!")

if __name__ == "__main__":
    main() 