from web3 import Web3
import pandas as pd
import csv
from datetime import datetime
import os
import argparse
from dotenv import load_dotenv
import time
import logging
import json
import sys
import matplotlib.pyplot as plt
import shutil

# Constants
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# Try to load environment variables, but provide fallbacks
try:
    load_dotenv()
    # RPC endpoints from .env
    RPC_ENDPOINTS = [
        os.getenv("ALCHEMY_RPC"),
        os.getenv("INFURA_RPC"),
        os.getenv("CLOUDFLARE_RPC", "https://cloudflare-eth.com")
    ]
    # Filter out None values in case some are not defined
    RPC_ENDPOINTS = [rpc for rpc in RPC_ENDPOINTS if rpc]
    
    if not RPC_ENDPOINTS:
        # If no endpoints were found in .env, use public endpoints
        RPC_ENDPOINTS = [
            "https://cloudflare-eth.com",  # Cloudflare's public endpoint
            "https://eth.llamarpc.com"     # LlamaRPC public endpoint
        ]
except Exception as e:
    # Fallback to public endpoints
    RPC_ENDPOINTS = [
        "https://cloudflare-eth.com",
        "https://eth.llamarpc.com"
    ]
    print(f"Warning: Error loading .env file: {e}. Using public RPC endpoints.")

def setup_directories(contract_address):
    """
    Create a structured output directory based on the contract address and timestamp.
    """
    # Create a timestamp for the run
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create main output directory with contract as name
    short_addr = contract_address[:10]  # First 10 chars of address
    output_dir = f"output_{short_addr}_{timestamp}"
    
    # Create subdirectories
    dirs = {
        'main': output_dir,
        'logs': os.path.join(output_dir, 'logs'),
        'data': os.path.join(output_dir, 'data'),
        'stats': os.path.join(output_dir, 'stats'),
        'plots': os.path.join(output_dir, 'plots')
    }
    
    # Create all directories
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    
    return dirs

