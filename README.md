# NFT Transaction Analyzer

This tool helps you analyze NFT transfer events from ERC-721 and ERC-1155 contracts on Ethereum.

## Setup

### Python Setup
1. Ensure you have Python 3.10+ installed
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

### Node.js Setup
1. Ensure you have Node.js 20+ installed
2. Install dependencies:
   ```
   npm install
   ```

## Setting Up RPC Endpoints

The tool now supports fallback between multiple RPC endpoints to handle rate limits. Create a `.env` file with your RPC endpoints:

```
ALCHEMY_RPC=https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY
INFURA_RPC=https://mainnet.infura.io/v3/YOUR_API_KEY
```

The scripts will try using Alchemy first, then fall back to Infura if rate limits are hit.

## Getting a Free RPC Endpoint

1. **Alchemy**:
   - Sign up at [https://www.alchemy.com](https://www.alchemy.com)
   - Create a new app for Ethereum Mainnet
   - Copy the HTTPS endpoint URL

2. **Infura**:
   - Sign up at [https://infura.io](https://infura.io)
   - Create a new project
   - Copy the HTTPS endpoint URL

## Usage

### Python

Run the analyzer with:

```
python nft_analyzer.py --contract CONTRACT_ADDRESS
```

The RPC will be loaded from your .env file, but you can override it:

```
python nft_analyzer.py --rpc YOUR_RPC_URL --contract CONTRACT_ADDRESS
```

Optional parameters:
- `--start` - Starting block number (default: 0)
- `--end` - Ending block number (default: latest)
- `--batch` - Batch size for requests (default: 10000)
- `--output` - Output CSV filename (default: transactions.csv)

Example:
```
python nft_analyzer.py --contract 0x1234567890abcdef1234567890abcdef12345678
```

### Node.js

Run the analyzer with:

```
node nft_analyzer.js --contract CONTRACT_ADDRESS
```

Similarly, you can override the RPC from your .env:

```
node nft_analyzer.js --rpc YOUR_RPC_URL --contract CONTRACT_ADDRESS
```

## Fallback and Rate Limiting Handling

The tools now include:
- Automatic fallback between multiple RPC providers when rate limits are hit
- Batch size reduction when all providers hit rate limits
- Intelligent retry logic with delays to avoid repeatedly hitting rate limits

## Output

The script will:
1. Connect to the Ethereum blockchain
2. Fetch all Transfer events for the specified contract
3. Decode the events to extract transaction details
4. Categorize events as MINT or TRANSFER
5. Save the results to a CSV file with columns: `tx_hash`, `block`, `from`, `to`, `tokenId`, `type`, `date`
6. Display basic statistics about the transactions

## Tips

- For large contracts, fetching all events may take some time
- If you encounter rate limits with all providers, try reducing the initial batch size with `--batch`
- You can use `transactions.csv` for further analysis in tools like Excel or Python

## Example Analysis

After running the script, you'll get stats like:
- Total number of mints and transfers
- Top receivers of the NFTs
- Busiest days for transactions 