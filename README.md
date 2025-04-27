# <div align="center">🔗 ChainTrace</div>

<div align="center">
  <!-- <img src="https://user-images.githubusercontent.com/46517096/185902404-94ab24f2-d8b2-4839-8033-24b14a1869dd.png" alt="ChainTrace Logo" width="200" height="200" /> -->
  <p><em>A powerful Ethereum NFT transaction analyzer and insights generator</em></p>
  
  [![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
  [![Node.js 20+](https://img.shields.io/badge/Node.js-20+-green.svg)](https://nodejs.org/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

## 📋 Overview

ChainTrace is a blockchain analysis tool designed to help researchers, collectors, and developers gain insights into NFT transaction histories. By analyzing on-chain data, ChainTrace provides comprehensive visualizations and statistics about how NFTs move through the Ethereum ecosystem, from initial minting events to subsequent transfers.

## ✨ Features

- 📊 Complete transaction history for any NFT contract
- 🔄 Automatic categorization of mints vs transfers
- 📈 Statistical analysis of top holders and busiest periods
- ⚡ Smart handling of RPC rate limits with automatic fallbacks
- 📁 CSV and JSON exports for further analysis

## 🚀 Quick Start

### Prerequisites

Choose either Python or Node.js implementation:

<details>
<summary><b>Python Setup</b></summary>

1. Ensure you have Python 3.10+ installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run with:
   ```bash
   python nft_analyzer.py --contract YOUR_CONTRACT_ADDRESS
   ```
</details>

<details>
<summary><b>Node.js Setup</b></summary>

1. Ensure you have Node.js 20+ installed
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run with:
   ```bash
   node nft_analyzer.js --contract YOUR_CONTRACT_ADDRESS
   ```
</details>

## 🔑 Setting Up Ethereum RPC Access

ChainTrace requires access to Ethereum blockchain data via an RPC endpoint. Create a `.env` file in the root directory with:

```
ALCHEMY_RPC=https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY
INFURA_RPC=https://mainnet.infura.io/v3/YOUR_API_KEY
```

### Getting Free API Keys

| Provider | Sign-up Link | Free Tier |
|----------|-------------|-----------|
| Alchemy | [alchemy.com](https://www.alchemy.com) | 300M compute units/month |
| Infura | [infura.io](https://infura.io) | 100K requests/day |

## 📝 Usage Examples

### Analyze a Specific NFT Collection

```bash
# For Python
python nft_analyzer.py --contract 0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e

# For Node.js
node nft_analyzer.js --contract 0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e
```

### Analyze a Specific Block Range

```bash
python nft_analyzer.py --contract 0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e --start 14000000 --end 14100000
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--contract` | NFT contract address (required) | - |
| `--start` | Starting block number | 0 |
| `--end` | Ending block number | latest |
| `--batch` | Batch size for requests | 10000 |
| `--output` | Output directory | auto-generated |

## 📊 Output and Analysis

ChainTrace creates a structured output directory containing:

```
output_[contract]_[timestamp]/
├── data/
│   ├── transactions.csv
│   ├── transactions.json
│   └── raw_logs.json
├── logs/
│   ├── nft_analyzer.log
│   └── run_parameters.json
├── stats/
│   ├── analysis_summary.txt
│   └── analysis_stats.json
└── README.md
```

### Analysis Insights

ChainTrace provides several key insights about the NFT collection:

- ✅ Total number of mint events
- 🔄 Total number of transfer events
- 👥 Top addresses receiving NFTs
- 📅 Busiest days for transactions
- 🔍 Full transaction history for further analysis

## 🛠️ Advanced Features

### Smart RPC Fallback

ChainTrace intelligently handles rate limiting by:
- Automatically switching between providers when rate limits are hit
- Dynamically reducing batch sizes when necessary
- Adding appropriate delays between retries

### Performance Tips

- For large contracts, use a smaller block range to avoid timeouts
- Reduce the batch size with `--batch` parameter for busy contracts
- For initial exploration, focus on a recent time period first

## 👨‍💻 Contributing

Contributions to ChainTrace are welcome! Feel free to submit a pull request or open an issue to improve the tool.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

<div align="center">
  <p>Made with ❤️ by Nat</p>
  
  <!-- <a href="https://github.com/yourusername">
    <img src="https://github.com/yourusername.png" width="50px" alt="Profile" style="border-radius:50%" />
  </a> -->
</div> 