def setup_logging(log_dir):
    """
    Configure logging to both file and console.
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Create handlers
    log_file = os.path.join(log_dir, 'nft_analyzer.log')
    file_handler = logging.FileHandler(log_file)
    console_handler = logging.StreamHandler()
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_fallback_web3_provider(logger):
    """Try to establish connection with different RPC endpoints"""
    if not RPC_ENDPOINTS:
        raise Exception("No RPC endpoints configured. Please check your .env file or add public endpoints.")
        
    for endpoint in RPC_ENDPOINTS:
        try:
            provider = Web3(Web3.HTTPProvider(endpoint))
            if provider.is_connected():
                logger.info(f"Connected to Ethereum node at {endpoint[:30]}...")
                return provider
        except Exception as e:
            logger.warning(f"Failed to connect to {endpoint[:30]}... - {str(e)}")
    
    raise Exception("Could not connect to any RPC endpoint. Please check your internet connection or API keys.")

def get_block_timestamp(w3, block_number):
    block = w3.eth.get_block(block_number)
    return datetime.fromtimestamp(block.timestamp).strftime('%Y-%m-%d')

def fetch_transfer_logs(w3, contract_address, start_block=0, end_block="latest", batch_size=10000, logger=None):
    """
    Fetch all Transfer events from an ERC-721 contract within a block range.
    Uses pagination and handles rate limiting gracefully.
    """
    logger = logger or logging.getLogger()
    
    # Convert start_block to int
    start_block = int(start_block)
    
    # Handle 'latest' end_block
    if end_block == "latest":
        end_block = w3.eth.block_number
    else:
        end_block = int(end_block)
    
    # For large block ranges, use a smaller initial batch size to avoid rate limits
    if (end_block - start_block) > 10000:
        batch_size = min(batch_size, 2000)
        logger.info(f"Large block range detected. Using smaller batch size: {batch_size}")
    
    # Create the transfer filter
    transfer_event_signature = w3.keccak(text="Transfer(address,address,uint256)").hex()
    
    logger.info(f"Fetching logs from block {start_block} to {end_block}")
    
    all_logs = []
    current_start = start_block
    
    while current_start <= end_block:
        current_end = min(current_start + batch_size - 1, end_block)
        logger.info(f"Fetching batch: {current_start} to {current_end}")
        
        retry_count = 0
        max_retries = 3
        success = False
        
        while not success and retry_count < max_retries:
            try:
                logs = w3.eth.get_logs({
                    'fromBlock': current_start,
                    'toBlock': current_end,
                    'address': contract_address,
                    'topics': [transfer_event_signature]
                })
                
                all_logs.extend(logs)
                current_start = current_end + 1
                success = True
                logger.info(f"Successfully fetched {len(logs)} logs")
                
            except Exception as e:
                retry_count += 1
                error_msg = str(e).lower()
                
                # Check if this is a rate limit error
                if any(term in error_msg for term in ["rate", "limit", "429", "too many", "exceeded"]):
                    batch_size = max(100, batch_size // 2)
                    logger.warning(f"Rate limit hit: {e}. Reducing batch size to {batch_size}")
                    current_end = min(current_start + batch_size - 1, end_block)
                    time.sleep(2)  # Add delay before retry
                    
                # Check if this is a timeout error
                elif any(term in error_msg for term in ["timeout", "timed out"]):
                    logger.warning(f"Timeout error: {e}. Retrying in 5 seconds...")
                    time.sleep(5)
                    
                # Check if request was too large
                elif "block range" in error_msg or "block limit" in error_msg or "range too large" in error_msg or "400" in error_msg or "bad request" in error_msg:
                    batch_size = max(100, batch_size // 4)  # More aggressive reduction
                    logger.warning(f"Block range too large or bad request: {e}. Reducing batch size to {batch_size}")
                    current_end = min(current_start + batch_size - 1, end_block)
                    time.sleep(1)  # Add a small delay
                    
                # For other errors, just try to switch providers
                else:
                    logger.error(f"Error fetching logs: {e}")
                    try:
                        logger.info("Attempting to switch providers...")
                        w3 = get_fallback_web3_provider(logger)
                    except Exception as provider_error:
                        logger.error(f"Could not switch providers: {provider_error}")
                        # If we're on the last retry, raise the original error
                        if retry_count == max_retries - 1:
                            raise
        
        # If we failed after all retries, raise an exception
        if not success:
            raise Exception(f"Failed to fetch logs after {max_retries} retries.")
    
    logger.info(f"Successfully fetched all {len(all_logs)} logs across block range {start_block}-{end_block}")
    return all_logs

def decode_transfer_log(w3, log):
    """
    Decode a Transfer event log into a structured object.
    """
    try:
        # Check if log is a dictionary or AttributeDict
        if hasattr(log, 'topics'):
            # It's an AttributeDict
            topics = log.topics
            tx_hash = log.transactionHash.hex() if hasattr(log.transactionHash, 'hex') else log.transactionHash
            block_number = log.blockNumber
        else:
            # It's a dictionary
            topics = log['topics']
            tx_hash = log['transactionHash'].hex() if hasattr(log['transactionHash'], 'hex') else log['transactionHash']
            block_number = log['blockNumber']
        
        # Format: Transfer(address indexed from, address indexed to, uint256 indexed tokenId)
        # Extract the last 20 bytes from the topics (the address parts)
        from_bytes = topics[1][-20:] if isinstance(topics[1], bytes) else bytes.fromhex(topics[1][2:])[-20:]
        to_bytes = topics[2][-20:] if isinstance(topics[2], bytes) else bytes.fromhex(topics[2][2:])[-20:]
        
        # Convert to hex strings
        from_hex = '0x' + from_bytes.hex()
        to_hex = '0x' + to_bytes.hex()
        
        # Convert to checksum addresses
        from_address = Web3.to_checksum_address(from_hex)
        to_address = Web3.to_checksum_address(to_hex)
        
        # Extract token ID from topic
        if isinstance(topics[3], bytes):
            token_id = int.from_bytes(topics[3], byteorder='big')
        else:
            token_id = int(topics[3][2:], 16)
        
        # Determine if this is a mint (from zero address)
        transaction_type = "MINT" if from_address == ZERO_ADDRESS else "TRANSFER"
        
        return {
            'tx_hash': tx_hash,
            'block': block_number,
            'from': from_address,
            'to': to_address,
            'tokenId': str(token_id),
            'type': transaction_type
        }
    except Exception as e:
        logging.error(f"Error decoding log: {str(e)}", exc_info=True)
        # Return a partial record with available data
        tx_hash = getattr(log, 'transactionHash', None)
        if tx_hash is None and isinstance(log, dict):
            tx_hash = log.get('transactionHash')
        
        block = getattr(log, 'blockNumber', None)
        if block is None and isinstance(log, dict):
            block = log.get('blockNumber')
            
        # Convert tx_hash to hex if it's bytes
        if hasattr(tx_hash, 'hex'):
            tx_hash = tx_hash.hex()
            
        return {
            'tx_hash': tx_hash or "ERROR",
            'block': block or 0,
            'from': "ERROR",
            'to': "ERROR",
            'tokenId': "ERROR",
            'type': "ERROR"
        }

def analyze_transfers(transactions_df, output_dirs, logger):
    """
    Analyze the transfer data to extract key insights.
    """
    logger.info("Analyzing transfer data...")
    
    # Basic statistics
    total_transfers = len(transactions_df)
    mint_count = len(transactions_df[transactions_df['type'] == 'MINT'])
    transfer_count = len(transactions_df[transactions_df['type'] == 'TRANSFER'])
    
    logger.info(f"Total transactions: {total_transfers}")
    logger.info(f"Mints: {mint_count}")
    logger.info(f"Transfers: {transfer_count}")
    
    # Top receivers (excluding zero address)
    receivers = transactions_df[transactions_df['to'] != ZERO_ADDRESS]
    top_receivers = receivers['to'].value_counts().head(10)
    
    logger.info("\nTop Receivers:")
    for addr, count in top_receivers.items():
        logger.info(f"{addr}: {count} NFTs received")
    
    # Busiest days
    if 'date' in transactions_df.columns and transactions_df['date'].nunique() > 1:
        daily_counts = transactions_df['date'].value_counts().head(10)
        
        logger.info("\nBusiest Days:")
        for date, count in daily_counts.items():
            logger.info(f"{date}: {count} transactions")
    
    # Save the summary to a text file
    summary_lines = [
        "----- NFT TRANSACTION ANALYSIS -----",
        f"Total Transactions: {total_transfers}",
        f"Total Mints: {mint_count}",
        f"Total Transfers: {transfer_count}",
        "",
        "----- TOP RECEIVERS -----"
    ]
    
    for addr, count in top_receivers.items():
        summary_lines.append(f"{addr}: {count} NFTs received")
    
    if 'date' in transactions_df.columns and transactions_df['date'].nunique() > 1:
        summary_lines.append("")
        summary_lines.append("----- BUSIEST DAYS -----")
        for date, count in daily_counts.items():
            summary_lines.append(f"{date}: {count} transactions")
    
    # Save summary to file
    with open(os.path.join(output_dirs['stats'], 'analysis_summary.txt'), 'w') as f:
        f.write('\n'.join(summary_lines))
    
    # Save detailed stats as JSON
    stats = {
        'total_transactions': total_transfers,
        'total_mints': mint_count,
        'total_transfers': transfer_count,
        'top_receivers': top_receivers.to_dict(),
    }
    
    if 'date' in transactions_df.columns and transactions_df['date'].nunique() > 1:
        stats['busiest_days'] = daily_counts.to_dict()
    
    with open(os.path.join(output_dirs['stats'], 'analysis_stats.json'), 'w') as f:
        json.dump(stats, f, indent=2, default=str)
    
    logger.info(f"Analysis results saved to {output_dirs['stats']} directory")
    return stats

def main():
    """
    Main function to execute the NFT analysis.
    """
    parser = argparse.ArgumentParser(description='Analyze NFT transfers for a specific contract.')
    parser.add_argument('--contract', required=True, help='Contract address to analyze')
    parser.add_argument('--start', default=0, help='Start block for analysis')
    parser.add_argument('--end', default='latest', help='End block for analysis')
    parser.add_argument('--batch', default=10000, type=int, help='Batch size for fetching logs')
    parser.add_argument('--output', default=None, help='Base output directory (default: auto-generate)')
    
    args = parser.parse_args()
    
    # Convert contract address to checksum address
    try:
        contract_address = Web3.to_checksum_address(args.contract)
    except Exception as e:
        print(f"Error with contract address: {e}")
        print("Using the address as-is for directories")
        contract_address = args.contract
    
    # Setup output directory structure
    output_dirs = setup_directories(contract_address)
    
    # Setup logging
    logger = setup_logging(output_dirs['logs'])
    
    # Log run information
    logger.info(f"Starting NFT Analysis for contract: {contract_address}")
    logger.info(f"Block range: {args.start} to {args.end}")
    logger.info(f"Output directories created at: {output_dirs['main']}")
    
    # Save run parameters
    with open(os.path.join(output_dirs['logs'], 'run_parameters.json'), 'w') as f:
        json.dump({
            'contract': contract_address,
            'start_block': args.start,
            'end_block': args.end,
            'batch_size': args.batch,
            'timestamp': datetime.now().isoformat()
        }, f, indent=2)
    
    try:
        # Connect to Ethereum and fetch actual data
        logger.info("Connecting to Ethereum node")
        w3 = get_fallback_web3_provider(logger)
        
        # Convert start and end blocks appropriately
        start_block = int(args.start) if args.start != 'latest' else 0
        end_block = args.end
        
        logger.info(f"Fetching transfer logs for contract {contract_address}")
        logs = fetch_transfer_logs(
            w3,
            contract_address,
            start_block=start_block,
            end_block=end_block,
            batch_size=min(args.batch, 500),  # Start with a conservative batch size
            logger=logger
        )
        
        logger.info(f"Decoding {len(logs)} transfer logs")
        transactions = []
        for log in logs:
            tx_data = decode_transfer_log(w3, log)
            # Add date using block timestamp
            try:
                tx_data['date'] = get_block_timestamp(w3, tx_data['block'])
            except Exception as e:
                logger.warning(f"Could not get timestamp for block {tx_data['block']}: {e}")
                tx_data['date'] = 'unknown'
            transactions.append(tx_data)
        
        # Convert to DataFrame
        df = pd.DataFrame(transactions)
        
        if len(df) == 0:
            logger.error("No transfer logs found for this contract in the specified block range")
            return 1
        
        # Save to CSV
        csv_path = os.path.join(output_dirs['data'], 'transactions.csv')
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved {len(df)} transactions to {csv_path}")
        
        # Save as JSON too
        json_path = os.path.join(output_dirs['data'], 'transactions.json')
        df.to_json(json_path, orient='records', indent=2)
        logger.info(f"Saved JSON format to {json_path}")
        
        # Analyze the transactions
        analyze_transfers(df, output_dirs, logger)
        
        # Create a README in the output directory
        readme_content = f"""# NFT Analysis Results

## Overview
- **Contract Address**: {contract_address}
- **Block Range**: {args.start} to {args.end}
- **Analysis Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Total Transactions**: {len(df)}

## Directory Structure
- **logs/**: Contains execution logs and run parameters
- **data/**: Contains raw and processed transaction data
- **stats/**: Contains analysis results and statistics
- **plots/**: Contains visualizations (if enabled)

## Key Files
- **data/transactions.csv**: All decoded transactions in CSV format
- **data/transactions.json**: All decoded transactions in JSON format
- **stats/analysis_summary.txt**: Summary of analysis findings
- **stats/analysis_stats.json**: Detailed statistics in JSON format
"""
        
        with open(os.path.join(output_dirs['main'], 'README.md'), 'w') as f:
            f.write(readme_content)
        
        # Create a symlink to the latest output for convenience
        latest_link = 'latest_output'
        if os.path.exists(latest_link):
            if os.path.islink(latest_link):
                os.unlink(latest_link)
            else:
                shutil.rmtree(latest_link)
        
        try:
            os.symlink(output_dirs['main'], latest_link)
            logger.info(f"Created symlink 'latest_output' -> {output_dirs['main']}")
        except:
            # If symlink not supported (e.g., on Windows), create a copy
            shutil.copytree(output_dirs['main'], latest_link)
            logger.info(f"Created copy 'latest_output' from {output_dirs['main']}")
            
        logger.info(f"Analysis complete. Results available in {output_dirs['main']}")
        logger.info(f"For quick access, use the 'latest_output' directory")
            
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}", exc_info=True)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main()) 